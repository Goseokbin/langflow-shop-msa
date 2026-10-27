from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from . import models, schemas
from .database import get_db
from .service_client import get_user, get_cart, clear_cart, update_product_inventory
from jose import JWTError, jwt
import os

router = APIRouter()

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

def get_user_id_from_token(authorization: Optional[str] = Header(None)) -> str:
    """Extract user_id from JWT token"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid authentication scheme")
        
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        return user_id
    except (ValueError, JWTError) as e:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_token_from_header(authorization: Optional[str] = Header(None)) -> str:
    """Extract JWT token from Authorization header"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid authentication scheme")
        return token
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid authorization header format")

@router.post("/orders", response_model=schemas.OrderResponse)
async def create_order(
    order_data: schemas.OrderCreate,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_user_id_from_token),
    token: str = Depends(get_token_from_header)
):
    """Create a new order from user's cart"""
    import httpx
    
    # Verify user exists
    user = await get_user(user_id)
    
    # Get cart items
    cart = await get_cart(token)
    
    if not cart.get("items") or len(cart["items"]) == 0:
        raise HTTPException(status_code=400, detail="Cart is empty")
    
    # Create order
    order = models.Order(
        user_id=user_id,
        total_amount=cart["total"],
        shipping_address=order_data.shipping_address,
        status=models.OrderStatus.PENDING
    )
    db.add(order)
    db.flush()
    
    # Create order items and update inventory
    order_items_details = []
    for cart_item in cart["items"]:
        order_item = models.OrderItem(
            order_id=order.id,
            product_id=cart_item["product_id"],
            quantity=cart_item["quantity"],
            price=cart_item["price"]
        )
        db.add(order_item)
        
        # Get product details for AI summary
        try:
            async with httpx.AsyncClient() as client:
                product_response = await client.get(
                    f"http://product-service:8002/api/products/{cart_item['product_id']}",
                    timeout=5.0
                )
                if product_response.status_code == 200:
                    product = product_response.json()
                    order_items_details.append({
                        "product_id": cart_item["product_id"],
                        "product_name": product.get("name", "Product"),
                        "quantity": cart_item["quantity"],
                        "price": cart_item["price"]
                    })
        except:
            order_items_details.append({
                "product_id": cart_item["product_id"],
                "product_name": "Product",
                "quantity": cart_item["quantity"],
                "price": cart_item["price"]
            })
        
        # Update product inventory (decrease)
        await update_product_inventory(
            cart_item["product_id"],
            -cart_item["quantity"]
        )
    
    # Generate AI summary
    try:
        print(f"🤖 Calling langflow-ai-service for order {order.id}")
        async with httpx.AsyncClient() as client:
            ai_response = await client.post(
                "http://langflow-ai-service:8005/api/chat/summarize-order",
                json={
                    "order_id": str(order.id),
                    "total_amount": float(order.total_amount),
                    "items": order_items_details,
                    "shipping_address": order.shipping_address
                },
                timeout=12.0  # AI 장애가 주문 확정을 오래 지연시키지 않도록 제한
            )
            print(f"📡 AI service response status: {ai_response.status_code}")
            if ai_response.status_code == 200:
                ai_data = ai_response.json()
                order.ai_summary = ai_data.get("summary", "")
                if order.ai_summary:
                    print(f"✅ AI summary generated: {order.ai_summary[:100]}...")
                else:
                    print(f"⚠️  AI service returned empty summary")
                    order.ai_summary = None
            else:
                print(f"❌ AI service returned non-200: {ai_response.text}")
                order.ai_summary = None
    except Exception as e:
        print(f"❌ Failed to generate AI summary: {e}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
        order.ai_summary = None
    
    db.commit()
    db.refresh(order)
    
    # Clear cart after successful order
    await clear_cart(token)
    
    return schemas.OrderResponse(
        id=order.id,
        user_id=order.user_id,
        total_amount=order.total_amount,
        status=order.status,
        shipping_address=order.shipping_address,
        ai_summary=order.ai_summary,
        items=[schemas.OrderItemResponse.from_orm(item) for item in order.items],
        created_at=order.created_at,
        updated_at=order.updated_at
    )

@router.get("/orders/{order_id}", response_model=schemas.OrderResponse)
async def get_order(order_id: str, db: Session = Depends(get_db)):
    """Get order details by ID"""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    return schemas.OrderResponse(
        id=order.id,
        user_id=order.user_id,
        total_amount=order.total_amount,
        status=order.status,
        shipping_address=order.shipping_address,
        items=[schemas.OrderItemResponse.from_orm(item) for item in order.items],
        created_at=order.created_at,
        updated_at=order.updated_at
    )

@router.get("/orders")
async def get_user_orders(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_user_id_from_token)
):
    """Get all orders for a user"""
    import httpx
    
    # Verify user exists
    await get_user(user_id)
    
    # Get orders
    orders = db.query(models.Order).filter(
        models.Order.user_id == user_id
    ).order_by(models.Order.created_at.desc()).all()
    
    result = []
    for order in orders:
        # Get order items separately
        order_items = db.query(models.OrderItem).filter(
            models.OrderItem.order_id == order.id
        ).all()
        
        items_list = []
        async with httpx.AsyncClient() as client:
            for item in order_items:
                # Fetch product details
                try:
                    product_response = await client.get(
                        f"http://product-service:8002/api/products/{item.product_id}",
                        timeout=5.0
                    )
                    if product_response.status_code == 200:
                        product = product_response.json()
                    else:
                        product = None
                except:
                    product = None
                
                items_list.append({
                    "id": str(item.id),
                    "order_id": str(item.order_id),
                    "product_id": str(item.product_id),
                    "quantity": item.quantity,
                    "price": item.price,
                    "product": product
                })
        
        result.append({
            "id": str(order.id),
            "user_id": str(order.user_id),
            "total_amount": order.total_amount,
            "status": order.status.value if hasattr(order.status, 'value') else str(order.status),
            "shipping_address": order.shipping_address,
            "ai_summary": order.ai_summary,
            "items": items_list,
            "created_at": order.created_at.isoformat(),
            "updated_at": order.updated_at.isoformat()
        })
    return result

