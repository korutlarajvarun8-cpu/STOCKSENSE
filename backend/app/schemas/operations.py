from pydantic import BaseModel, Field
from typing import Optional, List
from decimal import Decimal
from datetime import datetime, date
import uuid
from app.models.operations import (
    POStatus, ReceiptStatus, SOStatus, DeliveryStatus,
    TransferStatus, AdjustmentStatus, AdjustmentReason, StockCountStatus
)


# ─── Purchase Orders ─────────────────────────────────────────────────────────

class POItemCreate(BaseModel):
    product_id: uuid.UUID
    quantity_ordered: Decimal = Field(..., gt=0)
    unit_price: Optional[Decimal] = Decimal("0")


class POCreate(BaseModel):
    supplier_id: uuid.UUID
    warehouse_id: uuid.UUID
    expected_date: Optional[date] = None
    notes: Optional[str] = None
    items: List[POItemCreate] = Field(..., min_length=1)


class POItemResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: Optional[str] = None
    product_sku: Optional[str] = None
    quantity_ordered: Decimal
    quantity_received: Decimal
    unit_price: Optional[Decimal] = None
    model_config = {"from_attributes": True}


class POResponse(BaseModel):
    id: uuid.UUID
    po_number: str
    supplier_id: uuid.UUID
    supplier_name: Optional[str] = None
    warehouse_id: uuid.UUID
    warehouse_name: Optional[str] = None
    status: POStatus
    expected_date: Optional[date] = None
    notes: Optional[str] = None
    total_amount: Optional[Decimal] = None
    items: List[POItemResponse] = []
    created_at: datetime
    model_config = {"from_attributes": True}


# ─── Receipts ────────────────────────────────────────────────────────────────

class ReceiptItemCreate(BaseModel):
    product_id: uuid.UUID
    quantity_received: Decimal = Field(..., gt=0)
    quantity_expected: Optional[Decimal] = None
    unit_cost: Optional[Decimal] = Decimal("0")


class ReceiptCreate(BaseModel):
    supplier_id: Optional[uuid.UUID] = None
    purchase_order_id: Optional[uuid.UUID] = None
    warehouse_id: uuid.UUID
    destination_location_id: uuid.UUID
    scheduled_date: Optional[date] = None
    notes: Optional[str] = None
    items: List[ReceiptItemCreate] = Field(..., min_length=1)


class ReceiptItemResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: Optional[str] = None
    product_sku: Optional[str] = None
    quantity_expected: Optional[Decimal] = None
    quantity_received: Decimal
    unit_cost: Optional[Decimal] = None
    model_config = {"from_attributes": True}


class ReceiptResponse(BaseModel):
    id: uuid.UUID
    receipt_number: str
    supplier_id: Optional[uuid.UUID] = None
    supplier_name: Optional[str] = None
    purchase_order_id: Optional[uuid.UUID] = None
    warehouse_id: uuid.UUID
    warehouse_name: Optional[str] = None
    destination_location_id: uuid.UUID
    destination_location_name: Optional[str] = None
    status: ReceiptStatus
    scheduled_date: Optional[date] = None
    validated_at: Optional[datetime] = None
    notes: Optional[str] = None
    items: List[ReceiptItemResponse] = []
    created_at: datetime
    model_config = {"from_attributes": True}


# ─── Sales Orders ────────────────────────────────────────────────────────────

class SOItemCreate(BaseModel):
    product_id: uuid.UUID
    quantity_ordered: Decimal = Field(..., gt=0)
    unit_price: Optional[Decimal] = Decimal("0")


class SOCreate(BaseModel):
    customer_id: uuid.UUID
    warehouse_id: uuid.UUID
    delivery_date: Optional[date] = None
    notes: Optional[str] = None
    discount: Optional[Decimal] = Decimal("0")
    tax: Optional[Decimal] = Decimal("0")
    items: List[SOItemCreate] = Field(..., min_length=1)


class SOItemResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: Optional[str] = None
    quantity_ordered: Decimal
    quantity_delivered: Decimal
    unit_price: Optional[Decimal] = None
    model_config = {"from_attributes": True}


class SOResponse(BaseModel):
    id: uuid.UUID
    so_number: str
    customer_id: uuid.UUID
    customer_name: Optional[str] = None
    warehouse_id: uuid.UUID
    status: SOStatus
    delivery_date: Optional[date] = None
    notes: Optional[str] = None
    total_amount: Optional[Decimal] = None
    items: List[SOItemResponse] = []
    created_at: datetime
    model_config = {"from_attributes": True}


# ─── Deliveries ──────────────────────────────────────────────────────────────

