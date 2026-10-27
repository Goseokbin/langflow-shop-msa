from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import Response
import httpx
import os

router = APIRouter()

# Service URLs
USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://user-service:8001")
PRODUCT_SERVICE_URL = os.getenv("PRODUCT_SERVICE_URL", "http://product-service:8002")
CART_SERVICE_URL = os.getenv("CART_SERVICE_URL", "http://cart-service:8003")
ORDER_SERVICE_URL = os.getenv("ORDER_SERVICE_URL", "http://order-service:8004")
AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://langflow-ai-service:8005")

async def proxy_request(service_url: str, request: Request, target_path: str | None = None):
    """Proxy request to a microservice"""
    # Use provided target_path or extract from request
    if target_path is None:
        path = request.url.path
    else:
        path = target_path
    
    # Build target URL
    target_url = f"{service_url}{path}"
    
    # Get query parameters
    query_params = dict(request.query_params)
    
    # Get headers (exclude host header)
    headers = dict(request.headers)
    headers.pop("host", None)
    
    # Get request body
    body = await request.body()
    
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.request(
                method=request.method,
                url=target_url,
                params=query_params,
                headers=headers,
                content=body,
                timeout=120.0
            )
            return response
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Service timeout")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail=f"Service unavailable: {str(e)}")

# Auth routes (with /api prefix)
@router.api_route("/api/auth/{path:path}", methods=["GET", "POST"])
async def auth_service_proxy_api(request: Request, path: str):
    target_path = f"/api/users/{path}"
    response = await proxy_request(USER_SERVICE_URL, request, target_path)
    return Response(content=response.content, status_code=response.status_code, media_type=response.headers.get("content-type", "application/json"))

# User Service routes (with /api prefix)
@router.api_route("/api/users/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def user_service_proxy_api(request: Request):
    response = await proxy_request(USER_SERVICE_URL, request)
    try:
        return Response(content=response.content, status_code=response.status_code, media_type=response.headers.get("content-type", "application/json"))
    except Exception as e:
        raise HTTPException(status_code=response.status_code, detail=response.text)

# User Service routes (without /api prefix for frontend)
@router.api_route("/users/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def user_service_proxy(path: str, request: Request):
    target_path = f"/api/users/{path}"
    response = await proxy_request(USER_SERVICE_URL, request, target_path)
    try:
        return Response(content=response.content, status_code=response.status_code, media_type=response.headers.get("content-type", "application/json"))
    except:
        return {"detail": response.text}

# Product Service routes (with /api prefix)
@router.api_route("/api/products/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def product_service_proxy_api(request: Request):
    response = await proxy_request(PRODUCT_SERVICE_URL, request)
    return Response(content=response.content, status_code=response.status_code, media_type=response.headers.get("content-type", "application/json"))

@router.api_route("/api/products", methods=["GET", "POST"])
async def product_list_proxy_api(request: Request):
    response = await proxy_request(PRODUCT_SERVICE_URL, request)
    return Response(content=response.content, status_code=response.status_code, media_type=response.headers.get("content-type", "application/json"))

# Product Service routes (without /api prefix for frontend)
@router.api_route("/products/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def product_service_proxy(path: str, request: Request):
    target_path = f"/api/products/{path}"
    response = await proxy_request(PRODUCT_SERVICE_URL, request, target_path)
    return Response(content=response.content, status_code=response.status_code, media_type=response.headers.get("content-type", "application/json"))

@router.api_route("/products", methods=["GET"])
async def product_list_proxy(request: Request):
    target_path = "/api/products"
    response = await proxy_request(PRODUCT_SERVICE_URL, request, target_path)
    return Response(content=response.content, status_code=response.status_code, media_type=response.headers.get("content-type", "application/json"))

# Cart Service routes (with /api prefix)
@router.api_route("/api/cart/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def cart_service_proxy_api(request: Request):
    response = await proxy_request(CART_SERVICE_URL, request)
    return Response(content=response.content, status_code=response.status_code, media_type=response.headers.get("content-type", "application/json"))

@router.api_route("/api/cart", methods=["GET", "DELETE"])
async def cart_proxy_api(request: Request):
    response = await proxy_request(CART_SERVICE_URL, request)
    return Response(content=response.content, status_code=response.status_code, media_type=response.headers.get("content-type", "application/json"))

# Cart Service routes (without /api prefix for frontend)
@router.api_route("/cart/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def cart_service_proxy(path: str, request: Request):
    target_path = f"/api/cart/{path}"
    response = await proxy_request(CART_SERVICE_URL, request, target_path)
    return Response(content=response.content, status_code=response.status_code, media_type=response.headers.get("content-type", "application/json"))

@router.api_route("/cart", methods=["GET"])
async def cart_proxy(request: Request):
    target_path = "/api/cart"
    response = await proxy_request(CART_SERVICE_URL, request, target_path)
    return Response(content=response.content, status_code=response.status_code, media_type=response.headers.get("content-type", "application/json"))

# Order Service routes (with /api prefix)
@router.api_route("/api/orders/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def order_service_proxy_api(request: Request):
    response = await proxy_request(ORDER_SERVICE_URL, request)
    return Response(content=response.content, status_code=response.status_code, media_type=response.headers.get("content-type", "application/json"))

@router.api_route("/api/orders", methods=["GET", "POST"])
async def order_list_proxy_api(request: Request):
    from fastapi.responses import Response
    response = await proxy_request(ORDER_SERVICE_URL, request)
    return Response(
        content=response.content,
        status_code=response.status_code,
        headers=dict(response.headers),
        media_type="application/json"
    )

# Order Service routes (without /api prefix for frontend)
@router.api_route("/orders/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def order_service_proxy(path: str, request: Request):
    target_path = f"/api/orders/{path}"
    response = await proxy_request(ORDER_SERVICE_URL, request, target_path)
    return Response(content=response.content, status_code=response.status_code, media_type=response.headers.get("content-type", "application/json"))

@router.api_route("/orders", methods=["GET", "POST"])
async def order_list_proxy(request: Request):
    target_path = "/api/orders"
    response = await proxy_request(ORDER_SERVICE_URL, request, target_path)
    return Response(content=response.content, status_code=response.status_code, media_type=response.headers.get("content-type", "application/json"))

# AI Service routes
@router.api_route("/api/chat/{path:path}", methods=["GET", "POST"])
async def ai_service_proxy(request: Request):
    response = await proxy_request(AI_SERVICE_URL, request)
    return Response(content=response.content, status_code=response.status_code, media_type=response.headers.get("content-type", "application/json"))

@router.api_route("/api/chat", methods=["POST"])
async def chat_proxy(request: Request):
    response = await proxy_request(AI_SERVICE_URL, request)
    return Response(content=response.content, status_code=response.status_code, media_type=response.headers.get("content-type", "application/json"))

# Made with Bob
