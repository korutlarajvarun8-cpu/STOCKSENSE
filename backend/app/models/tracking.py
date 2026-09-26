import uuid
from datetime import date
from sqlalchemy import (
    Column, String, Text, ForeignKey, Numeric, Date, Boolean,
    Enum as SAEnum, UniqueConstraint
)
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import relationship
import enum
from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class SerialStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    RESERVED = "RESERVED"
    SOLD = "SOLD"
    RETURNED = "RETURNED"
    DAMAGED = "DAMAGED"


class Batch(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "batches"

    batch_number = Column(String(100), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    supplier_id = Column(UUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=True)
    manufacture_date = Column(Date, nullable=True)
    expiry_date = Column(Date, nullable=True, index=True)
    quantity = Column(Numeric(18, 4), nullable=False, default=0)
    notes = Column(Text, nullable=True)

    product = relationship("Product", back_populates="batches")
    supplier = relationship("Supplier")

    __table_args__ = (
        UniqueConstraint("batch_number", "product_id", name="uq_batch_product"),
    )


class SerialNumber(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "serial_numbers"

    serial = Column(String(200), nullable=False, unique=True, index=True)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    location_id = Column(UUID(as_uuid=True), ForeignKey("locations.id"), nullable=True)
    batch_id = Column(UUID(as_uuid=True), ForeignKey("batches.id"), nullable=True)
    status = Column(SAEnum(SerialStatus), nullable=False, default=SerialStatus.AVAILABLE)
    notes = Column(Text, nullable=True)

    product = relationship("Product", back_populates="serial_numbers")
    location = relationship("Location")
    batch = relationship("Batch")


class ReorderRule(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "reorder_rules"

    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    warehouse_id = Column(UUID(as_uuid=True), ForeignKey("warehouses.id"), nullable=False)
    location_id = Column(UUID(as_uuid=True), ForeignKey("locations.id"), nullable=True)
    min_quantity = Column(Numeric(18, 4), nullable=False, default=0)
    max_quantity = Column(Numeric(18, 4), nullable=True)
    reorder_quantity = Column(Numeric(18, 4), nullable=False, default=0)
    is_active = Column(Boolean, default=True)

    product = relationship("Product", back_populates="reorder_rules")
    warehouse = relationship("Warehouse")
    location = relationship("Location")

    __table_args__ = (
        UniqueConstraint("product_id", "warehouse_id", name="uq_reorder_product_warehouse"),
    )
