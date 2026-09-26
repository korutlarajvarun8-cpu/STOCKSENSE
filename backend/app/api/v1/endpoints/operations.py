"""
Operations API — Purchase Orders, Receipts, Sales Orders, Deliveries, Transfers, Adjustments
Each workflow goes through the InventoryService for atomicity and ledger creation.
"""
import math
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.models.user import User, UserRole
from app.models.operations import (
    PurchaseOrder, PurchaseOrderItem, POStatus,
    Receipt, ReceiptItem, ReceiptStatus,
    SalesOrder, SalesOrderItem, SOStatus,
    Delivery, DeliveryItem, DeliveryStatus,
    Transfer, TransferItem, TransferStatus,
    Adjustment, AdjustmentItem, AdjustmentStatus,
    StockCount, StockCountItem, StockCountStatus,
)
from app.models.product import Product
from app.models.warehouse import Warehouse, Location
from app.models.stakeholder import Supplier, Customer
from app.models.inventory import Inventory
from app.services.inventory_service import InventoryService, InsufficientStockError, DuplicateTransactionError
from app.services.document_numbering import get_next_document_number
from app.schemas.operations import (
    POCreate, POResponse, POItemResponse,
    ReceiptCreate, ReceiptResponse, ReceiptItemResponse,
    SOCreate, SOResponse,
    DeliveryCreate, DeliveryResponse,
    TransferCreate, TransferResponse,
    AdjustmentCreate, AdjustmentResponse,
)
from app.events.websocket_manager import emit_event, EventTypes

router = APIRouter(tags=["Operations"])


# ─── Purchase Orders ──────────────────────────────────────────────────────────

po_router = APIRouter(prefix="/purchase-orders", tags=["Purchase Orders"])


@po_router.get("", response_model=List[POResponse])
async def list_pos(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
    status: Optional[POStatus] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    q = select(PurchaseOrder).options(
        selectinload(PurchaseOrder.items).selectinload(PurchaseOrderItem.product),
        selectinload(PurchaseOrder.supplier),
        selectinload(PurchaseOrder.warehouse),
    )
    if status:
        q = q.where(PurchaseOrder.status == status)
    result = await db.execute(q.order_by(PurchaseOrder.created_at.desc()).offset((page-1)*page_size).limit(page_size))
    pos = result.scalars().all()
    return [_enrich_po(po) for po in pos]


def _enrich_po(po: PurchaseOrder) -> dict:
    data = {
        "id": po.id, "po_number": po.po_number,
        "supplier_id": po.supplier_id,
        "supplier_name": po.supplier.name if po.supplier else None,
        "warehouse_id": po.warehouse_id,
        "warehouse_name": po.warehouse.name if po.warehouse else None,
        "status": po.status, "expected_date": po.expected_date,
        "notes": po.notes, "total_amount": po.total_amount,
        "created_at": po.created_at,
        "items": [
            {
                "id": i.id, "product_id": i.product_id,
                "product_name": i.product.name if i.product else None,
                "product_sku": i.product.sku if i.product else None,
                "quantity_ordered": i.quantity_ordered,
                "quantity_received": i.quantity_received,
                "unit_price": i.unit_price,
            }
            for i in po.items
        ],
    }
    return data


@po_router.post("", response_model=POResponse, status_code=201)
async def create_po(
    body: POCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.INVENTORY_MANAGER)),
):
    po_number = await get_next_document_number(db, "PURCHASE_ORDER")
    total = sum(i.quantity_ordered * (i.unit_price or 0) for i in body.items)
    po = PurchaseOrder(
        po_number=po_number,
        supplier_id=body.supplier_id,
        warehouse_id=body.warehouse_id,
        expected_date=body.expected_date,
        notes=body.notes,
        total_amount=total,
        created_by=current_user.id,
    )
    db.add(po)
    await db.flush()

    for item in body.items:
        db.add(PurchaseOrderItem(
            purchase_order_id=po.id,
            product_id=item.product_id,
            quantity_ordered=item.quantity_ordered,
            unit_price=item.unit_price,
        ))

    await db.commit()
    await db.refresh(po)
    result = await db.execute(
        select(PurchaseOrder)
        .options(
            selectinload(PurchaseOrder.items).selectinload(PurchaseOrderItem.product),
            selectinload(PurchaseOrder.supplier),
            selectinload(PurchaseOrder.warehouse),
        )
        .where(PurchaseOrder.id == po.id)
    )
    return _enrich_po(result.scalar_one())


