import uuid
from sqlalchemy import (
    Column, String, Boolean, Text, ForeignKey, Enum as SAEnum,
    DateTime, Integer, func, UniqueConstraint, Index
)
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import relationship
import enum
from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    INVENTORY_MANAGER = "INVENTORY_MANAGER"
    WAREHOUSE_STAFF = "WAREHOUSE_STAFF"
    VIEWER = "VIEWER"


class User(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users"

    full_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(SAEnum(UserRole), nullable=False, default=UserRole.VIEWER)
    is_active = Column(Boolean, default=True, nullable=False)
    is_email_verified = Column(Boolean, default=False, nullable=False)
    last_login = Column(DateTime(timezone=True), nullable=True)
    avatar_url = Column(String(500), nullable=True)

    # Relationships
    audit_logs = relationship("AuditLog", back_populates="user", lazy="select")
    notifications = relationship("Notification", back_populates="user", lazy="select")

    def __repr__(self):
        return f"<User {self.email}>"
