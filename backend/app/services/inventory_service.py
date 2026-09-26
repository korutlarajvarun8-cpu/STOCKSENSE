"""
INVENTORY SERVICE — The central source of truth for all stock operations.

ALL inventory-changing operations MUST go through this service.
Every operation is:
  - Transactional (atomic)
  - Idempotent (idempotency_key prevents duplicates)
  - Audited (creates ledger entries)
  - Concurrency-safe (row-level locking)
"""

import uuid
from decimal import Decimal
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, insert as sa_insert

from app.models.inventory import Inventory, StockLedger, MovementType
from app.models.product import Product
from app.models.warehouse import Location
from app.core.config import settings


class InsufficientStockError(Exception):
    """Raised when there is not enough available stock to complete an operation."""
    def __init__(self, product_name: str, available: Decimal, requested: Decimal):
        self.product_name = product_name
        self.available = available
        self.requested = requested
        super().__init__(
            f"Only {available} units of '{product_name}' are available. You requested {requested}."
        )


class DuplicateTransactionError(Exception):
    """Raised when an idempotency key collision is detected."""
    pass


class InventoryService:
    """
    Central inventory service. All stock mutations go through here.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ─── Internal Helpers ──────────────────────────────────────────────────────

    async def _get_or_create_inventory(
        self,
        product_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        location_id: uuid.UUID,
        lock: bool = False,
    ) -> Inventory:
        """Get inventory record, create if doesn't exist. Optionally lock for update."""
        query = select(Inventory).where(
            Inventory.product_id == product_id,
            Inventory.location_id == location_id,
        )
        if lock:
            query = query.with_for_update()

        result = await self.db.execute(query)
        inv = result.scalar_one_or_none()

        if inv is None:
            inv = Inventory(
                product_id=product_id,
                warehouse_id=warehouse_id,
                location_id=location_id,
                on_hand=Decimal("0"),
                reserved=Decimal("0"),
            )
            self.db.add(inv)
            await self.db.flush()

        return inv

    async def _check_idempotency(self, idempotency_key: str) -> bool:
        """Returns True if key already processed (duplicate request)."""
        result = await self.db.execute(
            select(StockLedger).where(StockLedger.idempotency_key == idempotency_key)
        )
        return result.scalar_one_or_none() is not None

    async def _create_ledger_entry(
        self,
        movement_type: MovementType,
        product_id: uuid.UUID,
        quantity: Decimal,
        quantity_before: Decimal,
        quantity_after: Decimal,
        source_location_id: Optional[uuid.UUID] = None,
        destination_location_id: Optional[uuid.UUID] = None,
        reference: Optional[str] = None,
        user_id: Optional[uuid.UUID] = None,
        reason: Optional[str] = None,
        notes: Optional[str] = None,
        unit_cost: Optional[Decimal] = None,
        idempotency_key: Optional[str] = None,
    ) -> StockLedger:
        """Create an immutable stock ledger entry."""
        entry = StockLedger(
            movement_type=movement_type,
            product_id=product_id,
            quantity=quantity,
            quantity_before=quantity_before,
            quantity_after=quantity_after,
            source_location_id=source_location_id,
            destination_location_id=destination_location_id,
            reference=reference,
            user_id=user_id,
            reason=reason,
            notes=notes,
            unit_cost=unit_cost,
            idempotency_key=idempotency_key,
        )
        self.db.add(entry)
        await self.db.flush()
        return entry

    # ─── Public Stock Operations ───────────────────────────────────────────────

    async def receive_stock(
        self,
        product_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        location_id: uuid.UUID,
        quantity: Decimal,
        reference: str,
        user_id: Optional[uuid.UUID] = None,
        unit_cost: Optional[Decimal] = None,
        notes: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> StockLedger:
        """
        Add stock (receipt, purchase return, etc.)
        Thread-safe via row-level lock.
        """
        if idempotency_key and await self._check_idempotency(idempotency_key):
            raise DuplicateTransactionError(f"Transaction {idempotency_key} already processed.")

        if quantity <= 0:
            raise ValueError("Quantity must be positive for receiving stock.")

        inv = await self._get_or_create_inventory(product_id, warehouse_id, location_id, lock=True)
        qty_before = inv.on_hand
        inv.on_hand += quantity
        qty_after = inv.on_hand

        ledger = await self._create_ledger_entry(
            movement_type=MovementType.RECEIPT,
            product_id=product_id,
            quantity=quantity,
            quantity_before=qty_before,
            quantity_after=qty_after,
            destination_location_id=location_id,
            reference=reference,
            user_id=user_id,
            notes=notes,
            unit_cost=unit_cost,
            idempotency_key=idempotency_key,
        )
        await self.db.flush()
        return ledger

    async def deliver_stock(
        self,
        product_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        location_id: uuid.UUID,
        quantity: Decimal,
        reference: str,
        user_id: Optional[uuid.UUID] = None,
        notes: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        allow_negative: bool = False,
    ) -> StockLedger:
        """
        Remove stock (delivery, sales return, etc.)
        Prevents negative stock unless explicitly allowed.
        """
        if idempotency_key and await self._check_idempotency(idempotency_key):
            raise DuplicateTransactionError(f"Transaction {idempotency_key} already processed.")

        if quantity <= 0:
            raise ValueError("Quantity must be positive for deliveries.")

        inv = await self._get_or_create_inventory(product_id, warehouse_id, location_id, lock=True)

        available = inv.on_hand - inv.reserved
        if not allow_negative and available < quantity:
            # Get product name for a useful error
            product = await self.db.get(Product, product_id)
            name = product.name if product else str(product_id)
            raise InsufficientStockError(name, available, quantity)

        qty_before = inv.on_hand
        inv.on_hand -= quantity
        # Release the reservation too
        inv.reserved = max(Decimal("0"), inv.reserved - quantity)
        qty_after = inv.on_hand

        ledger = await self._create_ledger_entry(
            movement_type=MovementType.DELIVERY,
            product_id=product_id,
            quantity=quantity,
            quantity_before=qty_before,
            quantity_after=qty_after,
            source_location_id=location_id,
            reference=reference,
            user_id=user_id,
            notes=notes,
            idempotency_key=idempotency_key,
        )
        await self.db.flush()
        return ledger

    async def transfer_stock(
        self,
        product_id: uuid.UUID,
        source_warehouse_id: uuid.UUID,
        source_location_id: uuid.UUID,
        destination_warehouse_id: uuid.UUID,
        destination_location_id: uuid.UUID,
        quantity: Decimal,
        reference: str,
        user_id: Optional[uuid.UUID] = None,
        notes: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> tuple[StockLedger, StockLedger]:
        """
        Transfer stock between locations. Company-wide total unchanged.
        Creates TRANSFER_OUT and TRANSFER_IN ledger entries.
        """
        if idempotency_key:
            out_key = f"{idempotency_key}_OUT"
            in_key = f"{idempotency_key}_IN"
            if await self._check_idempotency(out_key):
                raise DuplicateTransactionError(f"Transfer {idempotency_key} already processed.")
        else:
            out_key = in_key = None

        if quantity <= 0:
            raise ValueError("Transfer quantity must be positive.")

        # Lock source first, then destination (consistent ordering prevents deadlocks)
        source_inv = await self._get_or_create_inventory(
            product_id, source_warehouse_id, source_location_id, lock=True
        )

        available = source_inv.on_hand - source_inv.reserved
        if available < quantity:
            product = await self.db.get(Product, product_id)
            name = product.name if product else str(product_id)
            raise InsufficientStockError(name, available, quantity)

        # Source deduction
        src_before = source_inv.on_hand
        source_inv.on_hand -= quantity
        src_after = source_inv.on_hand

        ledger_out = await self._create_ledger_entry(
            movement_type=MovementType.TRANSFER_OUT,
            product_id=product_id,
            quantity=quantity,
            quantity_before=src_before,
            quantity_after=src_after,
            source_location_id=source_location_id,
            destination_location_id=destination_location_id,
            reference=reference,
            user_id=user_id,
            notes=notes,
            idempotency_key=out_key,
        )

        # Destination addition
        dest_inv = await self._get_or_create_inventory(
            product_id, destination_warehouse_id, destination_location_id, lock=True
        )
        dst_before = dest_inv.on_hand
        dest_inv.on_hand += quantity
        dst_after = dest_inv.on_hand

        ledger_in = await self._create_ledger_entry(
            movement_type=MovementType.TRANSFER_IN,
            product_id=product_id,
            quantity=quantity,
            quantity_before=dst_before,
            quantity_after=dst_after,
            source_location_id=source_location_id,
            destination_location_id=destination_location_id,
            reference=reference,
            user_id=user_id,
            notes=notes,
            idempotency_key=in_key,
        )

        await self.db.flush()
        return ledger_out, ledger_in

    async def adjust_stock(
        self,
        product_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        location_id: uuid.UUID,
        counted_quantity: Decimal,
        reference: str,
        user_id: Optional[uuid.UUID] = None,
        reason: Optional[str] = None,
        notes: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> StockLedger:
        """
        Set stock to a specific quantity (stock count adjustment).
        Difference can be positive or negative.
        """
        if idempotency_key and await self._check_idempotency(idempotency_key):
            raise DuplicateTransactionError(f"Transaction {idempotency_key} already processed.")

        if counted_quantity < 0:
            raise ValueError("Counted quantity cannot be negative.")

        inv = await self._get_or_create_inventory(product_id, warehouse_id, location_id, lock=True)
        qty_before = inv.on_hand
        difference = counted_quantity - qty_before
        inv.on_hand = counted_quantity

        ledger = await self._create_ledger_entry(
            movement_type=MovementType.ADJUSTMENT,
            product_id=product_id,
            quantity=difference,
            quantity_before=qty_before,
            quantity_after=counted_quantity,
            source_location_id=location_id if difference < 0 else None,
            destination_location_id=location_id if difference >= 0 else None,
            reference=reference,
            user_id=user_id,
            reason=reason,
            notes=notes,
            idempotency_key=idempotency_key,
        )
        await self.db.flush()
        return ledger

    async def reserve_stock(
        self,
        product_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        location_id: uuid.UUID,
        quantity: Decimal,
        reference: str,
        user_id: Optional[uuid.UUID] = None,
    ) -> Inventory:
        """Reserve stock for a pending order. Does not reduce on_hand."""
        inv = await self._get_or_create_inventory(product_id, warehouse_id, location_id, lock=True)
        available = inv.on_hand - inv.reserved

        if available < quantity:
            product = await self.db.get(Product, product_id)
            name = product.name if product else str(product_id)
            raise InsufficientStockError(name, available, quantity)

        inv.reserved += quantity

        await self._create_ledger_entry(
            movement_type=MovementType.RESERVATION,
            product_id=product_id,
            quantity=quantity,
            quantity_before=inv.on_hand,
            quantity_after=inv.on_hand,
            source_location_id=location_id,
            reference=reference,
            user_id=user_id,
        )

        await self.db.flush()
        return inv

    async def release_reservation(
        self,
        product_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        location_id: uuid.UUID,
        quantity: Decimal,
        reference: str,
        user_id: Optional[uuid.UUID] = None,
    ) -> Inventory:
        """Release reserved stock (order cancelled)."""
        inv = await self._get_or_create_inventory(product_id, warehouse_id, location_id, lock=True)
        inv.reserved = max(Decimal("0"), inv.reserved - quantity)

        await self._create_ledger_entry(
            movement_type=MovementType.RELEASE,
            product_id=product_id,
            quantity=quantity,
            quantity_before=inv.on_hand,
            quantity_after=inv.on_hand,
            destination_location_id=location_id,
            reference=reference,
            user_id=user_id,
        )

        await self.db.flush()
        return inv

    async def get_stock_summary(
        self, product_id: uuid.UUID
    ) -> dict:
        """Get aggregated stock for a product across all locations."""
        result = await self.db.execute(
            select(Inventory).where(Inventory.product_id == product_id)
        )
        inventories = result.scalars().all()

        total_on_hand = sum(i.on_hand for i in inventories)
        total_reserved = sum(i.reserved for i in inventories)

        return {
            "on_hand": total_on_hand,
            "reserved": total_reserved,
            "available": total_on_hand - total_reserved,
            "locations": [
                {
                    "location_id": str(i.location_id),
                    "warehouse_id": str(i.warehouse_id),
                    "on_hand": i.on_hand,
                    "reserved": i.reserved,
                    "available": i.on_hand - i.reserved,
                }
                for i in inventories
            ],
        }
