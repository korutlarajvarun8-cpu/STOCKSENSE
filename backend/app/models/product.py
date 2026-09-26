import uuid
from sqlalchemy import (
    Column, String, Boolean, Text, ForeignKey, Numeric,
    Integer, Index, UniqueConstraint, Enum as SAEnum
)
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import relationship
import enum
from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class Category(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "categories"

    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)

    products = relationship("Product", back_populates="category", lazy="select")

    def __repr__(self):
        return f"<Category {self.name}>"


class Product(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "products"

    name = Column(String(255), nullable=False)
    sku = Column(String(100), nullable=False, unique=True, index=True)
    barcode = Column(String(100), nullable=True, unique=True, index=True)
    qr_code = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    brand = Column(String(100), nullable=True)
    unit_of_measure = Column(String(50), nullable=False, default="unit")

    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=False, index=True)
    
    cost_price = Column(Numeric(12, 4), nullable=True, default=0)
    selling_price = Column(Numeric(12, 4), nullable=True, default=0)

    reorder_level = Column(Numeric(12, 4), nullable=True, default=0)
    min_stock = Column(Numeric(12, 4), nullable=True, default=0)
    max_stock = Column(Numeric(12, 4), nullable=True, default=0)

    default_warehouse_id = Column(UUID(as_uuid=True), ForeignKey("warehouses.id"), nullable=True)
    default_location_id = Column(UUID(as_uuid=True), ForeignKey("locations.id"), nullable=True)

    image_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)

    # Tracking features
    batch_tracking = Column(Boolean, default=False)
    serial_tracking = Column(Boolean, default=False)
    expiry_tracking = Column(Boolean, default=False)

    # Relationships
    category = relationship("Category", back_populates="products")
    default_warehouse = relationship("Warehouse", foreign_keys=[default_warehouse_id])
    default_location = relationship("Location", foreign_keys=[default_location_id])
    inventory = relationship("Inventory", back_populates="product", lazy="select")
    reorder_rules = relationship("ReorderRule", back_populates="product", lazy="select")
    batches = relationship("Batch", back_populates="product", lazy="select")
    serial_numbers = relationship("SerialNumber", back_populates="product", lazy="select")

    __table_args__ = (
        Index("ix_products_name_sku", "name", "sku"),
    )

    def __repr__(self):
        return f"<Product {self.sku}: {self.name}>"
