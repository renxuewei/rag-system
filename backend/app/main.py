"""
RAG API main program (API-only mode, frontend separated)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
import logging
import time

from app.routers import api

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="RAG Knowledge Base System",
    description="Enterprise-grade RAG knowledge base system API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api.router, prefix="/api", tags=["API"])

# Health check endpoint
@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "rag-api",
        "timestamp": time.time()
    }


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics():
    """Prometheus metrics endpoint"""
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    return PlainTextResponse(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


@app.on_event("startup")
async def startup_event():
    """Startup event"""
    logger.info("RAG API service starting...")

    try:
        from app.services.vector_store import milvus_service
        milvus_service.connect()
        milvus_service.create_collection()
        logger.info("Milvus connection successful")
    except Exception as e:
        logger.warning(f"Milvus connection warning: {e}")

    try:
        from app.services.cache_warmup import warmup_cache_on_startup
        await warmup_cache_on_startup()
    except Exception as e:
        logger.warning(f"Cache warmup skipped: {e}")

    logger.info("RAG API service ready")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("RAG API service shutdown")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",  # Listen on all network interfaces, accessible via 192.168.49.1 for Minikube
        port=8000,
        reload=False,
        workers=1
    )