class DeliveryItemCreate(BaseModel):
    product_id: uuid.UUID
    quantity_demanded: Decimal = Field(..., gt=0)
    location_id: Optional[uuid.UUID] = None


class DeliveryCreate(BaseModel):
    sales_order_id: Optional[uuid.UUID] = None
    customer_id: Optional[uuid.UUID] = None
    warehouse_id: uuid.UUID
    source_location_id: uuid.UUID
    scheduled_date: Optional[date] = None
    notes: Optional[str] = None
    items: List[DeliveryItemCreate] = Field(..., min_length=1)


class DeliveryItemResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: Optional[str] = None
    product_sku: Optional[str] = None
    quantity_demanded: Decimal
    quantity_picked: Decimal
    quantity_packed: Decimal
    quantity_done: Decimal
    location_id: Optional[uuid.UUID] = None
    model_config = {"from_attributes": True}


class DeliveryResponse(BaseModel):
    id: uuid.UUID
    delivery_number: str
    sales_order_id: Optional[uuid.UUID] = None
    customer_id: Optional[uuid.UUID] = None
    customer_name: Optional[str] = None
    warehouse_id: uuid.UUID
    warehouse_name: Optional[str] = None
    source_location_id: uuid.UUID
    status: DeliveryStatus
    scheduled_date: Optional[date] = None
    validated_at: Optional[datetime] = None
    notes: Optional[str] = None
    items: List[DeliveryItemResponse] = []
    created_at: datetime
    model_config = {"from_attributes": True}


# ─── Transfers ───────────────────────────────────────────────────────────────

class TransferItemCreate(BaseModel):
    product_id: uuid.UUID
    quantity: Decimal = Field(..., gt=0)


class TransferCreate(BaseModel):
    source_warehouse_id: uuid.UUID
    source_location_id: uuid.UUID
    destination_warehouse_id: uuid.UUID
    destination_location_id: uuid.UUID
    scheduled_date: Optional[date] = None
    notes: Optional[str] = None
    items: List[TransferItemCreate] = Field(..., min_length=1)


class TransferItemResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: Optional[str] = None
    quantity: Decimal
    quantity_done: Decimal
    model_config = {"from_attributes": True}


class TransferResponse(BaseModel):
    id: uuid.UUID
    transfer_number: str
    source_warehouse_id: uuid.UUID
    source_warehouse_name: Optional[str] = None
    source_location_id: uuid.UUID
    source_location_name: Optional[str] = None
    destination_warehouse_id: uuid.UUID
    destination_warehouse_name: Optional[str] = None
    destination_location_id: uuid.UUID
    destination_location_name: Optional[str] = None
    status: TransferStatus
    scheduled_date: Optional[date] = None
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None
    items: List[TransferItemResponse] = []
    created_at: datetime
    model_config = {"from_attributes": True}


# ─── Adjustments ─────────────────────────────────────────────────────────────

class AdjustmentItemCreate(BaseModel):
    product_id: uuid.UUID
    counted_quantity: Decimal = Field(..., ge=0)


class AdjustmentCreate(BaseModel):
    warehouse_id: uuid.UUID
    location_id: uuid.UUID
    reason: AdjustmentReason = AdjustmentReason.OTHER
    notes: Optional[str] = None
    items: List[AdjustmentItemCreate] = Field(..., min_length=1)


class AdjustmentItemResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: Optional[str] = None
    system_quantity: Decimal
    counted_quantity: Decimal
    difference: Decimal
    model_config = {"from_attributes": True}


class AdjustmentResponse(BaseModel):
    id: uuid.UUID
    adjustment_number: str
    warehouse_id: uuid.UUID
    warehouse_name: Optional[str] = None
    location_id: uuid.UUID
    location_name: Optional[str] = None
    status: AdjustmentStatus
    reason: AdjustmentReason
    notes: Optional[str] = None
    validated_at: Optional[datetime] = None
    items: List[AdjustmentItemResponse] = []
    created_at: datetime
    model_config = {"from_attributes": True}


# ─── Stock Ledger ─────────────────────────────────────────────────────────────

class LedgerEntryResponse(BaseModel):
    id: uuid.UUID
    created_at: datetime
    reference: Optional[str] = None
    movement_type: str
    product_id: uuid.UUID
    product_name: Optional[str] = None
    product_sku: Optional[str] = None
    source_location_name: Optional[str] = None
    destination_location_name: Optional[str] = None
    quantity: Decimal
    quantity_before: Decimal
    quantity_after: Decimal
    user_name: Optional[str] = None
    reason: Optional[str] = None
    notes: Optional[str] = None
    model_config = {"from_attributes": True}


class PaginatedLedger(BaseModel):
    items: List[LedgerEntryResponse]
    total: int
    page: int
    page_size: int
    pages: int