# ─── Receipts ─────────────────────────────────────────────────────────────────

rec_router = APIRouter(prefix="/receipts", tags=["Receipts"])


def _enrich_receipt(rec: Receipt) -> dict:
    return {
        "id": rec.id, "receipt_number": rec.receipt_number,
        "supplier_id": rec.supplier_id,
        "supplier_name": rec.supplier.name if rec.supplier else None,
        "purchase_order_id": rec.purchase_order_id,
        "warehouse_id": rec.warehouse_id,
        "warehouse_name": rec.warehouse.name if rec.warehouse else None,
        "destination_location_id": rec.destination_location_id,
        "destination_location_name": rec.destination_location.name if rec.destination_location else None,
        "status": rec.status, "scheduled_date": rec.scheduled_date,
        "validated_at": rec.validated_at, "notes": rec.notes,
        "created_at": rec.created_at,
        "items": [
            {
                "id": i.id, "product_id": i.product_id,
                "product_name": i.product.name if i.product else None,
                "product_sku": i.product.sku if i.product else None,
                "quantity_expected": i.quantity_expected,
                "quantity_received": i.quantity_received,
                "unit_cost": i.unit_cost,
            }
            for i in rec.items
        ],
    }


@rec_router.get("", response_model=List[dict])
async def list_receipts(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
    status: Optional[ReceiptStatus] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    q = select(Receipt).options(
        selectinload(Receipt.items).selectinload(ReceiptItem.product),
        selectinload(Receipt.supplier),
        selectinload(Receipt.warehouse),
        selectinload(Receipt.destination_location),
    )
    if status:
        q = q.where(Receipt.status == status)
    result = await db.execute(q.order_by(Receipt.created_at.desc()).offset((page-1)*page_size).limit(page_size))
    return [_enrich_receipt(r) for r in result.scalars().all()]


@rec_router.post("", response_model=dict, status_code=201)
async def create_receipt(
    body: ReceiptCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.INVENTORY_MANAGER, UserRole.WAREHOUSE_STAFF)),
):
    rec_number = await get_next_document_number(db, "RECEIPT")
    rec = Receipt(
        receipt_number=rec_number,
        supplier_id=body.supplier_id,
        purchase_order_id=body.purchase_order_id,
        warehouse_id=body.warehouse_id,
        destination_location_id=body.destination_location_id,
        scheduled_date=body.scheduled_date,
        notes=body.notes,
        status=ReceiptStatus.WAITING,
        created_by=current_user.id,
    )
    db.add(rec)
    await db.flush()

    for item in body.items:
        db.add(ReceiptItem(
            receipt_id=rec.id,
            product_id=item.product_id,
            quantity_expected=item.quantity_expected,
            quantity_received=item.quantity_received,
            unit_cost=item.unit_cost,
        ))

    await db.commit()

    result = await db.execute(
        select(Receipt).options(
            selectinload(Receipt.items).selectinload(ReceiptItem.product),
            selectinload(Receipt.supplier),
            selectinload(Receipt.warehouse),
            selectinload(Receipt.destination_location),
        ).where(Receipt.id == rec.id)
    )
    return _enrich_receipt(result.scalar_one())


@rec_router.get("/{receipt_id}", response_model=dict)
async def get_receipt(
    receipt_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Receipt).options(
            selectinload(Receipt.items).selectinload(ReceiptItem.product),
            selectinload(Receipt.supplier),
            selectinload(Receipt.warehouse),
            selectinload(Receipt.destination_location),
        ).where(Receipt.id == receipt_id)
    )
    rec = result.scalar_one_or_none()
    if not rec:
        raise HTTPException(404, "Receipt not found.")
    return _enrich_receipt(rec)


