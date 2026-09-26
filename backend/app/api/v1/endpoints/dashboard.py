"""
Dashboard, Reports, Stock Ledger, and AI endpoints.
"""
import math
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.core.security import decode_token
from app.models.user import User, UserRole
from app.models.product import Product
from app.models.inventory import Inventory, StockLedger, MovementType
from app.models.operations import (
    Receipt, ReceiptStatus, Delivery, DeliveryStatus,
    Transfer, TransferStatus, Adjustment,
)
from app.models.tracking import Batch, ReorderRule
from app.models.system import Notification, NotificationType, NotificationSeverity
from app.events.websocket_manager import ws_manager, emit_event
from app.core.config import settings

router = APIRouter(tags=["Dashboard & Analytics"])


# ─── Dashboard ────────────────────────────────────────────────────────────────

dash_router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@dash_router.get("")
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    # Total inventory
    inv_result = await db.execute(
        select(
            func.sum(Inventory.on_hand).label("total_on_hand"),
            func.sum(Inventory.reserved).label("total_reserved"),
            func.count(func.distinct(Inventory.product_id)).label("unique_products"),
        )
    )
    inv_totals = inv_result.one()
    total_on_hand = inv_totals.total_on_hand or 0
    total_reserved = inv_totals.total_reserved or 0

    # Inventory value (on_hand * cost_price)
    val_result = await db.execute(
        select(func.sum(Inventory.on_hand * Product.cost_price))
        .join(Product, Inventory.product_id == Product.id)
    )
    total_value = val_result.scalar() or 0

    # Low stock products
    low_stock_result = await db.execute(
        select(func.count(func.distinct(Inventory.product_id)))
        .join(Product, Inventory.product_id == Product.id)
        .where(
            Product.reorder_level > 0,
            (Inventory.on_hand - Inventory.reserved) <= Product.reorder_level,
            (Inventory.on_hand - Inventory.reserved) > 0,
        )
    )
    low_stock_count = low_stock_result.scalar() or 0

    out_of_stock_result = await db.execute(
        select(func.count(func.distinct(Inventory.product_id)))
        .where(Inventory.on_hand <= 0)
    )
    out_of_stock_count = out_of_stock_result.scalar() or 0

    # Pending receipts
    pending_rec_result = await db.execute(
        select(func.count(Receipt.id), func.sum(
            select(func.sum(func.cast(func.cast(Inventory.on_hand, "text"), "numeric")))
        ))
        .where(Receipt.status.in_([ReceiptStatus.WAITING, ReceiptStatus.READY]))
    )
    # Simpler count
    pending_rec_count = await db.execute(
        select(func.count(Receipt.id)).where(Receipt.status.in_([ReceiptStatus.WAITING, ReceiptStatus.READY]))
    )
    pending_receipts = pending_rec_count.scalar() or 0

    pending_del_count = await db.execute(
        select(func.count(Delivery.id)).where(
            Delivery.status.in_([DeliveryStatus.WAITING, DeliveryStatus.READY, DeliveryStatus.PICKING, DeliveryStatus.PACKING])
        )
    )
    pending_deliveries = pending_del_count.scalar() or 0

    pending_trf_count = await db.execute(
        select(func.count(Transfer.id)).where(
            Transfer.status.in_([TransferStatus.WAITING, TransferStatus.READY])
        )
    )
    pending_transfers = pending_trf_count.scalar() or 0

    # Recent movements (last 7 days)
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    recent_result = await db.execute(
        select(StockLedger, Product.name.label("product_name"), Product.sku.label("product_sku"))
        .join(Product, StockLedger.product_id == Product.id)
        .where(StockLedger.created_at >= seven_days_ago)
        .order_by(StockLedger.created_at.desc())
        .limit(10)
    )
    recent_movements = []
    for ledger, p_name, p_sku in recent_result.all():
        recent_movements.append({
            "id": str(ledger.id),
            "date": ledger.created_at.isoformat(),
            "type": ledger.movement_type,
            "product": p_name,
            "sku": p_sku,
            "quantity": str(ledger.quantity),
            "reference": ledger.reference,
        })

    # Stock movement chart data (last 30 days)
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    chart_result = await db.execute(
        select(
            func.date(StockLedger.created_at).label("day"),
            StockLedger.movement_type,
            func.sum(func.abs(StockLedger.quantity)).label("total"),
        )
        .where(StockLedger.created_at >= thirty_days_ago)
        .group_by(func.date(StockLedger.created_at), StockLedger.movement_type)
        .order_by(func.date(StockLedger.created_at))
    )
    chart_data = {}
    for day, move_type, total in chart_result.all():
        day_str = day.strftime("%Y-%m-%d") if hasattr(day, 'strftime') else str(day) if day else "unknown"
        if day_str not in chart_data:
            chart_data[day_str] = {"date": day_str, "incoming": 0, "outgoing": 0, "adjustments": 0}
        if move_type in [MovementType.RECEIPT, MovementType.TRANSFER_IN, MovementType.RETURN_IN]:
            chart_data[day_str]["incoming"] += float(total)
        elif move_type in [MovementType.DELIVERY, MovementType.TRANSFER_OUT, MovementType.RETURN_OUT]:
            chart_data[day_str]["outgoing"] += float(total)
        elif move_type == MovementType.ADJUSTMENT:
            chart_data[day_str]["adjustments"] += float(total)

    return {
        "kpis": {
            "total_on_hand": float(total_on_hand),
            "total_reserved": float(total_reserved),
            "total_available": float(total_on_hand - total_reserved),
            "unique_products": inv_totals.unique_products or 0,
            "total_inventory_value": float(total_value),
            "low_stock_count": low_stock_count,
            "out_of_stock_count": out_of_stock_count,
            "pending_receipts": pending_receipts,
            "pending_deliveries": pending_deliveries,
            "pending_transfers": pending_transfers,
        },
        "recent_movements": recent_movements,
        "movement_chart": list(chart_data.values()),
    }


