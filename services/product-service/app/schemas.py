from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID
from decimal import Decimal


class ProductBase(BaseModel):
    name: str
    description: Optional[str] = None
    price: Decimal = Field(..., gt=0)
    category: str
    inventory: int = Field(default=0, ge=0)
    image_url: Optional[str] = None
    detailed_description: Optional[str] = None
    specifications: Optional[str] = None
    brand: Optional[str] = None
    rating: Optional[Decimal] = Field(default=Decimal('0.0'), ge=0, le=5)
    review_count: Optional[int] = Field(default=0, ge=0)


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[Decimal] = Field(None, gt=0)
    category: Optional[str] = None
    inventory: Optional[int] = Field(None, ge=0)
    image_url: Optional[str] = None
    detailed_description: Optional[str] = None
    specifications: Optional[str] = None
    brand: Optional[str] = None
    rating: Optional[Decimal] = Field(None, ge=0, le=5)
    review_count: Optional[int] = Field(None, ge=0)


class ProductResponse(ProductBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class InventoryUpdate(BaseModel):
    quantity_change: int  # Positive to add, negative to subtract

# Made with Bob
