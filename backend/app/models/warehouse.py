import uuid
from sqlalchemy import (
    Column, String, Boolean, Text, ForeignKey, Enum as SAEnum, Integer
)
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import relationship
import enum
from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class LocationType(str, enum.Enum):
    WAREHOUSE = "WAREHOUSE"
    STORAGE = "STORAGE"
    PRODUCTION = "PRODUCTION"
    RECEIVING = "RECEIVING"
    SHIPPING = "SHIPPING"
    INTERNAL = "INTERNAL"
    DAMAGED = "DAMAGED"
    VIRTUAL = "VIRTUAL"


class Warehouse(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "warehouses"

    name = Column(String(255), nullable=False)
    code = Column(String(50), nullable=False, unique=True)
    address = Column(Text, nullable=True)
    manager_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    is_active = Column(Boolean, default=True)

    manager = relationship("User", foreign_keys=[manager_id])
    locations = relationship("Location", back_populates="warehouse", lazy="select", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Warehouse {self.code}: {self.name}>"


class Location(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "locations"

    name = Column(String(255), nullable=False)
    code = Column(String(100), nullable=False)
    warehouse_id = Column(UUID(as_uuid=True), ForeignKey("warehouses.id"), nullable=False, index=True)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("locations.id"), nullable=True)
    location_type = Column(SAEnum(LocationType), nullable=False, default=LocationType.STORAGE)
    is_active = Column(Boolean, default=True)
    barcode = Column(String(100), nullable=True)

    warehouse = relationship("Warehouse", back_populates="locations")
    parent = relationship("Location", remote_side="Location.id", foreign_keys=[parent_id])
    children = relationship("Location", foreign_keys=[parent_id], lazy="select")
    inventory = relationship("Inventory", back_populates="location", lazy="select")

    def __repr__(self):
        return f"<Location {self.code}: {self.name}>"
