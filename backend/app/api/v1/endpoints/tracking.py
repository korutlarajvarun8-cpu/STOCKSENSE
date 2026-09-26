from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.models.user import User, UserRole
from app.models.tracking import Batch, SerialNumber, ReorderRule
from app.models.product import Product

router = APIRouter(tags=["Tracking & Advanced Warehouse"])

# ─── Batches ─────────────────────────────────────────────────────────────────

batch_router = APIRouter(prefix="/batches", tags=["Batches"])

@batch_router.get("")
async def list_batches(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
    product_id: Optional[uuid.UUID] = None,
):
    q = select(Batch).options(selectinload(Batch.product))
    if product_id:
        q = q.where(Batch.product_id == product_id)
    
    # MySQL: NULLS LAST is not supported; use case() to push NULLs to end
    from sqlalchemy import case
    result = await db.execute(q.order_by(
        case((Batch.expiry_date.is_(None), 1), else_=0),
        Batch.expiry_date.asc()
    ))
    batches = result.scalars().all()
    
    return [
        {
            "id": str(b.id),
            "batch_number": b.batch_number,
            "product_id": str(b.product_id),
            "product_name": b.product.name if b.product else None,
            "manufacture_date": b.manufacture_date.isoformat() if b.manufacture_date else None,
            "expiry_date": b.expiry_date.isoformat() if b.expiry_date else None,
            "quantity": float(b.quantity),
            "notes": b.notes
        }
        for b in batches
    ]

# ─── Serial Numbers ─────────────────────────────────────────────────────────

serial_router = APIRouter(prefix="/serials", tags=["Serial Numbers"])

@serial_router.get("")
async def list_serials(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
    product_id: Optional[uuid.UUID] = None,
    status: Optional[str] = None,
):
    q = select(SerialNumber).options(selectinload(SerialNumber.product))
    if product_id:
        q = q.where(SerialNumber.product_id == product_id)
    if status:
        q = q.where(SerialNumber.status == status)
        
    result = await db.execute(q.order_by(SerialNumber.created_at.desc()))
    serials = result.scalars().all()
    
    return [
        {
            "id": str(s.id),
            "serial": s.serial,
            "product_id": str(s.product_id),
            "product_name": s.product.name if s.product else None,
            "status": s.status,
            "location_id": str(s.location_id) if s.location_id else None,
            "batch_id": str(s.batch_id) if s.batch_id else None,
        }
        for s in serials
    ]

# ─── Reorder Rules ──────────────────────────────────────────────────────────

reorder_router = APIRouter(prefix="/reorder-rules", tags=["Reorder Rules"])

@reorder_router.get("")
async def list_reorder_rules(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = select(ReorderRule).options(
        selectinload(ReorderRule.product),
        selectinload(ReorderRule.warehouse)
    )
    result = await db.execute(q)
    rules = result.scalars().all()
    
    return [
        {
            "id": str(r.id),
            "product_id": str(r.product_id),
            "product_name": r.product.name if r.product else None,
            "warehouse_id": str(r.warehouse_id),
            "warehouse_name": r.warehouse.name if r.warehouse else None,
            "min_quantity": float(r.min_quantity),
            "max_quantity": float(r.max_quantity) if r.max_quantity else None,
            "reorder_quantity": float(r.reorder_quantity),
            "is_active": r.is_active
        }
        for r in rules
    ]
