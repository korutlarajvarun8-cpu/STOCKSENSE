"""
setup_db.py — Creates all tables directly in MySQL and seeds demo data.
Run from: d:\StockSense\backend
Usage:  py setup_db.py
"""
import asyncio
import uuid
import os
import sys
from decimal import Decimal
from datetime import datetime, timezone, timedelta

# Load .env from parent directory
sys.path.insert(0, os.path.dirname(__file__))

# Set env vars before importing app modules
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'), override=True)

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped
import bcrypt as _bcrypt

# Import all models so metadata is populated
from app.core.database import Base
import app.models  # noqa - registers all models

# MySQL async URL
DB_URL = os.environ.get(
    "DATABASE_URL",
    "mysql+aiomysql://root:Vineet%2326@localhost:3306/stocksense"
)

engine = create_async_engine(DB_URL, echo=False)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

def hash_password(pwd: str) -> str:
    return _bcrypt.hashpw(pwd.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")



async def create_tables():
    print("\n🔧 Creating tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ All tables created.")


async def seed_data():
    from app.models.user import User, UserRole
    from app.models.warehouse import Warehouse, Location
    from app.models.product import Product, Category
    from app.models.stakeholder import Supplier, Customer
    from app.models.inventory import Inventory, StockLedger, MovementType
    from app.models.system import Notification, NotificationType
    from sqlalchemy import select

    async with SessionLocal() as db:
        # ── Users ──────────────────────────────────────────────────────────
        users_data = [
            {"full_name": "Admin User",      "email": "admin@stocksense.com",   "role": UserRole.ADMIN},
            {"full_name": "Inventory Manager","email": "manager@stocksense.com", "role": UserRole.INVENTORY_MANAGER},
            {"full_name": "Warehouse Staff",  "email": "staff@stocksense.com",   "role": UserRole.WAREHOUSE_STAFF},
            {"full_name": "View Only",        "email": "viewer@stocksense.com",  "role": UserRole.VIEWER},
        ]
        users = {}
        for u in users_data:
            r = await db.execute(select(User).where(User.email == u["email"]))
            existing = r.scalar_one_or_none()
            if not existing:
                user = User(
                    id=uuid.uuid4(),
                    full_name=u["full_name"],
                    email=u["email"],
                    hashed_password=hash_password("password123"),
                    role=u["role"],
                    is_active=True,
                    is_email_verified=True,
                )
                db.add(user)
                await db.flush()
                users[u["email"]] = user
                print(f"  ✅ User created: {u['email']}")
            else:
                users[u["email"]] = existing
                print(f"  ⏩ User exists: {u['email']}")

        # ── Categories ──────────────────────────────────────────────────────
        cats = {}
        for name in ["Electronics", "Furniture", "Office Supplies"]:
            r = await db.execute(select(Category).where(Category.name == name))
            cat = r.scalar_one_or_none()
            if not cat:
                cat = Category(id=uuid.uuid4(), name=name, description=f"{name} category")
                db.add(cat)
                await db.flush()
            cats[name] = cat
        print("  ✅ Categories ready")

        # ── Warehouses ──────────────────────────────────────────────────────
        r = await db.execute(select(Warehouse).where(Warehouse.name == "Main Distribution Center"))
        wh_main = r.scalar_one_or_none()
        if not wh_main:
            wh_main = Warehouse(id=uuid.uuid4(), name="Main Distribution Center", code="MDC", is_active=True)
            db.add(wh_main)
            await db.flush()

        r = await db.execute(select(Warehouse).where(Warehouse.name == "Retail Store"))
        wh_retail = r.scalar_one_or_none()
        if not wh_retail:
            wh_retail = Warehouse(id=uuid.uuid4(), name="Retail Store", code="RTS", is_active=True)
            db.add(wh_retail)
            await db.flush()
        print("  ✅ Warehouses ready")

        # ── Locations ───────────────────────────────────────────────────────
        locs = {}
        for wh, aisle in [(wh_main, "A1"), (wh_main, "B2"), (wh_retail, "S1")]:
            r = await db.execute(select(Location).where(Location.code == aisle, Location.warehouse_id == wh.id))
            loc = r.scalar_one_or_none()
            if not loc:
                loc = Location(id=uuid.uuid4(), warehouse_id=wh.id, name=f"Aisle {aisle}", code=aisle, is_active=True)
                db.add(loc)
                await db.flush()
            locs[aisle] = loc
        print("  ✅ Locations ready")

        # ── Suppliers ───────────────────────────────────────────────────────
        r = await db.execute(select(Supplier).where(Supplier.email == "sales@techcorp.com"))
        supplier = r.scalar_one_or_none()
        if not supplier:
            supplier = Supplier(id=uuid.uuid4(), name="TechCorp Ltd", email="sales@techcorp.com", phone="+91-9800000001", is_active=True)
            db.add(supplier)
            await db.flush()
        print("  ✅ Supplier ready")

        # ── Customers ───────────────────────────────────────────────────────
        r = await db.execute(select(Customer).where(Customer.email == "purchase@enterprise.com"))
        customer = r.scalar_one_or_none()
        if not customer:
            customer = Customer(id=uuid.uuid4(), name="Enterprise Corp", email="purchase@enterprise.com", phone="+91-9900000001", is_active=True)
            db.add(customer)
            await db.flush()
        print("  ✅ Customer ready")

        # ── Products ────────────────────────────────────────────────────────
        products_data = [
            {"name": "MacBook Pro 14\"", "sku": "MBP-14-2024", "selling_price": Decimal("1999.99"), "cost_price": Decimal("1499.99"), "category": "Electronics", "reorder_level": 5, "min_stock": 2},
            {"name": "Herman Miller Aeron Chair", "sku": "HM-AERON-B", "selling_price": Decimal("1495.00"), "cost_price": Decimal("995.00"), "category": "Furniture", "reorder_level": 3, "min_stock": 1},
            {"name": "Logitech MX Master 3", "sku": "LOG-MX3-BLK", "selling_price": Decimal("99.99"), "cost_price": Decimal("59.99"), "category": "Electronics", "reorder_level": 10, "min_stock": 5},
            {"name": "Standing Desk 160cm", "sku": "DESK-SIT-160", "selling_price": Decimal("799.00"), "cost_price": Decimal("499.00"), "category": "Furniture", "reorder_level": 4, "min_stock": 2},
            {"name": "USB-C Hub 7-in-1", "sku": "USB-C-HUB-7", "selling_price": Decimal("49.99"), "cost_price": Decimal("24.99"), "category": "Electronics", "reorder_level": 15, "min_stock": 8},
        ]
        products = {}
        for pd in products_data:
            r = await db.execute(select(Product).where(Product.sku == pd["sku"]))
            p = r.scalar_one_or_none()
            if not p:
                p = Product(
                    id=uuid.uuid4(),
                    name=pd["name"],
                    sku=pd["sku"],
                    selling_price=pd["selling_price"],
                    cost_price=pd["cost_price"],
                    category_id=cats[pd["category"]].id,
                    reorder_level=pd["reorder_level"],
                    min_stock=pd["min_stock"],
                    is_active=True,
                    serial_tracking=False,
                    batch_tracking=False,
                )
                db.add(p)
                await db.flush()
            products[pd["sku"]] = p
        print("  Products ready")

        # ── Inventory ───────────────────────────────────────────────────────
        stock_data = [
            ("MBP-14-2024", "A1", 15),
            ("HM-AERON-B",  "A1", 8),
            ("LOG-MX3-BLK", "B2", 52),
            ("DESK-SIT-160","A1", 4),
            ("USB-C-HUB-7", "B2", 3),  # deliberately low for low-stock demo
        ]
        for sku, aisle, qty in stock_data:
            prod = products[sku]
            loc  = locs[aisle]
            r = await db.execute(select(Inventory).where(Inventory.product_id == prod.id, Inventory.location_id == loc.id))
            inv = r.scalar_one_or_none()
            if not inv:
                inv = Inventory(
                    id=uuid.uuid4(),
                    product_id=prod.id,
                    warehouse_id=loc.warehouse_id,
                    location_id=loc.id,
                    on_hand=Decimal(str(qty)),
                    reserved=Decimal("0"),
                )
                db.add(inv)
                await db.flush()

                # Create a seed ledger entry
                ledger = StockLedger(
                    id=uuid.uuid4(),
                    movement_type=MovementType.RECEIPT,
                    product_id=prod.id,
                    quantity=Decimal(str(qty)),
                    quantity_before=Decimal("0"),
                    quantity_after=Decimal(str(qty)),
                    destination_location_id=loc.id,
                    reference="SEED-INITIAL",
                    reason="Initial stock load",
                    idempotency_key=f"seed-{prod.id}-{loc.id}",
                )
                db.add(ledger)
                await db.flush()
        print("  ✅ Inventory + Ledger ready")

        # ── Notification ────────────────────────────────────────────────────
        admin = users.get("admin@stocksense.com")
        if admin:
            r = await db.execute(select(Notification).where(Notification.user_id == admin.id))
            if not r.scalar_one_or_none():
                notif = Notification(
                    id=uuid.uuid4(),
                    user_id=admin.id,
                    title="Low Stock Alert",
                    message="USB-C Hub 7-in-1 is below reorder point (3 units). Reorder now.",
                    notification_type=NotificationType.LOW_STOCK,
                    is_read=False,
                )
                db.add(notif)
                await db.flush()
        print("  ✅ Notification ready")

        await db.commit()
        print("\n🎉 Database seeded successfully!")


async def main():
    await create_tables()
    await seed_data()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
