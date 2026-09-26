import math
from typing import Optional, List
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, delete, and_
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.models.user import User, UserRole
from app.models.product import Product, Category
from app.models.inventory import Inventory
from app.schemas.product import (
    ProductCreate, ProductUpdate, ProductResponse, ProductListItem,
    PaginatedProducts, CategoryCreate, CategoryUpdate, CategoryResponse
)

router = APIRouter(prefix="/products", tags=["Products"])


# ─── Categories ───────────────────────────────────────────────────────────────

@router.get("/categories", response_model=List[CategoryResponse])
async def list_categories(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Category, func.count(Product.id).label("product_count"))
        .outerjoin(Product, and_(Product.category_id == Category.id, Product.is_active == True))
        .group_by(Category.id)
        .order_by(Category.name)
    )
    rows = result.all()
    categories = []
    for cat, count in rows:
        resp = CategoryResponse.model_validate(cat)
        resp.product_count = count
        categories.append(resp)
    return categories


@router.post("/categories", response_model=CategoryResponse, status_code=201)
async def create_category(
    body: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.INVENTORY_MANAGER)),
):
    cat = Category(**body.model_dump())
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return cat


@router.put("/categories/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: uuid.UUID,
    body: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.INVENTORY_MANAGER)),
):
    result = await db.execute(select(Category).where(Category.id == category_id))
    cat = result.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found.")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(cat, k, v)
    await db.commit()
    await db.refresh(cat)
    return cat


@router.delete("/categories/{category_id}", status_code=204)
async def delete_category(
    category_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.INVENTORY_MANAGER)),
):
    result = await db.execute(
        select(func.count(Product.id)).where(Product.category_id == category_id, Product.is_active == True)
    )
    count = result.scalar()
    if count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete category. {count} active product(s) belong to it. Please reassign them first.",
        )
    await db.execute(delete(Category).where(Category.id == category_id))
    await db.commit()


# ─── Products ─────────────────────────────────────────────────────────────────

@router.get("", response_model=PaginatedProducts)
async def list_products(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    category_id: Optional[uuid.UUID] = Query(None),
    is_active: Optional[bool] = Query(None),
    low_stock: bool = Query(False),
):
    query = (
        select(Product)
        .options(selectinload(Product.category))
        .where(Product.is_active == True if is_active is None else Product.is_active == is_active)
    )

    if search:
        query = query.where(
            Product.name.ilike(f"%{search}%") |
            Product.sku.ilike(f"%{search}%") |
            Product.barcode.ilike(f"%{search}%")
        )
    if category_id:
        query = query.where(Product.category_id == category_id)

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar()

    offset = (page - 1) * page_size
    result = await db.execute(query.offset(offset).limit(page_size).order_by(Product.name))
    products = result.scalars().all()

    # Fetch inventory summaries
    product_ids = [p.id for p in products]
    inv_result = await db.execute(
        select(
            Inventory.product_id,
            func.sum(Inventory.on_hand).label("on_hand"),
            func.sum(Inventory.reserved).label("reserved"),
        )
        .where(Inventory.product_id.in_(product_ids))
        .group_by(Inventory.product_id)
    )
    inv_map = {row.product_id: row for row in inv_result.all()}

    items = []
    for p in products:
        inv = inv_map.get(p.id)
        on_hand = inv.on_hand if inv else 0
        reserved = inv.reserved if inv else 0
        available = on_hand - reserved

        if low_stock and p.reorder_level and available > p.reorder_level:
            continue

        item = ProductListItem(
            id=p.id,
            name=p.name,
            sku=p.sku,
            barcode=p.barcode,
            unit_of_measure=p.unit_of_measure,
            category=p.category,
            is_active=p.is_active,
            on_hand=on_hand,
            available=available,
            reorder_level=p.reorder_level,
        )
        items.append(item)

    return PaginatedProducts(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 1,
    )


@router.post("", response_model=ProductResponse, status_code=201)
async def create_product(
    body: ProductCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.INVENTORY_MANAGER)),
):
    # SKU uniqueness check
    result = await db.execute(select(Product).where(Product.sku == body.sku))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"SKU '{body.sku}' already exists.")

    # Barcode uniqueness check
    if body.barcode:
        result = await db.execute(select(Product).where(Product.barcode == body.barcode))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail=f"Barcode '{body.barcode}' already exists.")

    product = Product(**body.model_dump())
    db.add(product)
    await db.commit()
    await db.refresh(product)

    result = await db.execute(
        select(Product).options(selectinload(Product.category)).where(Product.id == product.id)
    )
    product = result.scalar_one()
    resp = ProductResponse.model_validate(product)
    return resp


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Product)
        .options(selectinload(Product.category))
        .where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")

    # Aggregate inventory
    inv_result = await db.execute(
        select(
            func.sum(Inventory.on_hand).label("on_hand"),
            func.sum(Inventory.reserved).label("reserved"),
        ).where(Inventory.product_id == product_id)
    )
    inv = inv_result.one()
    on_hand = inv.on_hand or 0
    reserved = inv.reserved or 0

    resp = ProductResponse.model_validate(product)
    resp.on_hand = on_hand
    resp.reserved = reserved
    resp.available = on_hand - reserved
    return resp


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: uuid.UUID,
    body: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.INVENTORY_MANAGER)),
):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")

    if body.barcode and body.barcode != product.barcode:
        existing = await db.execute(
            select(Product).where(Product.barcode == body.barcode, Product.id != product_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Barcode already in use.")

    for k, v in body.model_dump(exclude_none=True).items():
        setattr(product, k, v)

    await db.commit()
    await db.refresh(product)
    return await get_product(product_id, db)


@router.delete("/{product_id}", status_code=204)
async def delete_product(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    # Soft delete
    await db.execute(
        update(Product).where(Product.id == product_id).values(is_active=False)
    )
    await db.commit()


@router.get("/barcode/{barcode}", response_model=ProductResponse)
async def get_product_by_barcode(
    barcode: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Product)
        .options(selectinload(Product.category))
        .where(Product.barcode == barcode)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail=f"No product found with barcode '{barcode}'.")
    return await get_product(product.id, db)
