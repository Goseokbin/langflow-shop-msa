from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import List, Optional
from . import models, schemas
from .database import get_db
from .service_client import get_user, check_product_availability, get_product
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

@router.get("/cart", response_model=schemas.CartResponse)
async def get_cart(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_user_id_from_token)
):
    """Get user's cart"""
    # Verify user exists
    await get_user(user_id)
    
    # Get or create cart
    cart = db.query(models.Cart).filter(models.Cart.user_id == user_id).first()
    if not cart:
        cart = models.Cart(user_id=user_id)
        db.add(cart)
        db.commit()
        db.refresh(cart)
    
    # Fetch product details for each item
    items_with_products = []
    for item in cart.items:
        try:
            product = await get_product(item.product_id)
            item_response = schemas.CartItemResponse(
                id=item.id,
                cart_id=item.cart_id,
                product_id=item.product_id,
                quantity=item.quantity,
                price=item.price,
                product=schemas.Product(**product)
            )
            items_with_products.append(item_response)
        except Exception as e:
            # If product fetch fails, include item without product details
            item_response = schemas.CartItemResponse(
                id=item.id,
                cart_id=item.cart_id,
                product_id=item.product_id,
                quantity=item.quantity,
                price=item.price,
                product=None
            )
            items_with_products.append(item_response)
    
    # Calculate total
    total = sum(item.price * item.quantity for item in cart.items)
    
    return schemas.CartResponse(
        id=cart.id,
        user_id=cart.user_id,
        items=items_with_products,
        total=total,
        created_at=cart.created_at,
        updated_at=cart.updated_at
    )

@router.post("/cart/items", response_model=schemas.CartResponse)
async def add_item_to_cart(
    item: schemas.CartItemCreate,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_user_id_from_token)
):
    """Add item to cart"""
    # Verify user exists
    await get_user(user_id)
    
    # Check product availability
    product = await check_product_availability(item.product_id, item.quantity)
    
    # Get or create cart
    cart = db.query(models.Cart).filter(models.Cart.user_id == user_id).first()
    if not cart:
        cart = models.Cart(user_id=user_id)
        db.add(cart)
        db.commit()
        db.refresh(cart)
    
    # Check if item already exists in cart
    existing_item = db.query(models.CartItem).filter(
        models.CartItem.cart_id == cart.id,
        models.CartItem.product_id == item.product_id
    ).first()
    
    if existing_item:
        # Update quantity
        new_quantity = existing_item.quantity + item.quantity
        await check_product_availability(item.product_id, new_quantity)
        existing_item.quantity = new_quantity
    else:
        # Add new item
        cart_item = models.CartItem(
            cart_id=cart.id,
            product_id=item.product_id,
            quantity=item.quantity,
            price=product["price"]
        )
        db.add(cart_item)
    
    db.commit()
    db.refresh(cart)
    
    # Calculate total
    total = sum(item.price * item.quantity for item in cart.items)
    
    return schemas.CartResponse(
        id=cart.id,
        user_id=cart.user_id,
        items=[schemas.CartItemResponse.from_orm(item) for item in cart.items],
        total=total,
        created_at=cart.created_at,
        updated_at=cart.updated_at
    )

@router.put("/cart/items/{item_id}", response_model=schemas.CartResponse)
async def update_cart_item(
    item_id: str,
    item_update: schemas.CartItemUpdate,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_user_id_from_token)
):
    """Update cart item quantity"""
    # Verify user exists
    await get_user(user_id)
    
    # Get cart
    cart = db.query(models.Cart).filter(models.Cart.user_id == user_id).first()
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")
    
    # Get cart item
    cart_item = db.query(models.CartItem).filter(
        models.CartItem.id == item_id,
        models.CartItem.cart_id == cart.id
    ).first()
    
    if not cart_item:
        raise HTTPException(status_code=404, detail="Cart item not found")
    
    # Check product availability
    await check_product_availability(cart_item.product_id, item_update.quantity)
    
    # Update quantity
    cart_item.quantity = item_update.quantity
    db.commit()
    db.refresh(cart)
    
    # Calculate total
    total = sum(item.price * item.quantity for item in cart.items)
    
    return schemas.CartResponse(
        id=cart.id,
        user_id=cart.user_id,
        items=[schemas.CartItemResponse.from_orm(item) for item in cart.items],
        total=total,
        created_at=cart.created_at,
        updated_at=cart.updated_at
    )

@router.delete("/cart/items/{item_id}")
async def remove_cart_item(
    item_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_user_id_from_token)
):
    """Remove item from cart"""
    # Verify user exists
    await get_user(user_id)
    
    # Get cart
    cart = db.query(models.Cart).filter(models.Cart.user_id == user_id).first()
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")
    
    # Get and delete cart item
    cart_item = db.query(models.CartItem).filter(
        models.CartItem.id == item_id,
        models.CartItem.cart_id == cart.id
    ).first()
    
    if not cart_item:
        raise HTTPException(status_code=404, detail="Cart item not found")
    
    db.delete(cart_item)
    db.commit()
    
    return {"message": "Item removed from cart"}

@router.delete("/cart/clear")
async def clear_cart(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_user_id_from_token)
):
    """Clear all items from cart"""
    # Verify user exists
    await get_user(user_id)
    
    # Get cart
    cart = db.query(models.Cart).filter(models.Cart.user_id == user_id).first()
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")
    
    # Delete all items
    db.query(models.CartItem).filter(models.CartItem.cart_id == cart.id).delete()
    db.commit()
    
    return {"message": "Cart cleared"}

# Made with Bob