@rec_router.post("/{receipt_id}/validate", response_model=dict)
async def validate_receipt(
    receipt_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.INVENTORY_MANAGER)),
):
    """
    Validate a receipt — the CORE transactional operation.
    Steps:
    1. Check permission (enforced by require_roles)
    2. Load and lock the receipt
    3. Validate status
    4. For each item, call InventoryService.receive_stock (atomic, idempotent)
    5. Update receipt status
    6. Commit
    7. Emit real-time event
    """
    result = await db.execute(
        select(Receipt).options(
            selectinload(Receipt.items).selectinload(ReceiptItem.product),
            selectinload(Receipt.warehouse),
            selectinload(Receipt.destination_location),
        ).where(Receipt.id == receipt_id).with_for_update()
    )
    rec = result.scalar_one_or_none()
    if not rec:
        raise HTTPException(404, "Receipt not found.")

    if rec.status == ReceiptStatus.DONE:
        raise HTTPException(400, f"Receipt {rec.receipt_number} has already been validated. Stock was not changed again.")

    if rec.status == ReceiptStatus.CANCELLED:
        raise HTTPException(400, "Cannot validate a cancelled receipt.")

    inv_service = InventoryService(db)

    for item in rec.items:
        if item.quantity_received <= 0:
            continue
        idempotency_key = f"receipt:{rec.id}:item:{item.id}"
        try:
            await inv_service.receive_stock(
                product_id=item.product_id,
                warehouse_id=rec.warehouse_id,
                location_id=rec.destination_location_id,
                quantity=Decimal(str(item.quantity_received)),
                reference=rec.receipt_number,
                user_id=current_user.id,
                unit_cost=Decimal(str(item.unit_cost)) if item.unit_cost else None,
                idempotency_key=idempotency_key,
            )
        except DuplicateTransactionError:
            raise HTTPException(400, f"Receipt {rec.receipt_number} was already validated.")

    rec.status = ReceiptStatus.DONE
    rec.validated_at = datetime.now(timezone.utc)
    rec.validated_by = current_user.id

    await db.commit()

    # Emit real-time event
    await emit_event(EventTypes.RECEIPT_COMPLETED, {
        "receipt_number": rec.receipt_number,
        "receipt_id": str(rec.id),
        "warehouse": rec.warehouse.name if rec.warehouse else None,
    })

    return {"message": f"Receipt {rec.receipt_number} validated successfully."}


# ─── Sales Orders ─────────────────────────────────────────────────────────────

so_router = APIRouter(prefix="/sales-orders", tags=["Sales Orders"])


def _enrich_so(so: SalesOrder) -> dict:
    return {
        "id": so.id, "so_number": so.so_number,
        "customer_id": so.customer_id,
        "customer_name": so.customer.name if so.customer else None,
        "warehouse_id": so.warehouse_id,
        "status": so.status,
        "delivery_date": so.delivery_date, "notes": so.notes,
        "total_amount": so.total_amount,
        "created_at": so.created_at,
        "items": [
            {
                "id": i.id, "product_id": i.product_id,
                "product_name": i.product.name if i.product else None,
                "quantity_ordered": i.quantity_ordered,
                "quantity_delivered": i.quantity_delivered,
                "unit_price": i.unit_price,
            }
            for i in so.items
        ],
    }


@so_router.get("", response_model=List[dict])
async def list_sos(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    q = select(SalesOrder).options(
        selectinload(SalesOrder.items).selectinload(SalesOrderItem.product),
        selectinload(SalesOrder.customer),
    )
    result = await db.execute(q.order_by(SalesOrder.created_at.desc()).offset((page-1)*page_size).limit(page_size))
    return [_enrich_so(so) for so in result.scalars().all()]


@so_router.post("", response_model=dict, status_code=201)
async def create_so(
    body: SOCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.INVENTORY_MANAGER)),
):
    so_number = await get_next_document_number(db, "SALES_ORDER")
    total = sum(i.quantity_ordered * (i.unit_price or 0) for i in body.items)
    so = SalesOrder(
        so_number=so_number,
        customer_id=body.customer_id,
        warehouse_id=body.warehouse_id,
        delivery_date=body.delivery_date,
        notes=body.notes,
        discount=body.discount,
        tax=body.tax,
        total_amount=total,
        created_by=current_user.id,
    )
    db.add(so)
    await db.flush()
    for item in body.items:
        db.add(SalesOrderItem(
            sales_order_id=so.id,
            product_id=item.product_id,
            quantity_ordered=item.quantity_ordered,
            unit_price=item.unit_price,
        ))
    await db.commit()
    result = await db.execute(
        select(SalesOrder).options(
            selectinload(SalesOrder.items).selectinload(SalesOrderItem.product),
            selectinload(SalesOrder.customer),
        ).where(SalesOrder.id == so.id)
    )
    return _enrich_so(result.scalar_one())


