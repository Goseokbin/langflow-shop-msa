from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class Product(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    price: float
    category: str
    inventory: int
    image_url: Optional[str] = None

class CartItemBase(BaseModel):
    product_id: str
    quantity: int
    price: float

class CartItemCreate(BaseModel):
    product_id: str
    quantity: int = 1

class CartItemUpdate(BaseModel):
    quantity: int

class CartItemResponse(CartItemBase):
    id: str
    cart_id: str
    product: Optional[Product] = None
    
    class Config:
        from_attributes = True

class CartBase(BaseModel):
    user_id: str

class CartResponse(BaseModel):
    id: str
    user_id: str
    items: List[CartItemResponse]
    total: float
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class CartSummary(BaseModel):
    item_count: int
    total: float

# Made with Bob
