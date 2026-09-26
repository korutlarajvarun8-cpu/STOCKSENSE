import uuid
from sqlalchemy import (
    Column, String, Numeric, ForeignKey, Enum as SAEnum,
    Index, UniqueConstraint, CheckConstraint, event
)
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import relationship
import enum
from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class MovementType(str, enum.Enum):
    INITIAL_STOCK = "INITIAL_STOCK"
    RECEIPT = "RECEIPT"
    DELIVERY = "DELIVERY"
    TRANSFER_OUT = "TRANSFER_OUT"
    TRANSFER_IN = "TRANSFER_IN"
    ADJUSTMENT = "ADJUSTMENT"
    RETURN_IN = "RETURN_IN"
    RETURN_OUT = "RETURN_OUT"
    DAMAGE = "DAMAGE"
    RESERVATION = "RESERVATION"
    RELEASE = "RELEASE"
    STOCK_COUNT = "STOCK_COUNT"


class Inventory(Base, UUIDMixin, TimestampMixin):
    """
    Current stock levels per product per location.
    This is the source of truth for physical quantities.
    """
    __tablename__ = "inventory"

    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    warehouse_id = Column(UUID(as_uuid=True), ForeignKey("warehouses.id"), nullable=False)
    location_id = Column(UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False)

    # Physical quantities
    on_hand = Column(Numeric(18, 4), nullable=False, default=0)
    reserved = Column(Numeric(18, 4), nullable=False, default=0)

    # Available = on_hand - reserved (computed by app layer or DB view)
    
    product = relationship("Product", back_populates="inventory")
    warehouse = relationship("Warehouse")
    location = relationship("Location", back_populates="inventory")

    __table_args__ = (
        UniqueConstraint("product_id", "location_id", name="uq_inventory_product_location"),
        Index("ix_inventory_product_warehouse", "product_id", "warehouse_id"),
        Index("ix_inventory_location", "location_id"),
        CheckConstraint("on_hand >= 0", name="ck_inventory_on_hand_non_negative"),
        CheckConstraint("reserved >= 0", name="ck_inventory_reserved_non_negative"),
    )

    @property
    def available(self):
        return self.on_hand - self.reserved

    def __repr__(self):
        return f"<Inventory product={self.product_id} location={self.location_id} on_hand={self.on_hand}>"


class StockLedger(Base, UUIDMixin, TimestampMixin):
    """
    Immutable append-only audit trail of every stock movement.
    Never delete or modify records here.
    """
    __tablename__ = "stock_ledger"

    reference = Column(String(100), nullable=True, index=True)
    movement_type = Column(SAEnum(MovementType), nullable=False, index=True)

    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False, index=True)
    source_location_id = Column(UUID(as_uuid=True), ForeignKey("locations.id"), nullable=True)
    destination_location_id = Column(UUID(as_uuid=True), ForeignKey("locations.id"), nullable=True)

    quantity = Column(Numeric(18, 4), nullable=False)
    quantity_before = Column(Numeric(18, 4), nullable=False)
    quantity_after = Column(Numeric(18, 4), nullable=False)

    unit_cost = Column(Numeric(12, 4), nullable=True)

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reason = Column(String(255), nullable=True)
    notes = Column(String(1000), nullable=True)

    # Idempotency key to prevent duplicate ledger entries
    idempotency_key = Column(String(255), nullable=True, unique=True)

    # Relationships
    product = relationship("Product")
    source_location = relationship("Location", foreign_keys=[source_location_id])
    destination_location = relationship("Location", foreign_keys=[destination_location_id])
    user = relationship("User")

    __table_args__ = (
        Index("ix_ledger_product_created", "product_id", "created_at"),
        Index("ix_ledger_movement_type", "movement_type"),
        Index("ix_ledger_reference", "reference"),
    )

    def __repr__(self):
        return f"<StockLedger {self.movement_type} qty={self.quantity} ref={self.reference}>"


class Reservation(Base, UUIDMixin, TimestampMixin):
    """Tracks reserved quantities per product/location for pending orders."""
    __tablename__ = "reservations"

    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    location_id = Column(UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False)
    quantity = Column(Numeric(18, 4), nullable=False)
    reference = Column(String(100), nullable=False)  # e.g., SO-00001
    reference_type = Column(String(50), nullable=False)  # SALES_ORDER, DELIVERY
    is_released = Column(SAEnum("pending", "released", "consumed", name="reservation_status"), default="pending")

    product = relationship("Product")
    location = relationship("Location")
