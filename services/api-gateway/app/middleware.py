from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
import os

security = HTTPBearer()

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

# Public endpoints that don't require authentication
PUBLIC_ENDPOINTS = [
    "/api/chat",
    "/health",
    "/ready",
    "/users/register",
    "/users/login",
    "/users/token",
    "/api/users/register",
    "/api/users/login",
    "/api/users/token",
    "/api/auth/register",
    "/api/auth/login",
    "/api/auth/token",
    "/products",
    "/api/products",
    "/docs",
    "/openapi.json",
]

def is_public_endpoint(path: str) -> bool:
    """Check if the endpoint is public"""
    for endpoint in PUBLIC_ENDPOINTS:
        if path.startswith(endpoint):
            return True
    return False

async def verify_token(request: Request):
    """Verify JWT token from request header"""
    if is_public_endpoint(request.url.path):
        return None
    
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    try:
        scheme, token = auth_header.split()
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid authentication scheme")
        
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid authorization header format")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

# Made with Bob
