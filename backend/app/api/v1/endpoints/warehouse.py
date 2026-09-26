import math
import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, delete
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.models.user import User, UserRole
from app.models.warehouse import Warehouse, Location, LocationType
from app.models.stakeholder import Supplier, Customer

router = APIRouter(tags=["Warehouse & Stakeholders"])


# ─── Warehouse Schemas ────────────────────────────────────────────────────────

class WarehouseCreate(BaseModel):
    name: str
    code: str
    address: Optional[str] = None
    manager_id: Optional[uuid.UUID] = None


class WarehouseUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    manager_id: Optional[uuid.UUID] = None
    is_active: Optional[bool] = None


class WarehouseResponse(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    address: Optional[str] = None
    manager_id: Optional[uuid.UUID] = None
    is_active: bool
    model_config = {"from_attributes": True}


class LocationCreate(BaseModel):
    name: str
    code: str
    warehouse_id: uuid.UUID
    parent_id: Optional[uuid.UUID] = None
    location_type: LocationType = LocationType.STORAGE
    barcode: Optional[str] = None


class LocationUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[uuid.UUID] = None
    location_type: Optional[LocationType] = None
    is_active: Optional[bool] = None


class LocationResponse(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    warehouse_id: uuid.UUID
    parent_id: Optional[uuid.UUID] = None
    location_type: LocationType
    is_active: bool
    barcode: Optional[str] = None
    model_config = {"from_attributes": True}


# ─── Supplier/Customer Schemas ────────────────────────────────────────────────

class SupplierCreate(BaseModel):
    name: str
    contact_person: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    tax_id: Optional[str] = None
    notes: Optional[str] = None


class SupplierResponse(BaseModel):
    id: uuid.UUID
    name: str
    contact_person: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    tax_id: Optional[str] = None
    notes: Optional[str] = None
    is_active: bool
    model_config = {"from_attributes": True}


class CustomerCreate(BaseModel):
    name: str
    contact_person: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None


class CustomerResponse(BaseModel):
    id: uuid.UUID
    name: str
    contact_person: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None
    is_active: bool
    model_config = {"from_attributes": True}


# ─── Warehouse Endpoints ──────────────────────────────────────────────────────

wh_router = APIRouter(prefix="/warehouses", tags=["Warehouses"])


@wh_router.get("", response_model=List[WarehouseResponse])
async def list_warehouses(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
    include_inactive: bool = False,
):
    q = select(Warehouse)
    if not include_inactive:
        q = q.where(Warehouse.is_active == True)
    result = await db.execute(q.order_by(Warehouse.name))
    return result.scalars().all()


@wh_router.post("", response_model=WarehouseResponse, status_code=201)
async def create_warehouse(
    body: WarehouseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.INVENTORY_MANAGER)),
):
    existing = await db.execute(select(Warehouse).where(Warehouse.code == body.code))
    if existing.scalar_one_or_none():
        raise HTTPException(400, f"Warehouse code '{body.code}' already exists.")
    wh = Warehouse(**body.model_dump())
    db.add(wh)
    await db.commit()
    await db.refresh(wh)
    return wh


@wh_router.get("/{warehouse_id}", response_model=WarehouseResponse)
async def get_warehouse(
    warehouse_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Warehouse).where(Warehouse.id == warehouse_id))
    wh = result.scalar_one_or_none()
    if not wh:
        raise HTTPException(404, "Warehouse not found.")
    return wh


@wh_router.put("/{warehouse_id}", response_model=WarehouseResponse)
async def update_warehouse(
    warehouse_id: uuid.UUID,
    body: WarehouseUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.INVENTORY_MANAGER)),
):
    result = await db.execute(select(Warehouse).where(Warehouse.id == warehouse_id))
    wh = result.scalar_one_or_none()
    if not wh:
        raise HTTPException(404, "Warehouse not found.")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(wh, k, v)
    await db.commit()
    await db.refresh(wh)
    return wh


# ─── Location Endpoints ───────────────────────────────────────────────────────

loc_router = APIRouter(prefix="/locations", tags=["Locations"])


@loc_router.get("", response_model=List[LocationResponse])
async def list_locations(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
    warehouse_id: Optional[uuid.UUID] = Query(None),
):
    q = select(Location).where(Location.is_active == True)
    if warehouse_id:
        q = q.where(Location.warehouse_id == warehouse_id)
    result = await db.execute(q.order_by(Location.name))
    return result.scalars().all()


@loc_router.post("", response_model=LocationResponse, status_code=201)
async def create_location(
    body: LocationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.INVENTORY_MANAGER)),
):
    loc = Location(**body.model_dump())
    db.add(loc)
    await db.commit()
    await db.refresh(loc)
    return loc


@loc_router.put("/{location_id}", response_model=LocationResponse)
async def update_location(
    location_id: uuid.UUID,
    body: LocationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.INVENTORY_MANAGER)),
):
    result = await db.execute(select(Location).where(Location.id == location_id))
    loc = result.scalar_one_or_none()
    if not loc:
        raise HTTPException(404, "Location not found.")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(loc, k, v)
    await db.commit()
    await db.refresh(loc)
    return loc


# ─── Supplier Endpoints ───────────────────────────────────────────────────────

sup_router = APIRouter(prefix="/suppliers", tags=["Suppliers"])


@sup_router.get("", response_model=List[SupplierResponse])
async def list_suppliers(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
    search: Optional[str] = Query(None),
):
    q = select(Supplier).where(Supplier.is_active == True)
    if search:
        q = q.where(Supplier.name.ilike(f"%{search}%"))
    result = await db.execute(q.order_by(Supplier.name))
    return result.scalars().all()


@sup_router.post("", response_model=SupplierResponse, status_code=201)
async def create_supplier(
    body: SupplierCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.INVENTORY_MANAGER)),
):
    s = Supplier(**body.model_dump())
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return s


@sup_router.get("/{supplier_id}", response_model=SupplierResponse)
async def get_supplier(
    supplier_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(404, "Supplier not found.")
    return s


@sup_router.put("/{supplier_id}", response_model=SupplierResponse)
async def update_supplier(
    supplier_id: uuid.UUID,
    body: SupplierCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.INVENTORY_MANAGER)),
):
    result = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(404, "Supplier not found.")
    for k, v in body.model_dump().items():
        setattr(s, k, v)
    await db.commit()
    await db.refresh(s)
    return s


# ─── Customer Endpoints ───────────────────────────────────────────────────────

cust_router = APIRouter(prefix="/customers", tags=["Customers"])


@cust_router.get("", response_model=List[CustomerResponse])
async def list_customers(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
    search: Optional[str] = Query(None),
):
    q = select(Customer).where(Customer.is_active == True)
    if search:
        q = q.where(Customer.name.ilike(f"%{search}%"))
    result = await db.execute(q.order_by(Customer.name))
    return result.scalars().all()


@cust_router.post("", response_model=CustomerResponse, status_code=201)
async def create_customer(
    body: CustomerCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.INVENTORY_MANAGER)),
):
    c = Customer(**body.model_dump())
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


@cust_router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(404, "Customer not found.")
    return c
