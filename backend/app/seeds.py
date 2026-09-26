import asyncio
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.user import User, UserRole
from app.models.product import Product, Category
from app.models.warehouse import Warehouse, Location, LocationType
from app.models.stakeholder import Supplier, Customer
from app.models.inventory import Inventory, StockLedger, MovementType
from app.models.tracking import Batch, SerialNumber, SerialStatus, ReorderRule
from app.models.system import Notification, NotificationType, NotificationSeverity
from app.core.security import get_password_hash


async def create_demo_users(db: AsyncSession):
    users_to_create = [
        {"email": "admin@stocksense.com", "full_name": "Admin User", "role": UserRole.ADMIN},
        {"email": "manager@stocksense.com", "full_name": "Inventory Manager", "role": UserRole.INVENTORY_MANAGER},
        {"email": "staff@stocksense.com", "full_name": "Warehouse Staff", "role": UserRole.WAREHOUSE_STAFF},
        {"email": "viewer@stocksense.com", "full_name": "Viewer", "role": UserRole.VIEWER},
    ]
    
    users = {}
    for u in users_to_create:
        result = await db.execute(select(User).where(User.email == u["email"]))
        user = result.scalar_one_or_none()
        if not user:
            user = User(
                full_name=u["full_name"],
                email=u["email"],
                hashed_password=get_password_hash("password123"),
                role=u["role"],
                is_active=True,
                is_email_verified=True,
            )
            db.add(user)
            await db.flush()
            print(f"Created user: {u['email']} / password123")
        users[u["email"]] = user
    return users


async def create_demo_data(db: AsyncSession, admin_user: User):
    # 1. Warehouses and Locations
    wh_result = await db.execute(select(Warehouse))
    if wh_result.scalars().first():
        print("Demo data already exists.")
        return

    main_wh = Warehouse(name="Main Distribution Center", code="MDC", address="100 Logistics Way", is_active=True)
    store_wh = Warehouse(name="Downtown Retail Store", code="RET-01", address="500 High Street", is_active=True)
    db.add_all([main_wh, store_wh])
    await db.flush()

    loc_recv = Location(warehouse_id=main_wh.id, name="Receiving Dock", code="MDC-RECV", location_type=LocationType.RECEIVING)
    loc_storage = Location(warehouse_id=main_wh.id, name="Aisle 1, Rack A", code="MDC-A1-RA", location_type=LocationType.INTERNAL)
    loc_storefront = Location(warehouse_id=store_wh.id, name="Storefront Display", code="RET-DISP", location_type=LocationType.INTERNAL)
    db.add_all([loc_recv, loc_storage, loc_storefront])
    await db.flush()

    # 2. Categories
    cat_elec = Category(name="Electronics", description="Consumer electronics and gadgets")
    cat_fur = Category(name="Furniture", description="Office and home furniture")
    db.add_all([cat_elec, cat_fur])
    await db.flush()

    # 3. Products
    prod1 = Product(name="MacBook Pro 16-inch", sku="APP-MBP-16", description="Apple M3 Max", unit_of_measure="pcs", category_id=cat_elec.id, cost_price=2499.00, sale_price=2999.00, reorder_level=10)
    prod2 = Product(name="Herman Miller Aeron", sku="FUR-HMA-01", description="Ergonomic office chair", unit_of_measure="pcs", category_id=cat_fur.id, cost_price=650.00, sale_price=1050.00, reorder_level=5)
    prod3 = Product(name="Wireless Mouse", sku="ACC-WM-01", description="Bluetooth ergonomic mouse", unit_of_measure="pcs", category_id=cat_elec.id, cost_price=15.00, sale_price=45.00, reorder_level=50)
    db.add_all([prod1, prod2, prod3])
    await db.flush()

    # 4. Suppliers & Customers
    sup1 = Supplier(name="TechDistributors Inc.", contact_name="John Doe", email="john@techdist.com")
    cust1 = Customer(name="Acme Corp", contact_name="Jane Smith", email="jane@acmecorp.com")
    db.add_all([sup1, cust1])
    await db.flush()

    # 5. Inventory & Ledger (Simulate historical receipts)
    inv1 = Inventory(product_id=prod1.id, warehouse_id=main_wh.id, location_id=loc_storage.id, on_hand=15, reserved=0)
    inv2 = Inventory(product_id=prod2.id, warehouse_id=main_wh.id, location_id=loc_storage.id, on_hand=3, reserved=0)  # Low stock!
    inv3 = Inventory(product_id=prod3.id, warehouse_id=main_wh.id, location_id=loc_storage.id, on_hand=150, reserved=0)
    db.add_all([inv1, inv2, inv3])

    # Simulate ledgers for movement chart
    now = datetime.now(timezone.utc)
    for i in range(5):
        day = now - timedelta(days=i*2)
        db.add(StockLedger(product_id=prod1.id, movement_type=MovementType.RECEIPT, quantity=10, quantity_before=0, quantity_after=10, reference=f"REC-00{i}", user_id=admin_user.id, created_at=day))
        db.add(StockLedger(product_id=prod3.id, movement_type=MovementType.DELIVERY, quantity=-20, quantity_before=20, quantity_after=0, reference=f"DEL-00{i}", user_id=admin_user.id, created_at=day))

    # 6. Advanced Tracking: Batches and Serials
    batch = Batch(batch_number="B-2026-XYZ", product_id=prod1.id, supplier_id=sup1.id, quantity=10, expiry_date=now.date() + timedelta(days=365))
    db.add(batch)
    await db.flush()

    for sn in ["SN10001", "SN10002", "SN10003"]:
        db.add(SerialNumber(serial=sn, product_id=prod1.id, location_id=loc_storage.id, batch_id=batch.id, status=SerialStatus.AVAILABLE))

    # 7. Reorder Rules
    db.add(ReorderRule(product_id=prod1.id, warehouse_id=main_wh.id, min_quantity=10, max_quantity=50, reorder_quantity=20))
    db.add(ReorderRule(product_id=prod2.id, warehouse_id=main_wh.id, min_quantity=5, max_quantity=20, reorder_quantity=10))

    # 8. Notifications
    db.add(Notification(user_id=admin_user.id, title="Low Stock Alert", message=f"Product {prod2.name} is below reorder level.", notification_type=NotificationType.LOW_STOCK, severity=NotificationSeverity.WARNING))
    
    await db.commit()
    print("Rich demo data created successfully.")


async def main():
    print("Seeding database...")
    async with AsyncSessionLocal() as db:
        users = await create_demo_users(db)
        await create_demo_data(db, users["admin@stocksense.com"])
    print("Database seeded.")


if __name__ == "__main__":
    asyncio.run(main())
