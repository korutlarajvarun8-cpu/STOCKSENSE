import uuid
from sqlalchemy import (
    Column, String, Text, ForeignKey, Boolean, DateTime,
    Enum as SAEnum, JSON, Index
)
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import relationship
import enum
from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class NotificationSeverity(str, enum.Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    SUCCESS = "SUCCESS"


class NotificationType(str, enum.Enum):
    LOW_STOCK = "LOW_STOCK"
    OUT_OF_STOCK = "OUT_OF_STOCK"
    PENDING_RECEIPT = "PENDING_RECEIPT"
    PENDING_DELIVERY = "PENDING_DELIVERY"
    TRANSFER_SCHEDULED = "TRANSFER_SCHEDULED"
    STOCK_ADJUSTMENT = "STOCK_ADJUSTMENT"
    EXPIRY_WARNING = "EXPIRY_WARNING"
    AI_ANOMALY = "AI_ANOMALY"
    SYSTEM = "SYSTEM"


class Notification(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "notifications"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    notification_type = Column(SAEnum(NotificationType), nullable=False)
    severity = Column(SAEnum(NotificationSeverity), nullable=False, default=NotificationSeverity.INFO)
    is_read = Column(Boolean, default=False, nullable=False)
    related_document = Column(String(100), nullable=True)
    data = Column(JSON, nullable=True)

    user = relationship("User", back_populates="notifications")

    __table_args__ = (
        Index("ix_notifications_user_unread", "user_id", "is_read"),
    )


class AuditLog(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "audit_logs"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(100), nullable=False)
    resource_id = Column(String(100), nullable=True)
    before_state = Column(JSON, nullable=True)
    after_state = Column(JSON, nullable=True)
    ip_address = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)

    user = relationship("User", back_populates="audit_logs")

    __table_args__ = (
        Index("ix_audit_user_action", "user_id", "action"),
        Index("ix_audit_resource", "resource_type", "resource_id"),
    )


class DocumentSequence(Base, UUIDMixin, TimestampMixin):
    """Tracks document numbering sequences per type."""
    __tablename__ = "document_sequences"

    document_type = Column(String(50), nullable=False, unique=True)
    prefix = Column(String(20), nullable=False)
    current_number = Column(String(20), nullable=False, default="0")
    padding = Column(String(10), nullable=False, default="5")

    def get_next(self) -> str:
        next_num = int(self.current_number) + 1
        self.current_number = str(next_num)
        return f"{self.prefix}-{str(next_num).zfill(int(self.padding))}"


class Return(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "returns"

    return_number = Column(String(50), nullable=False, unique=True, index=True)
    return_type = Column(SAEnum("PURCHASE_RETURN", "SALES_RETURN", name="return_type"), nullable=False)
    reference_id = Column(UUID(as_uuid=True), nullable=True)  # receipt_id or delivery_id
    warehouse_id = Column(UUID(as_uuid=True), ForeignKey("warehouses.id"), nullable=False)
    location_id = Column(UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False)
    status = Column(SAEnum("DRAFT", "VALIDATED", "CANCELLED", name="return_status"), default="DRAFT")
    notes = Column(Text, nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    warehouse = relationship("Warehouse")
    location = relationship("Location", foreign_keys=[location_id])
    items = relationship("ReturnItem", back_populates="return_doc", cascade="all, delete-orphan")
    creator = relationship("User", foreign_keys=[created_by])


class ReturnItem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "return_items"

    return_id = Column(UUID(as_uuid=True), ForeignKey("returns.id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    quantity = Column(String(50), nullable=False)  # Numeric as string
    reason = Column(Text, nullable=True)

    return_doc = relationship("Return", back_populates="items")
    product = relationship("Product")
