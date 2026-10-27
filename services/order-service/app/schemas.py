from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from .models import OrderStatus

class OrderItemBase(BaseModel):
    product_id: str
    quantity: int
    price: float

class OrderItemResponse(OrderItemBase):
    id: str
    order_id: str
    
    class Config:
        from_attributes = True

class OrderCreate(BaseModel):
    shipping_address: str

class OrderStatusUpdate(BaseModel):
    status: OrderStatus

class OrderResponse(BaseModel):
    id: str
    user_id: str
    total_amount: float
    status: OrderStatus
    shipping_address: str
    ai_summary: Optional[str] = None
    items: List[OrderItemResponse]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class OrderSummary(BaseModel):
    id: str
    user_id: str
    total_amount: float
    status: OrderStatus
    created_at: datetime
    
    class Config:
        from_attributes = True

# Made with Bob
