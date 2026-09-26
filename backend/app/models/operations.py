import uuid
from sqlalchemy import (
    Column, String, Text, ForeignKey, Numeric, Date, DateTime,
    Enum as SAEnum, Integer, Index, Boolean
)
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import relationship
import enum
from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class POStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SENT = "SENT"
    PARTIALLY_RECEIVED = "PARTIALLY_RECEIVED"
    RECEIVED = "RECEIVED"
    CANCELLED = "CANCELLED"


class ReceiptStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    WAITING = "WAITING"
    READY = "READY"
    DONE = "DONE"
    CANCELLED = "CANCELLED"


class SOStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    PARTIALLY_DELIVERED = "PARTIALLY_DELIVERED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


class DeliveryStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    WAITING = "WAITING"
    READY = "READY"
    PICKING = "PICKING"
    PACKING = "PACKING"
    DONE = "DONE"
    CANCELLED = "CANCELLED"


class TransferStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    WAITING = "WAITING"
    READY = "READY"
    DONE = "DONE"
    CANCELLED = "CANCELLED"


class AdjustmentStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    CANCELLED = "CANCELLED"


class AdjustmentReason(str, enum.Enum):
    DAMAGE = "DAMAGE"
    LOSS = "LOSS"
    FOUND_STOCK = "FOUND_STOCK"
    COUNTING_ERROR = "COUNTING_ERROR"
    EXPIRED = "EXPIRED"
    OTHER = "OTHER"


# ─── Purchase Orders ────────────────────────────────────────────────────