@so_router.get("/{so_id}", response_model=dict)
async def get_so(so_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(
        select(SalesOrder).options(
            selectinload(SalesOrder.items).selectinload(SalesOrderItem.product),
            selectinload(SalesOrder.customer),
        ).where(SalesOrder.id == so_id)
    )
    so = result.scalar_one_or_none()
    if not so:
        raise HTTPException(404, "Sales order not found.")
    return _enrich_so(so)


@so_router.post("/{so_id}/confirm", response_model=dict)
async def confirm_so(
    so_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.INVENTORY_MANAGER)),
):
    result = await db.execute(
        select(SalesOrder).options(
            selectinload(SalesOrder.items).selectinload(SalesOrderItem.product),
        ).where(SalesOrder.id == so_id).with_for_update()
    )
    so = result.scalar_one_or_none()
    if not so:
        raise HTTPException(404, "Sales order not found.")
    if so.status != SOStatus.DRAFT:
        raise HTTPException(400, f"Sales order is already {so.status}.")

    inv_service = InventoryService(db)

    # Reserve stock for each item
    wh_result = await db.execute(select(Warehouse).where(Warehouse.id == so.warehouse_id))
    wh = wh_result.scalar_one()

    for item in so.items:
        # Find default location in warehouse
        inv_result = await db.execute(
            select(Inventory).where(
                Inventory.product_id == item.product_id,
                Inventory.warehouse_id == so.warehouse_id,
            ).order_by(Inventory.on_hand.desc()).limit(1)
        )
        inv = inv_result.scalar_one_or_none()
        if not inv:
            raise HTTPException(400, f"No inventory found for {item.product_id} in warehouse.")

        try:
            await inv_service.reserve_stock(
                product_id=item.product_id,
                warehouse_id=so.warehouse_id,
                location_id=inv.location_id,
                quantity=Decimal(str(item.quantity_ordered)),
                reference=so.so_number,
                user_id=current_user.id,
            )
        except Exception as e:
            raise HTTPException(400, str(e))

    so.status = SOStatus.CONFIRMED
    so.confirmed_at = datetime.now(timezone.utc)
    await db.commit()
    return {"message": f"Sales order {so.so_number} confirmed. Stock reserved."}


# ─── Deliveries ───────────────────────────────────────────────────────────────

del_router = APIRouter(prefix="/deliveries", tags=["Deliveries"])


def _enrich_delivery(d: Delivery) -> dict:
    return {
        "id": d.id, "delivery_number": d.delivery_number,
        "sales_order_id": d.sales_order_id,
        "customer_id": d.customer_id,
        "customer_name": d.customer.name if d.customer else None,
        "warehouse_id": d.warehouse_id,
        "warehouse_name": d.warehouse.name if d.warehouse else None,
        "source_location_id": d.source_location_id,
        "source_location_name": d.source_location.name if d.source_location else None,
        "status": d.status, "scheduled_date": d.scheduled_date,
        "validated_at": d.validated_at, "notes": d.notes,
        "created_at": d.created_at,
        "items": [
            {
                "id": i.id, "product_id": i.product_id,
                "product_name": i.product.name if i.product else None,
                "product_sku": i.product.sku if i.product else None,
                "quantity_demanded": i.quantity_demanded,
                "quantity_picked": i.quantity_picked,
                "quantity_packed": i.quantity_packed,
                "quantity_done": i.quantity_done,
                "location_id": i.location_id,
            }
            for i in d.items
        ],
    }


