"""
Backfill AI summaries for existing orders
"""
import os
import sys
import asyncio
import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Order, OrderItem

# Database connection
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://orderuser:orderpass@order-db:5432/order_db')
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

LANGFLOW_AI_SERVICE_URL = os.getenv('LANGFLOW_AI_SERVICE_URL', 'http://langflow-ai-service:8005')

async def generate_ai_summary(order_data: dict) -> str:
    """Call langflow-ai-service to generate order summary"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{LANGFLOW_AI_SERVICE_URL}/api/chat/summarize-order",
                json=order_data,
                timeout=30.0
            )
            if response.status_code == 200:
                result = response.json()
                return result.get('summary', '')
            else:
                print(f"  ❌ Failed to generate AI summary: {response.status_code}")
                return None
    except Exception as e:
        print(f"  ❌ Error calling langflow-ai-service: {str(e)}")
        return None

async def backfill_summaries():
    """Backfill AI summaries for orders that don't have them"""
    db = SessionLocal()
    try:
        # Find orders without AI summaries
        orders = db.query(Order).filter(
            (Order.ai_summary == None) | (Order.ai_summary == '')
        ).all()
        
        print(f"📊 Found {len(orders)} orders without AI summaries")
        
        for i, order in enumerate(orders, 1):
            print(f"\n[{i}/{len(orders)}] Processing order {order.id[:8]}...")
            
            # Get order items
            items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
            
            # Prepare order data for AI summary
            items_data = []
            for item in items:
                items_data.append({
                    "product_id": str(item.product_id),
                    "product_name": f"Product {item.product_id[:8]}",  # We don't have product names here
                    "quantity": item.quantity,
                    "price": float(item.price)
                })
            
            order_data = {
                "order_id": str(order.id),
                "items": items_data,
                "total_amount": float(order.total_amount),
                "shipping_address": order.shipping_address
            }
            
            # Generate AI summary
            ai_summary = await generate_ai_summary(order_data)
            
            if ai_summary:
                order.ai_summary = ai_summary
                db.commit()
                print(f"  ✅ AI summary added: {ai_summary[:50]}...")
            else:
                print(f"  ⚠️  Skipped (failed to generate summary)")
        
        print(f"\n🎉 Backfill complete! Updated {len(orders)} orders")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(backfill_summaries())

# Made with Bob