@router.put("/orders/{order_id}/status", response_model=schemas.OrderResponse)
async def update_order_status(
    order_id: str,
    status_update: schemas.OrderStatusUpdate,
    db: Session = Depends(get_db)
):
    """Update order status"""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    order.status = status_update.status
    db.commit()
    db.refresh(order)
    
    return schemas.OrderResponse(
        id=order.id,
        user_id=order.user_id,
        total_amount=order.total_amount,
        status=order.status,
        shipping_address=order.shipping_address,
        items=[schemas.OrderItemResponse.from_orm(item) for item in order.items],
        created_at=order.created_at,
        updated_at=order.updated_at
    )

@router.post("/orders/{order_id}/cancel")
async def cancel_order(
    order_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_user_id_from_token)
):
    """Cancel an order and restore inventory"""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Verify order belongs to user
    if str(order.user_id) != str(user_id):
        raise HTTPException(status_code=403, detail="Not authorized to cancel this order")
    
    # Check if order can be cancelled
    if order.status in [models.OrderStatus.DELIVERED, models.OrderStatus.CANCELLED]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel order with status: {order.status.value}"
        )
    
    # Get order items to restore inventory
    order_items = db.query(models.OrderItem).filter(
        models.OrderItem.order_id == order.id
    ).all()
    
    # Restore inventory for each item
    for item in order_items:
        try:
            await update_product_inventory(
                str(item.product_id),
                item.quantity  # Add back to inventory
            )
        except Exception as e:
            # Log error but continue with cancellation
            print(f"Failed to restore inventory for product {item.product_id}: {e}")
    
    # Update order status
    order.status = models.OrderStatus.CANCELLED
    db.commit()
    db.refresh(order)
    
    return {
        "message": "Order cancelled successfully",
        "order_id": str(order.id),
        "status": order.status.value
    }

@router.delete("/orders/{order_id}")
async def delete_order(
    order_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_user_id_from_token)
):
    """Delete an order permanently and restore inventory"""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Verify order belongs to user
    if str(order.user_id) != str(user_id):
        raise HTTPException(status_code=403, detail="Not authorized to delete this order")
    
    # Get order items to restore inventory
    order_items = db.query(models.OrderItem).filter(
        models.OrderItem.order_id == order.id
    ).all()
    
    # Restore inventory for each item (only if order is not delivered)
    if order.status != models.OrderStatus.DELIVERED:
        for item in order_items:
            try:
                await update_product_inventory(
                    str(item.product_id),
                    item.quantity  # Add back to inventory
                )
            except Exception as e:
                # Log error but continue with deletion
                print(f"Failed to restore inventory for product {item.product_id}: {e}")
    
    # Delete order items first (foreign key constraint)
    for item in order_items:
        db.delete(item)
    
    # Delete the order
    db.delete(order)
    db.commit()
    
    return {
        "message": "Order deleted successfully",
        "order_id": str(order_id)
    }

# Made with Bob
