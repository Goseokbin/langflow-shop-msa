from fastapi import APIRouter, Depends
from typing import Dict, List
import uuid
import os

from .schemas import ChatRequest, ChatResponse, OrderSummaryRequest, OrderSummaryResponse
from .chatbot import ShoppingAssistant
from .service_client import ServiceClient

router = APIRouter()

# Initialize services
PRODUCT_SERVICE_URL = os.getenv("PRODUCT_SERVICE_URL", "http://product-service:8002")
ORDER_SERVICE_URL = os.getenv("ORDER_SERVICE_URL", "http://order-service:8004")

service_client = ServiceClient(PRODUCT_SERVICE_URL, ORDER_SERVICE_URL)
assistant = ShoppingAssistant()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Chat with AI assistant
    
    The assistant can help with:
    - Product search and recommendations
    - Order status inquiries
    - General shopping questions
    """
    # Generate session ID if not provided
    session_id = request.session_id or str(uuid.uuid4())
    
    # Analyze user intent
    intent_data = await assistant.analyze_intent(request.message)
    intent = intent_data.get("intent", "general_question")
    
    # Fetch context based on intent
    context: Dict = {}
    
    if intent == "product_search":
        # Search for products
        products = await service_client.search_products(request.message)
        context["products"] = products
    
    elif intent == "order_status" and request.user_id:
        # Get user's orders
        orders = await service_client.get_user_orders(request.user_id)
        context["orders"] = orders
    
    elif intent == "recommendation":
        # Get some products for recommendation
        products = await service_client.get_products()
        context["products"] = products[:10]  # Limit to 10
    
    # Generate response with context
    response_text = await assistant.chat(request.message, context)
    
    return ChatResponse(
        response=response_text,
        session_id=session_id,
        intent=intent
    )


@router.get("/chat/history/{session_id}")
async def get_chat_history(session_id: str):
    """Get chat history for a session (placeholder)"""
    # In a real implementation, this would fetch from a database or cache
    return {
        "session_id": session_id,
        "messages": [],
        "note": "Chat history feature not yet implemented"
    }


@router.post("/chat/summarize-order", response_model=OrderSummaryResponse)
async def summarize_order(request: OrderSummaryRequest):
    """
    Generate a natural language summary of an order
    
    Takes order details and generates a friendly, conversational summary
    """
    try:
        print(f"🔍 Received order summary request: {request.dict()}")
        
        # Convert OrderItem objects to dicts
        items_dict = [item.dict() for item in request.items]
        
        # Generate order summary using AI
        summary = await assistant.generate_order_summary(
            order_id=request.order_id,
            total_amount=request.total_amount,
            items=items_dict,
            shipping_address=request.shipping_address
        )
        
        print(f"✅ Generated summary for order {request.order_id}")
        
        return OrderSummaryResponse(
            order_id=request.order_id,
            summary=summary
        )
    except Exception as e:
        print(f"❌ Error in summarize_order: {str(e)}")
        print(f"❌ Error type: {type(e).__name__}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
        raise

# Made with Bob