class PurchaseOrder(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "purchase_orders"

    po_number = Column(String(50), nullable=False, unique=True, index=True)
    supplier_id = Column(UUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=False)
    warehouse_id = Column(UUID(as_uuid=True), ForeignKey("warehouses.id"), nullable=False)
    status = Column(SAEnum(POStatus), nullable=False, default=POStatus.DRAFT)
    expected_date = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    total_amount = Column(Numeric(15, 4), nullable=True, default=0)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    supplier = relationship("Supplier", back_populates="purchase_orders")
    warehouse = relationship("Warehouse")
    items = relationship("PurchaseOrderItem", back_populates="purchase_order", cascade="all, delete-orphan")
    receipts = relationship("Receipt", back_populates="purchase_order")
    creator = relationship("User", foreign_keys=[created_by])


class PurchaseOrderItem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "purchase_order_items"

    purchase_order_id = Column(UUID(as_uuid=True), ForeignKey("purchase_orders.id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    quantity_ordered = Column(Numeric(18, 4), nullable=False)
    quantity_received = Column(Numeric(18, 4), nullable=False, default=0)
    unit_price = Column(Numeric(12, 4), nullable=True, default=0)

    purchase_order = relationship("PurchaseOrder", back_populates="items")
    product = relationship("Product")


# ─── Receipts ───────────────────────────────────────────────────────────

class Receipt(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "receipts"

    receipt_number = Column(String(50), nullable=False, unique=True, index=True)
    supplier_id = Column(UUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=True)
    purchase_order_id = Column(UUID(as_uuid=True), ForeignKey("purchase_orders.id"), nullable=True)
    warehouse_id = Column(UUID(as_uuid=True), ForeignKey("warehouses.id"), nullable=False)
    destination_location_id = Column(UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False)
    status = Column(SAEnum(ReceiptStatus), nullable=False, default=ReceiptStatus.DRAFT)
    scheduled_date = Column(Date, nullable=True)
    validated_at = Column(DateTime(timezone=True), nullable=True)
    validated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    notes = Column(Text, nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    idempotency_key = Column(String(255), nullable=True, unique=True)

    supplier = relationship("Supplier")
    purchase_order = relationship("PurchaseOrder", back_populates="receipts")
    warehouse = relationship("Warehouse")
    destination_location = relationship("Location", foreign_keys=[destination_location_id])
    items = relationship("ReceiptItem", back_populates="receipt", cascade="all, delete-orphan")
    validator = relationship("User", foreign_keys=[validated_by])
    creator = relationship("User", foreign_keys=[created_by])


class ReceiptItem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "receipt_items"

    receipt_id = Column(UUID(as_uuid=True), ForeignKey("receipts.id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    quantity_expected = Column(Numeric(18, 4), nullable=True)
    quantity_received = Column(Numeric(18, 4), nullable=False, default=0)
    unit_cost = Column(Numeric(12, 4), nullable=True, default=0)
    batch_id = Column(UUID(as_uuid=True), ForeignKey("batches.id"), nullable=True)

    receipt = relationship("Receipt", back_populates="items")
    product = relationship("Product")
    batch = relationship("Batch")


# ─── Sales Orders ───────────────────────────────────────────────────────

class SalesOrder(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "sales_orders"

    so_number = Column(String(50), nullable=False, unique=True, index=True)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    warehouse_id = Column(UUID(as_uuid=True), ForeignKey("warehouses.id"), nullable=False)
    status = Column(SAEnum(SOStatus), nullable=False, default=SOStatus.DRAFT)
    delivery_date = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    total_amount = Column(Numeric(15, 4), nullable=True, default=0)
    discount = Column(Numeric(5, 2), nullable=True, default=0)
    tax = Column(Numeric(5, 2), nullable=True, default=0)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    customer = relationship("Customer", back_populates="sales_orders")
    warehouse = relationship("Warehouse")
    items = relationship("SalesOrderItem", back_populates="sales_order", cascade="all, delete-orphan")
    deliveries = relationship("Delivery", back_populates="sales_order")
    creator = relationship("User", foreign_keys=[created_by])


class SalesOrderItem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "sales_order_items"

    sales_order_id = Column(UUID(as_uuid=True), ForeignKey("sales_orders.id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    quantity_ordered = Column(Numeric(18, 4), nullable=False)
    quantity_delivered = Column(Numeric(18, 4), nullable=False, default=0)
    unit_price = Column(Numeric(12, 4), nullable=True, default=0)

    sales_order = relationship("SalesOrder", back_populates="items")
    product = relationship("Product")


# ─── Deliveries ─────────────────────────────────────────────────────────

class Delivery(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "deliveries"

    delivery_number = Column(String(50), nullable=False, unique=True, index=True)
    sales_order_id = Column(UUID(as_uuid=True), ForeignKey("sales_orders.id"), nullable=True)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True)
    warehouse_id = Column(UUID(as_uuid=True), ForeignKey("warehouses.id"), nullable=False)
    source_location_id = Column(UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False)
    status = Column(SAEnum(DeliveryStatus), nullable=False, default=DeliveryStatus.DRAFT)
    scheduled_date = Column(Date, nullable=True)
    validated_at = Column(DateTime(timezone=True), nullable=True)
    validated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    notes = Column(Text, nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    idempotency_key = Column(String(255), nullable=True, unique=True)

    sales_order = relationship("SalesOrder", back_populates="deliveries")
    customer = relationship("Customer")
    warehouse = relationship("Warehouse")
    source_location = relationship("Location", foreign_keys=[source_location_id])
    items = relationship("DeliveryItem", back_populates="delivery", cascade="all, delete-orphan")
    validator = relationship("User", foreign_keys=[validated_by])
    creator = relationship("User", foreign_keys=[created_by])


class DeliveryItem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "delivery_items"

    delivery_id = Column(UUID(as_uuid=True), ForeignKey("deliveries.id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    quantity_demanded = Column(Numeric(18, 4), nullable=False)
    quantity_picked = Column(Numeric(18, 4), nullable=False, default=0)
    quantity_packed = Column(Numeric(18, 4), nullable=False, default=0)
    quantity_done = Column(Numeric(18, 4), nullable=False, default=0)
    location_id = Column(UUID(as_uuid=True), ForeignKey("locations.id"), nullable=True)

    delivery = relationship("Delivery", back_populates="items")
    product = relationship("Product")
    location = relationship("Location", foreign_keys=[location_id])


# ─── Internal Transfers ─────────────────────────────────────────────────

class Transfer(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "transfers"

    transfer_number = Column(String(50), nullable=False, unique=True, index=True)
    source_warehouse_id = Column(UUID(as_uuid=True), ForeignKey("warehouses.id"), nullable=False)
    source_location_id = Column(UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False)
    destination_warehouse_id = Column(UUID(as_uuid=True), ForeignKey("warehouses.id"), nullable=False)
    destination_location_id = Column(UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False)
    status = Column(SAEnum(TransferStatus), nullable=False, default=TransferStatus.DRAFT)
    scheduled_date = Column(Date, nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    idempotency_key = Column(String(255), nullable=True, unique=True)

    source_warehouse = relationship("Warehouse", foreign_keys=[source_warehouse_id])
    source_location = relationship("Location", foreign_keys=[source_location_id])
    destination_warehouse = relationship("Warehouse", foreign_keys=[destination_warehouse_id])
    destination_location = relationship("Location", foreign_keys=[destination_location_id])
    items = relationship("TransferItem", back_populates="transfer", cascade="all, delete-orphan")
    creator = relationship("User", foreign_keys=[created_by])


class TransferItem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "transfer_items"

    transfer_id = Column(UUID(as_uuid=True), ForeignKey("transfers.id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    quantity = Column(Numeric(18, 4), nullable=False)
    quantity_done = Column(Numeric(18, 4), nullable=False, default=0)

    transfer = relationship("Transfer", back_populates="items")
    product = relationship("Product")


# ─── Adjustments ────────────────────────────────────────────────────────

class Adjustment(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "adjustments"

    adjustment_number = Column(String(50), nullable=False, unique=True, index=True)
    warehouse_id = Column(UUID(as_uuid=True), ForeignKey("warehouses.id"), nullable=False)
    location_id = Column(UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False)
    status = Column(SAEnum(AdjustmentStatus), nullable=False, default=AdjustmentStatus.DRAFT)
    reason = Column(SAEnum(AdjustmentReason), nullable=False, default=AdjustmentReason.OTHER)
    notes = Column(Text, nullable=True)
    validated_at = Column(DateTime(timezone=True), nullable=True)
    validated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    warehouse = relationship("Warehouse")
    location = relationship("Location", foreign_keys=[location_id])
    items = relationship("AdjustmentItem", back_populates="adjustment", cascade="all, delete-orphan")
    validator = relationship("User", foreign_keys=[validated_by])
    creator = relationship("User", foreign_keys=[created_by])


class AdjustmentItem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "adjustment_items"

    adjustment_id = Column(UUID(as_uuid=True), ForeignKey("adjustments.id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    system_quantity = Column(Numeric(18, 4), nullable=False)
    counted_quantity = Column(Numeric(18, 4), nullable=False)
    difference = Column(Numeric(18, 4), nullable=False)  # counted - system

    adjustment = relationship("Adjustment", back_populates="items")
    product = relationship("Product")


# ─── Stock Counts ────────────────────────────────────────────────────────

class StockCountStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    APPROVED = "APPROVED"
    CANCELLED = "CANCELLED"


class StockCount(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "stock_counts"

    count_number = Column(String(50), nullable=False, unique=True, index=True)
    warehouse_id = Column(UUID(as_uuid=True), ForeignKey("warehouses.id"), nullable=False)
    status = Column(SAEnum(StockCountStatus), nullable=False, default=StockCountStatus.DRAFT)
    blind_mode = Column(Boolean, default=True)
    notes = Column(Text, nullable=True)
    assigned_to = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    approved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    warehouse = relationship("Warehouse")
    items = relationship("StockCountItem", back_populates="stock_count", cascade="all, delete-orphan")
    assignee = relationship("User", foreign_keys=[assigned_to])
    approver = relationship("User", foreign_keys=[approved_by])
    creator = relationship("User", foreign_keys=[created_by])


class StockCountItem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "stock_count_items"

    stock_count_id = Column(UUID(as_uuid=True), ForeignKey("stock_counts.id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    location_id = Column(UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False)
    system_quantity = Column(Numeric(18, 4), nullable=True)
    counted_quantity = Column(Numeric(18, 4), nullable=True)
    is_counted = Column(Boolean, default=False)

    stock_count = relationship("StockCount", back_populates="items")
    product = relationship("Product")
    location = relationship("Location")
