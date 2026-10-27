from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from .routes import router
from .middleware import verify_token

app = FastAPI(
    title="API Gateway",
    description="API Gateway for MSA Shopping Mall",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Authentication middleware
@app.middleware("http")
async def authentication_middleware(request: Request, call_next):
    """Verify JWT token for protected endpoints"""
    # Skip authentication for OPTIONS requests (CORS preflight)
    if request.method == "OPTIONS":
        response = await call_next(request)
        return response
    
    try:
        await verify_token(request)
        response = await call_next(request)
        return response
    except Exception as e:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=getattr(e, 'status_code', 500),
            content={"detail": str(e)}
        )

# Include routes
app.include_router(router)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "api-gateway"}

@app.get("/ready")
async def readiness_check():
    """Readiness check endpoint"""
    return {"status": "ready", "service": "api-gateway"}

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "API Gateway",
        "version": "1.0.0",
        "endpoints": {
            "users": "/api/users",
            "products": "/api/products",
            "cart": "/api/cart",
            "orders": "/api/orders",
            "chat": "/api/chat"
        }
    }

# Made with Bob
