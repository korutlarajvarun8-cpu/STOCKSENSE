from pydantic import BaseModel, Field
from typing import Optional, List
from decimal import Decimal
from datetime import datetime
import uuid


# ─── Category ────────────────────────────────────────────────────────────────

class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class CategoryResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    is_active: bool
    created_at: datetime
    product_count: Optional[int] = 0

    model_config = {"from_attributes": True}


# ─── Product ──────────────────────────────────────────────────────────────────

class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    sku: str = Field(..., min_length=1, max_length=100)
    barcode: Optional[str] = None
    description: Optional[str] = None
    brand: Optional[str] = None
    unit_of_measure: str = "unit"
    category_id: uuid.UUID
    cost_price: Optional[Decimal] = Decimal("0")
    selling_price: Optional[Decimal] = Decimal("0")
    reorder_level: Optional[Decimal] = Decimal("0")
    min_stock: Optional[Decimal] = Decimal("0")
    max_stock: Optional[Decimal] = Decimal("0")
    default_warehouse_id: Optional[uuid.UUID] = None
    default_location_id: Optional[uuid.UUID] = None
    image_url: Optional[str] = None
    batch_tracking: bool = False
    serial_tracking: bool = False
    expiry_tracking: bool = False


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    barcode: Optional[str] = None
    description: Optional[str] = None
    brand: Optional[str] = None
    unit_of_measure: Optional[str] = None
    category_id: Optional[uuid.UUID] = None
    cost_price: Optional[Decimal] = None
    selling_price: Optional[Decimal] = None
    reorder_level: Optional[Decimal] = None
    min_stock: Optional[Decimal] = None
    max_stock: Optional[Decimal] = None
    default_warehouse_id: Optional[uuid.UUID] = None
    default_location_id: Optional[uuid.UUID] = None
    image_url: Optional[str] = None
    is_active: Optional[bool] = None
    batch_tracking: Optional[bool] = None
    serial_tracking: Optional[bool] = None
    expiry_tracking: Optional[bool] = None


class CategoryBrief(BaseModel):
    id: uuid.UUID
    name: str
    model_config = {"from_attributes": True}


class ProductResponse(BaseModel):
    id: uuid.UUID
    name: str
    sku: str
    barcode: Optional[str] = None
    qr_code: Optional[str] = None
    description: Optional[str] = None
    brand: Optional[str] = None
    unit_of_measure: str
    category_id: uuid.UUID
    category: Optional[CategoryBrief] = None
    cost_price: Optional[Decimal] = None
    selling_price: Optional[Decimal] = None
    reorder_level: Optional[Decimal] = None
    min_stock: Optional[Decimal] = None
    max_stock: Optional[Decimal] = None
    image_url: Optional[str] = None
    is_active: bool
    batch_tracking: bool
    serial_tracking: bool
    expiry_tracking: bool
    on_hand: Optional[Decimal] = Decimal("0")
    reserved: Optional[Decimal] = Decimal("0")
    available: Optional[Decimal] = Decimal("0")
    created_at: datetime

    model_config = {"from_attributes": True}


class ProductListItem(BaseModel):
    id: uuid.UUID
    name: str
    sku: str
    barcode: Optional[str] = None
    unit_of_measure: str
    category: Optional[CategoryBrief] = None
    is_active: bool
    on_hand: Optional[Decimal] = Decimal("0")
    available: Optional[Decimal] = Decimal("0")
    reorder_level: Optional[Decimal] = None

    model_config = {"from_attributes": True}


class PaginatedProducts(BaseModel):
    items: List[ProductListItem]
    total: int
    page: int
    page_size: int
    pages: int
