import uuid
from sqlalchemy import Column, String, Text, Boolean
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class Supplier(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "suppliers"

    name = Column(String(255), nullable=False)
    contact_person = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    address = Column(Text, nullable=True)
    tax_id = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)

    purchase_orders = relationship("PurchaseOrder", back_populates="supplier", lazy="select")

    def __repr__(self):
        return f"<Supplier {self.name}>"


class Customer(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "customers"

    name = Column(String(255), nullable=False)
    contact_person = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    address = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)

    sales_orders = relationship("SalesOrder", back_populates="customer", lazy="select")

    def __repr__(self):
        return f"<Customer {self.name}>"