# ─── Stock Ledger ─────────────────────────────────────────────────────────────

ledger_router = APIRouter(prefix="/ledger", tags=["Stock Ledger"])


@ledger_router.get("")
async def get_ledger(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    product_id: Optional[uuid.UUID] = Query(None),
    movement_type: Optional[str] = Query(None),
    reference: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
):
    q = (
        select(StockLedger, Product.name.label("p_name"), Product.sku.label("p_sku"), User.full_name.label("u_name"))
        .join(Product, StockLedger.product_id == Product.id)
        .outerjoin(User, StockLedger.user_id == User.id)
    )

    if product_id:
        q = q.where(StockLedger.product_id == product_id)
    if movement_type:
        q = q.where(StockLedger.movement_type == movement_type)
    if reference:
        q = q.where(StockLedger.reference.ilike(f"%{reference}%"))
    if date_from:
        q = q.where(StockLedger.created_at >= datetime.fromisoformat(date_from))
    if date_to:
        q = q.where(StockLedger.created_at <= datetime.fromisoformat(date_to))

    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar()

    result = await db.execute(
        q.order_by(StockLedger.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    items = []
    for ledger, p_name, p_sku, u_name in result.all():
        items.append({
            "id": str(ledger.id),
            "created_at": ledger.created_at.isoformat() if ledger.created_at else None,
            "reference": ledger.reference,
            "movement_type": ledger.movement_type,
            "product_id": str(ledger.product_id),
            "product_name": p_name,
            "product_sku": p_sku,
            "quantity": str(ledger.quantity),
            "quantity_before": str(ledger.quantity_before),
            "quantity_after": str(ledger.quantity_after),
            "user_name": u_name,
            "reason": ledger.reason,
            "notes": ledger.notes,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if total > 0 else 1,
    }


# ─── Reports ─────────────────────────────────────────────────────────────────

report_router = APIRouter(prefix="/reports", tags=["Reports"])


@report_router.get("/inventory-overview")
async def inventory_overview(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(
            func.count(Product.id).label("total_products"),
            func.sum(Inventory.on_hand).label("total_on_hand"),
            func.sum(Inventory.reserved).label("total_reserved"),
            func.sum(Inventory.on_hand * Product.cost_price).label("total_value"),
        )
        .outerjoin(Inventory, Inventory.product_id == Product.id)
        .where(Product.is_active == True)
    )
    row = result.one()

    # Low stock
    low = await db.execute(
        select(func.count(func.distinct(Product.id)))
        .join(Inventory, Inventory.product_id == Product.id)
        .where(Product.reorder_level > 0, (Inventory.on_hand - Inventory.reserved) <= Product.reorder_level)
    )

    return {
        "total_products": row.total_products or 0,
        "total_on_hand": float(row.total_on_hand or 0),
        "total_reserved": float(row.total_reserved or 0),
        "total_available": float((row.total_on_hand or 0) - (row.total_reserved or 0)),
        "total_value": float(row.total_value or 0),
        "low_stock_count": low.scalar() or 0,
    }


@report_router.get("/low-stock")
async def low_stock_report(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Product, func.sum(Inventory.on_hand).label("on_hand"), func.sum(Inventory.reserved).label("reserved"))
        .join(Inventory, Inventory.product_id == Product.id, isouter=True)
        .where(Product.is_active == True)
        .group_by(Product.id)
        .having(
            or_(
                func.sum(Inventory.on_hand) <= 0,
                and_(
                    Product.reorder_level > 0,
                    (func.sum(Inventory.on_hand) - func.sum(Inventory.reserved)) <= Product.reorder_level
                )
            )
        )
        .order_by(func.sum(Inventory.on_hand))
    )
    items = []
    for product, on_hand, reserved in result.all():
        on_hand = on_hand or 0
        reserved = reserved or 0
        available = on_hand - reserved
        items.append({
            "id": str(product.id),
            "name": product.name,
            "sku": product.sku,
            "on_hand": float(on_hand),
            "reserved": float(reserved),
            "available": float(available),
            "reorder_level": float(product.reorder_level or 0),
            "status": "OUT_OF_STOCK" if on_hand <= 0 else "LOW_STOCK",
        })
    return {"items": items, "total": len(items)}


@report_router.get("/stock-movement")
async def stock_movement_report(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
    days: int = Query(30, ge=1, le=365),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(
            StockLedger.movement_type,
            func.count(StockLedger.id).label("count"),
            func.sum(func.abs(StockLedger.quantity)).label("total_qty"),
        )
        .where(StockLedger.created_at >= since)
        .group_by(StockLedger.movement_type)
    )

    breakdown = {}
    for move_type, count, total_qty in result.all():
        breakdown[move_type] = {"count": count, "total_quantity": float(total_qty or 0)}

    return {
        "period_days": days,
        "breakdown": breakdown,
        "incoming": breakdown.get("RECEIPT", {}).get("total_quantity", 0),
        "outgoing": breakdown.get("DELIVERY", {}).get("total_quantity", 0),
        "adjustments": breakdown.get("ADJUSTMENT", {}).get("total_quantity", 0),
    }


# ─── Notifications ────────────────────────────────────────────────────────────

notif_router = APIRouter(prefix="/notifications", tags=["Notifications"])


@notif_router.get("")
async def list_notifications(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    unread_only: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    q = select(Notification).where(Notification.user_id == current_user.id)
    if unread_only:
        q = q.where(Notification.is_read == False)

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    result = await db.execute(
        q.order_by(Notification.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    notifications = result.scalars().all()

    unread_count = (await db.execute(
        select(func.count(Notification.id))
        .where(Notification.user_id == current_user.id, Notification.is_read == False)
    )).scalar()

    return {
        "items": [
            {
                "id": str(n.id),
                "title": n.title,
                "message": n.message,
                "type": n.notification_type,
                "severity": n.severity,
                "is_read": n.is_read,
                "related_document": n.related_document,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in notifications
        ],
        "total": total,
        "unread_count": unread_count,
        "page": page,
        "pages": math.ceil(total / page_size) if total > 0 else 1,
    }


@notif_router.post("/{notification_id}/read")
async def mark_read(
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import update
    await db.execute(
        update(Notification)
        .where(Notification.id == notification_id, Notification.user_id == current_user.id)
        .values(is_read=True)
    )
    await db.commit()
    return {"message": "Marked as read."}


@notif_router.post("/read-all")
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import update
    await db.execute(
        update(Notification)
        .where(Notification.user_id == current_user.id)
        .values(is_read=True)
    )
    await db.commit()
    return {"message": "All notifications marked as read."}


# ─── WebSocket ─────────────────────────────────────────────────────────────────

ws_router = APIRouter(tags=["WebSocket"])


@ws_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: Optional[str] = None):
    # Authenticate via token query param
    user_id = "anonymous"
    if token:
        payload = decode_token(token)
        if payload:
            user_id = payload.get("sub", "anonymous")

    await ws_manager.connect(websocket, user_id)
    try:
        while True:
            # Keep alive — client can send pings
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, user_id)


# ─── AI Endpoints ─────────────────────────────────────────────────────────────

ai_router = APIRouter(prefix="/ai", tags=["AI Intelligence"])


@ai_router.post("/assistant")
async def ai_assistant(
    request: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    AI Inventory Assistant — reads inventory data and answers questions.
    Uses OpenAI if API key is set; falls back to rule-based responses.
    AI can ONLY read — never write — inventory.
    """
    question = request.get("question", "")
    if not question:
        raise HTTPException(400, "Question is required.")

    # Gather context from database
    inv_result = await db.execute(
        select(func.sum(Inventory.on_hand).label("total"), func.count(func.distinct(Inventory.product_id)).label("products"))
    )
    inv_summary = inv_result.one()

    low_result = await db.execute(
        select(Product.name, Inventory.on_hand, Inventory.reserved, Product.reorder_level)
        .join(Inventory, Inventory.product_id == Product.id)
        .where(
            Product.reorder_level > 0,
            (Inventory.on_hand - Inventory.reserved) <= Product.reorder_level
        )
        .limit(10)
    )
    low_stock = [
        f"{name}: {float(on_hand)} on hand, {float(on_hand - reserved)} available (reorder at {float(rl)})"
        for name, on_hand, reserved, rl in low_result.all()
    ]

    context = f"""
You are StockSense AI Assistant. You help users understand their inventory data.
You can read and analyze inventory but you cannot modify stock levels.

Current inventory snapshot:
- Total units on hand: {float(inv_summary.total or 0):.0f}
- Active products tracked: {inv_summary.products or 0}
- Low stock items: {len(low_stock)}
{chr(10).join(low_stock[:5])}

IMPORTANT: You cannot modify inventory. For any changes, guide the user through the proper StockSense workflow.
"""

    if settings.OPENAI_API_KEY:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            response = await client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": context},
                    {"role": "user", "content": question},
                ],
                max_tokens=500,
                temperature=0.3,
            )
            answer = response.choices[0].message.content
        except Exception as e:
            answer = f"AI service temporarily unavailable. Based on current data: {inv_summary.total or 0} units across {inv_summary.products or 0} products tracked."
    else:
        # Rule-based fallback
        q_lower = question.lower()
        if "how many" in q_lower or "stock" in q_lower:
            answer = f"Currently tracking {inv_summary.products or 0} products with {float(inv_summary.total or 0):.0f} total units on hand."
        elif "low" in q_lower:
            if low_stock:
                answer = "Low stock items: " + "; ".join(low_stock[:3])
            else:
                answer = "No products are currently below reorder level."
        else:
            answer = f"I can see {inv_summary.products or 0} products in inventory. Could you be more specific about what you'd like to know?"

    return {"answer": answer, "context_used": True}


@ai_router.get("/forecast/{product_id}")
async def get_forecast(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Generate demand forecast based on historical movement data."""
    # Get last 90 days of movement
    ninety_days_ago = datetime.now(timezone.utc) - timedelta(days=90)
    # MySQL: group by YEARWEEK, use MIN(DATE) as the week label
    result = await db.execute(
        select(
            func.min(func.date(StockLedger.created_at)).label("week"),
            func.sum(func.abs(StockLedger.quantity)).label("demand"),
        )
        .where(
            StockLedger.product_id == product_id,
            StockLedger.movement_type == MovementType.DELIVERY,
            StockLedger.created_at >= ninety_days_ago,
        )
        .group_by(func.yearweek(StockLedger.created_at, 1))
        .order_by(func.yearweek(StockLedger.created_at, 1))
    )
    history = result.all()

    product_result = await db.execute(select(Product).where(Product.id == product_id))
    product = product_result.scalar_one_or_none()
    if not product:
        raise HTTPException(404, "Product not found.")

    inv_result = await db.execute(
        select(func.sum(Inventory.on_hand), func.sum(Inventory.reserved))
        .where(Inventory.product_id == product_id)
    )
    inv = inv_result.one()
    on_hand = float(inv[0] or 0)
    reserved = float(inv[1] or 0)
    available = on_hand - reserved

    weekly_demands = [float(row.demand) for row in history]
    avg_weekly = sum(weekly_demands) / len(weekly_demands) if weekly_demands else 0
    forecast_30_days = avg_weekly * (30 / 7)

    shortage = max(0, forecast_30_days - available)

    return {
        "product": {"id": str(product.id), "name": product.name, "sku": product.sku, "unit": product.unit_of_measure},
        "current_stock": {"on_hand": on_hand, "reserved": reserved, "available": available},
        "forecast": {
            "period_days": 30,
            "estimated_demand": round(forecast_30_days, 2),
            "average_weekly_demand": round(avg_weekly, 2),
            "weeks_of_coverage": round(available / avg_weekly, 1) if avg_weekly > 0 else 999,
            "suggested_reorder": round(shortage, 2),
        },
        "disclaimer": "Forecasts are estimates based on historical movement data. Actual demand may vary.",
        "history": [{"week": row.week.strftime("%Y-%m-%d") if hasattr(row.week, 'strftime') else str(row.week)[:10], "demand": float(row.demand)} for row in history],
    }


@ai_router.get("/anomalies")
async def detect_anomalies(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Detect unusual inventory movements."""
    twenty_four_hours_ago = datetime.now(timezone.utc) - timedelta(hours=24)
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)

    # Large recent adjustments
    adj_result = await db.execute(
        select(StockLedger, Product.name)
        .join(Product, StockLedger.product_id == Product.id)
        .where(
            StockLedger.movement_type == MovementType.ADJUSTMENT,
            StockLedger.created_at >= seven_days_ago,
            func.abs(StockLedger.quantity) > 50,
        )
        .order_by(StockLedger.created_at.desc())
        .limit(10)
    )
    anomalies = []
    for ledger, p_name in adj_result.all():
        anomalies.append({
            "product": p_name,
            "type": "LARGE_ADJUSTMENT",
            "quantity": float(ledger.quantity),
            "timestamp": ledger.created_at.isoformat() if ledger.created_at else None,
            "reference": ledger.reference,
            "severity": "HIGH" if abs(float(ledger.quantity)) > 100 else "MEDIUM",
            "message": f"Unusual inventory adjustment detected for {p_name}. Quantity: {ledger.quantity}.",
        })

    return {"anomalies": anomalies, "total": len(anomalies), "disclaimer": "Anomaly detection is advisory only."}


# ─── Users ────────────────────────────────────────────────────────────────────

users_router = APIRouter(prefix="/users", tags=["Users"])


@users_router.get("")
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    return [
        {
            "id": str(u.id), "full_name": u.full_name, "email": u.email,
            "role": u.role, "is_active": u.is_active,
            "last_login": u.last_login.isoformat() if u.last_login else None,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ]


@users_router.post("")
async def create_user(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    from app.services.auth_service import AuthService
    service = AuthService(db)
    user = await service.signup(
        full_name=body["full_name"],
        email=body["email"],
        password=body["password"],
        role=UserRole(body.get("role", "VIEWER")),
    )
    await db.commit()
    return {"id": str(user.id), "email": user.email, "role": user.role}


@users_router.put("/{user_id}")
async def update_user(
    user_id: uuid.UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    from sqlalchemy import update
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found.")
    if "role" in body:
        user.role = UserRole(body["role"])
    if "is_active" in body:
        user.is_active = body["is_active"]
    if "full_name" in body:
        user.full_name = body["full_name"]
    await db.commit()
    return {"message": "User updated."}


# ─── Search ──────────────────────────────────────────────────────────────────

search_router = APIRouter(prefix="/search", tags=["Search"])


@search_router.get("")
async def global_search(
    q: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Global Ctrl+K search across products, orders, etc."""
    term = f"%{q}%"

    # Products
    prod_result = await db.execute(
        select(Product)
        .where(
            Product.is_active == True,
            or_(Product.name.ilike(term), Product.sku.ilike(term), Product.barcode.ilike(term))
        )
        .limit(5)
    )
    products = [
        {"type": "product", "id": str(p.id), "title": p.name, "subtitle": p.sku, "url": f"/products/{p.id}"}
        for p in prod_result.scalars().all()
    ]

    # Receipts
    rec_result = await db.execute(
        select(Receipt).where(Receipt.receipt_number.ilike(term)).limit(3)
    )
    receipts = [
        {"type": "receipt", "id": str(r.id), "title": r.receipt_number, "subtitle": f"Status: {r.status}", "url": f"/receipts/{r.id}"}
        for r in rec_result.scalars().all()
    ]

    return {
        "results": products + receipts,
        "total": len(products) + len(receipts),
    }


# ─── Inventory Valuation ──────────────────────────────────────────────────────

val_router = APIRouter(prefix="/valuation", tags=["Valuation"])


@val_router.get("")
async def get_valuation(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(
            Product.name,
            Product.sku,
            Product.cost_price,
            func.sum(Inventory.on_hand).label("on_hand"),
            (func.sum(Inventory.on_hand) * Product.cost_price).label("value"),
        )
        .join(Inventory, Inventory.product_id == Product.id)
        .where(Product.is_active == True)
        .group_by(Product.id, Product.name, Product.sku, Product.cost_price)
        .order_by((func.sum(Inventory.on_hand) * Product.cost_price).desc())
    )

    items = []
    total_value = 0
    for name, sku, cost, on_hand, value in result.all():
        v = float(value or 0)
        total_value += v
        items.append({
            "name": name, "sku": sku,
            "cost_price": float(cost or 0),
            "on_hand": float(on_hand or 0),
            "value": v,
        })

    return {"total_value": total_value, "items": items, "currency": "USD", "method": "Weighted Average Cost"}
