import httpx
import os
from fastapi import HTTPException

USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://user-service:8001")
PRODUCT_SERVICE_URL = os.getenv("PRODUCT_SERVICE_URL", "http://product-service:8002")

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

async def get_product(product_id: str):
    """Get product information from Product Service"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{PRODUCT_SERVICE_URL}/api/products/{product_id}",
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

async def check_product_availability(product_id: str, quantity: int):
    """Check if product has sufficient inventory"""
    product = await get_product(product_id)
    if product["inventory"] < quantity:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient inventory. Available: {product['inventory']}, Requested: {quantity}"
        )
    return product

# Made with Bob
