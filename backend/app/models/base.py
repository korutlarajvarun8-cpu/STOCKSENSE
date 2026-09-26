import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Boolean, func
from sqlalchemy import Uuid as UUID
from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at = Column(DateTime(timezone=True), default=utcnow, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, server_default=func.now())


class UUIDMixin:
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
