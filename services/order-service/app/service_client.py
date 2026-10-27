import httpx
import os
from fastapi import HTTPException

USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://user-service:8001")
PRODUCT_SERVICE_URL = os.getenv("PRODUCT_SERVICE_URL", "http://product-service:8002")
CART_SERVICE_URL = os.getenv("CART_SERVICE_URL", "http://cart-service:8003")

async def get_user(user_id: str):
    """Get user information from User Service"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{USER_SERVICE_URL}/api/users/{user_id}",
                timeout=5.0
            )
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail="User not found")
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="User service timeout")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail=f"User service unavailable: {str(e)}")

async def get_cart(token: str):
    """Get user's cart from Cart Service"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{CART_SERVICE_URL}/api/cart",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5.0
            )
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail="Cart not found")
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Cart service timeout")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail=f"Cart service unavailable: {str(e)}")

async def clear_cart(token: str):
    """Clear user's cart after order creation"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{CART_SERVICE_URL}/api/cart/clear",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5.0
            )
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Cart service timeout")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail=f"Cart service unavailable: {str(e)}")

async def update_product_inventory(product_id: str, quantity_change: int):
    """Update product inventory in Product Service"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{PRODUCT_SERVICE_URL}/api/products/{product_id}/inventory",
                json={"quantity_change": quantity_change},
                timeout=5.0
            )
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail="Product not found")
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Product service timeout")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail=f"Product service unavailable: {str(e)}")

# Made with Bob