@del_router.get("", response_model=List[dict])
async def list_deliveries(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    q = select(Delivery).options(
        selectinload(Delivery.items).selectinload(DeliveryItem.product),
        selectinload(Delivery.customer),
        selectinload(Delivery.warehouse),
        selectinload(Delivery.source_location),
    )
    result = await db.execute(q.order_by(Delivery.created_at.desc()).offset((page-1)*page_size).limit(page_size))
    return [_enrich_delivery(d) for d in result.scalars().all()]


@del_router.post("", response_model=dict, status_code=201)
async def create_delivery(
    body: DeliveryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.INVENTORY_MANAGER)),
):
    del_number = await get_next_document_number(db, "DELIVERY")
    d = Delivery(
        delivery_number=del_number,
        sales_order_id=body.sales_order_id,
        customer_id=body.customer_id,
        warehouse_id=body.warehouse_id,
        source_location_id=body.source_location_id,
        scheduled_date=body.scheduled_date,
        notes=body.notes,
        created_by=current_user.id,
        status=DeliveryStatus.WAITING,
    )
    db.add(d)
    await db.flush()
    for item in body.items:
        db.add(DeliveryItem(
            delivery_id=d.id,
            product_id=item.product_id,
            quantity_demanded=item.quantity_demanded,
            location_id=item.location_id or body.source_location_id,
        ))
    await db.commit()
    result = await db.execute(
        select(Delivery).options(
            selectinload(Delivery.items).selectinload(DeliveryItem.product),
            selectinload(Delivery.customer),
            selectinload(Delivery.warehouse),
            selectinload(Delivery.source_location),
        ).where(Delivery.id == d.id)
    )
    return _enrich_delivery(result.scalar_one())


@del_router.get("/{delivery_id}", response_model=dict)
async def get_delivery(delivery_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(
        select(Delivery).options(
            selectinload(Delivery.items).selectinload(DeliveryItem.product),
            selectinload(Delivery.customer),
            selectinload(Delivery.warehouse),
            selectinload(Delivery.source_location),
        ).where(Delivery.id == delivery_id)
    )
    d = result.scalar_one_or_none()
    if not d:
        raise HTTPException(404, "Delivery not found.")
    return _enrich_delivery(d)


@del_router.post("/{delivery_id}/validate", response_model=dict)
async def validate_delivery(
    delivery_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.INVENTORY_MANAGER)),
):
    result = await db.execute(
        select(Delivery).options(
            selectinload(Delivery.items).selectinload(DeliveryItem.product),
            selectinload(Delivery.warehouse),
            selectinload(Delivery.source_location),
        ).where(Delivery.id == delivery_id).with_for_update()
    )
    d = result.scalar_one_or_none()
    if not d:
        raise HTTPException(404, "Delivery not found.")
    if d.status == DeliveryStatus.DONE:
        raise HTTPException(400, f"Delivery {d.delivery_number} is already complete. Stock was not changed again.")
    if d.status == DeliveryStatus.CANCELLED:
        raise HTTPException(400, "Cannot validate a cancelled delivery.")

    inv_service = InventoryService(db)

    for item in d.items:
        qty = Decimal(str(item.quantity_demanded))
        idempotency_key = f"delivery:{d.id}:item:{item.id}"
        try:
            await inv_service.deliver_stock(
                product_id=item.product_id,
                warehouse_id=d.warehouse_id,
                location_id=item.location_id or d.source_location_id,
                quantity=qty,
                reference=d.delivery_number,
                user_id=current_user.id,
                idempotency_key=idempotency_key,
            )
        except InsufficientStockError as e:
            raise HTTPException(400, str(e))
        except DuplicateTransactionError:
            raise HTTPException(400, f"Delivery {d.delivery_number} was already validated.")

        item.quantity_done = qty

    d.status = DeliveryStatus.DONE
    d.validated_at = datetime.now(timezone.utc)
    d.validated_by = current_user.id

    await db.commit()

    await emit_event(EventTypes.DELIVERY_COMPLETED, {
        "delivery_number": d.delivery_number,
        "delivery_id": str(d.id),
    })

    return {"message": f"Delivery {d.delivery_number} completed. Stock deducted."}


# ─── Transfers ────────────────────────────────────────────────────────────────

trf_router = APIRouter(prefix="/transfers", tags=["Transfers"])


