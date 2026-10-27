from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class ChatRequest(BaseModel):
    message: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    session_id: str
    intent: Optional[str] = None


class OrderItem(BaseModel):
    product_id: str
    product_name: str
    quantity: int
    price: float


class OrderSummaryRequest(BaseModel):
    order_id: str
    total_amount: float
    items: List[OrderItem]
    shipping_address: str


class OrderSummaryResponse(BaseModel):
    order_id: str
    summary: str

# Made with Bob
