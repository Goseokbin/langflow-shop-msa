from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import os


from .routes import router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Langflow AI Service",
    description="AI-powered chatbot for customer support using ChatGPT-3.5-turbo",
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

# Include routers
app.include_router(router, prefix="/api", tags=["chat"])


@app.on_event("startup")
async def startup_event():
    """Startup event"""
    logger.info("Langflow AI Service started successfully")
    
    # Verify Langflow API key is set
    api_key = os.getenv("LANGFLOW_API_KEY")
    langflow_url = os.getenv("LANGFLOW_URL")
    
    if not api_key:
        logger.warning("LANGFLOW_API_KEY is not set, using default")
    else:
        logger.info("Langflow API key configured")
    
    if not langflow_url:
        logger.warning("LANGFLOW_URL is not set, using default")
    else:
        logger.info(f"Langflow URL configured: {langflow_url}")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "langflow-ai-service"}


@app.get("/ready")
async def readiness_check():
    """Readiness check endpoint"""
    api_key = os.getenv("LANGFLOW_API_KEY")
    langflow_url = os.getenv("LANGFLOW_URL")
    
    # Service is ready even with default values
    return {
        "status": "ready",
        "service": "langflow-ai-service",
        "langflow_configured": bool(api_key and langflow_url)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)

# Made with Bob