def _enrich_transfer(t: Transfer) -> dict:
    return {
        "id": t.id, "transfer_number": t.transfer_number,
        "source_warehouse_id": t.source_warehouse_id,
        "source_warehouse_name": t.source_warehouse.name if t.source_warehouse else None,
        "source_location_id": t.source_location_id,
        "source_location_name": t.source_location.name if t.source_location else None,
        "destination_warehouse_id": t.destination_warehouse_id,
        "destination_warehouse_name": t.destination_warehouse.name if t.destination_warehouse else None,
        "destination_location_id": t.destination_location_id,
        "destination_location_name": t.destination_location.name if t.destination_location else None,
        "status": t.status, "scheduled_date": t.scheduled_date,
        "completed_at": t.completed_at, "notes": t.notes,
        "created_at": t.created_at,
        "items": [
            {
                "id": i.id, "product_id": i.product_id,
                "product_name": i.product.name if i.product else None,
                "quantity": i.quantity, "quantity_done": i.quantity_done,
            }
            for i in t.items
        ],
    }


@trf_router.get("", response_model=List[dict])
async def list_transfers(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    q = select(Transfer).options(
        selectinload(Transfer.items).selectinload(TransferItem.product),
        selectinload(Transfer.source_warehouse),
        selectinload(Transfer.source_location),
        selectinload(Transfer.destination_warehouse),
        selectinload(Transfer.destination_location),
    )
    result = await db.execute(q.order_by(Transfer.created_at.desc()).offset((page-1)*page_size).limit(page_size))
    return [_enrich_transfer(t) for t in result.scalars().all()]


@trf_router.post("", response_model=dict, status_code=201)
async def create_transfer(
    body: TransferCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.INVENTORY_MANAGER, UserRole.WAREHOUSE_STAFF)),
):
    trf_number = await get_next_document_number(db, "TRANSFER")
    t = Transfer(
        transfer_number=trf_number,
        source_warehouse_id=body.source_warehouse_id,
        source_location_id=body.source_location_id,
        destination_warehouse_id=body.destination_warehouse_id,
        destination_location_id=body.destination_location_id,
        scheduled_date=body.scheduled_date,
        notes=body.notes,
        created_by=current_user.id,
    )
    db.add(t)
    await db.flush()
    for item in body.items:
        db.add(TransferItem(
            transfer_id=t.id,
            product_id=item.product_id,
            quantity=item.quantity,
        ))
    await db.commit()
    result = await db.execute(
        select(Transfer).options(
            selectinload(Transfer.items).selectinload(TransferItem.product),
            selectinload(Transfer.source_warehouse),
            selectinload(Transfer.source_location),
            selectinload(Transfer.destination_warehouse),
            selectinload(Transfer.destination_location),
        ).where(Transfer.id == t.id)
    )
    return _enrich_transfer(result.scalar_one())


@trf_router.post("/{transfer_id}/validate", response_model=dict)
async def validate_transfer(
    transfer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.INVENTORY_MANAGER, UserRole.WAREHOUSE_STAFF)),
):
    result = await db.execute(
        select(Transfer).options(
            selectinload(Transfer.items).selectinload(TransferItem.product),
        ).where(Transfer.id == transfer_id).with_for_update()
    )
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(404, "Transfer not found.")
    if t.status == TransferStatus.DONE:
        raise HTTPException(400, f"Transfer {t.transfer_number} already completed.")
    if t.status == TransferStatus.CANCELLED:
        raise HTTPException(400, "Cannot validate a cancelled transfer.")

    inv_service = InventoryService(db)

    for item in t.items:
        idempotency_key = f"transfer:{t.id}:item:{item.id}"
        try:
            await inv_service.transfer_stock(
                product_id=item.product_id,
                source_warehouse_id=t.source_warehouse_id,
                source_location_id=t.source_location_id,
                destination_warehouse_id=t.destination_warehouse_id,
                destination_location_id=t.destination_location_id,
                quantity=Decimal(str(item.quantity)),
                reference=t.transfer_number,
                user_id=current_user.id,
                idempotency_key=idempotency_key,
            )
        except InsufficientStockError as e:
            raise HTTPException(400, str(e))
        except DuplicateTransactionError:
            raise HTTPException(400, f"Transfer {t.transfer_number} was already validated.")

        item.quantity_done = item.quantity

    t.status = TransferStatus.DONE
    t.completed_at = datetime.now(timezone.utc)
    await db.commit()

    await emit_event(EventTypes.TRANSFER_COMPLETED, {
        "transfer_number": t.transfer_number,
        "transfer_id": str(t.id),
    })

    return {"message": f"Transfer {t.transfer_number} completed. Company-wide total stock unchanged."}


# ─── Adjustments ─────────────────────────────────────────────────────────────

