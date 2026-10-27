import httpx
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class ServiceClient:
    """HTTP client for calling other microservices"""
    
    def __init__(self, product_service_url: str, order_service_url: str):
        self.product_service_url = product_service_url
        self.order_service_url = order_service_url
        self.timeout = 5.0
    
    async def search_products(self, query: str) -> List[Dict]:
        """Search products from Product Service"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.product_service_url}/api/products/search",
                    params={"q": query}
                )
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException:
            logger.error("Product service timeout")
            return []
        except httpx.HTTPError as e:
            logger.error(f"Error calling product service: {str(e)}")
            return []
    
    async def get_products(self, category: Optional[str] = None) -> List[Dict]:
        """Get products from Product Service"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                url = f"{self.product_service_url}/api/products"
                params = {}
                if category:
                    params["category"] = category
                
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException:
            logger.error("Product service timeout")
            return []
        except httpx.HTTPError as e:
            logger.error(f"Error calling product service: {str(e)}")
            return []
    
    async def get_product_by_id(self, product_id: str) -> Optional[Dict]:
        """Get product details by ID"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.product_service_url}/api/products/{product_id}"
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Error getting product: {str(e)}")
            return None
    
    async def get_user_orders(self, user_id: str) -> List[Dict]:
        """Get user's orders from Order Service"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.order_service_url}/api/orders/user/{user_id}"
                )
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException:
            logger.error("Order service timeout")
            return []
        except httpx.HTTPError as e:
            logger.error(f"Error calling order service: {str(e)}")
            return []
    
    async def get_order_by_id(self, order_id: str) -> Optional[Dict]:
        """Get order details by ID"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.order_service_url}/api/orders/{order_id}"
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Error getting order: {str(e)}")
            return None

# Made with Bob