adj_router = APIRouter(prefix="/adjustments", tags=["Adjustments"])


def _enrich_adj(a: Adjustment) -> dict:
    return {
        "id": a.id, "adjustment_number": a.adjustment_number,
        "warehouse_id": a.warehouse_id,
        "warehouse_name": a.warehouse.name if a.warehouse else None,
        "location_id": a.location_id,
        "location_name": a.location.name if a.location else None,
        "status": a.status, "reason": a.reason, "notes": a.notes,
        "validated_at": a.validated_at,
        "created_at": a.created_at,
        "items": [
            {
                "id": i.id, "product_id": i.product_id,
                "product_name": i.product.name if i.product else None,
                "system_quantity": i.system_quantity,
                "counted_quantity": i.counted_quantity,
                "difference": i.difference,
            }
            for i in a.items
        ],
    }


@adj_router.get("", response_model=List[dict])
async def list_adjustments(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    q = select(Adjustment).options(
        selectinload(Adjustment.items).selectinload(AdjustmentItem.product),
        selectinload(Adjustment.warehouse),
        selectinload(Adjustment.location),
    )
    result = await db.execute(q.order_by(Adjustment.created_at.desc()).offset((page-1)*page_size).limit(page_size))
    return [_enrich_adj(a) for a in result.scalars().all()]


@adj_router.post("", response_model=dict, status_code=201)
async def create_adjustment(
    body: AdjustmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.INVENTORY_MANAGER)),
):
    adj_number = await get_next_document_number(db, "ADJUSTMENT")
    a = Adjustment(
        adjustment_number=adj_number,
        warehouse_id=body.warehouse_id,
        location_id=body.location_id,
        reason=body.reason,
        notes=body.notes,
        created_by=current_user.id,
    )
    db.add(a)
    await db.flush()

    for item in body.items:
        # Get current system quantity
        inv_result = await db.execute(
            select(Inventory).where(
                Inventory.product_id == item.product_id,
                Inventory.location_id == body.location_id,
            )
        )
        inv = inv_result.scalar_one_or_none()
        system_qty = inv.on_hand if inv else Decimal("0")
        diff = item.counted_quantity - system_qty

        db.add(AdjustmentItem(
            adjustment_id=a.id,
            product_id=item.product_id,
            system_quantity=system_qty,
            counted_quantity=item.counted_quantity,
            difference=diff,
        ))

    await db.commit()
    result = await db.execute(
        select(Adjustment).options(
            selectinload(Adjustment.items).selectinload(AdjustmentItem.product),
            selectinload(Adjustment.warehouse),
            selectinload(Adjustment.location),
        ).where(Adjustment.id == a.id)
    )
    return _enrich_adj(result.scalar_one())


@adj_router.post("/{adjustment_id}/validate", response_model=dict)
async def validate_adjustment(
    adjustment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.INVENTORY_MANAGER)),
):
    result = await db.execute(
        select(Adjustment).options(
            selectinload(Adjustment.items).selectinload(AdjustmentItem.product),
        ).where(Adjustment.id == adjustment_id).with_for_update()
    )
    a = result.scalar_one_or_none()
    if not a:
        raise HTTPException(404, "Adjustment not found.")
    if a.status == AdjustmentStatus.VALIDATED:
        raise HTTPException(400, f"Adjustment {a.adjustment_number} already validated.")

    inv_service = InventoryService(db)

    for item in a.items:
        idempotency_key = f"adjustment:{a.id}:item:{item.id}"
        await inv_service.adjust_stock(
            product_id=item.product_id,
            warehouse_id=a.warehouse_id,
            location_id=a.location_id,
            counted_quantity=Decimal(str(item.counted_quantity)),
            reference=a.adjustment_number,
            user_id=current_user.id,
            reason=a.reason,
            notes=a.notes,
            idempotency_key=idempotency_key,
        )

    a.status = AdjustmentStatus.VALIDATED
    a.validated_at = datetime.now(timezone.utc)
    a.validated_by = current_user.id
    await db.commit()

    await emit_event(EventTypes.ADJUSTMENT_CREATED, {
        "adjustment_number": a.adjustment_number,
        "adjustment_id": str(a.id),
    })

    return {"message": f"Adjustment {a.adjustment_number} validated. Inventory updated."}
