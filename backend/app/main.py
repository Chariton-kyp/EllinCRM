"""
EllinCRM - AI Document Automation API
======================================

FastAPI application for automated data extraction from forms, emails, and invoices
with human-in-the-loop controls.

Author: Kypraios Chariton
"""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.ai.embeddings import get_embedding_status, start_embedding_model_loading
from app.ai.ai_router import get_ai_router, init_ai_router
from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.db.database import close_db, init_db
from app.routers import extraction_router, records_router
from app.routers.chat import router as chat_router
from app.routers.notifications import router as notifications_router
from app.routers.search import router as search_router

# Initialize logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown."""
    # Startup
    logger.info(
        "application_startup",
        app_name=settings.app_name,
        environment=settings.app_env,
        debug=settings.debug,
    )

    # Initialize database connection
    if settings.database_url:
        try:
            await init_db()
            logger.info("database_initialized")
        except Exception as e:
            logger.error("database_init_failed", error=str(e))
            # Continue without database in development
            if settings.is_production:
                raise

    # Verify data path exists
    if not settings.data_path.exists():
        logger.warning("data_path_not_found", path=str(settings.data_path))

    # Ensure output path exists
    settings.output_path.mkdir(parents=True, exist_ok=True)

    # Start embedding model loading in background (non-blocking)
    # This allows the API to start immediately while the model loads
    logger.info("starting_embedding_model_background_loading")
    start_embedding_model_loading()

    # Initialize any-llm AI router (non-blocking, graceful degradation)
    logger.info("initializing_ai_router")
    init_ai_router()

    yield

    # Shutdown
    if settings.database_url:
        await close_db()
        logger.info("database_closed")

    logger.info("application_shutdown")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="EllinCRM - AI-powered document extraction with human-in-the-loop controls",
    version="1.0.0",
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],  # Required for file downloads
)


# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle HTTP exceptions with structured response."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.status_code,
                "message": exc.detail,
            }
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions."""
    logger.error("unhandled_exception", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": 500,
                "message": "Internal server error",
            }
        },
    )


# Health check endpoint
@app.get("/health")
async def health_check() -> dict[str, Any]:
    """Health check endpoint for container orchestration."""
    embedding_status = get_embedding_status()
    router = get_ai_router()
    ai_router_status = "initialized" if router is not None else "not configured"
    chat_ready = router is not None and embedding_status["is_ready"]
    return {
        "status": "healthy",
        "app": settings.app_name,
        "environment": settings.app_env,
        "version": "1.0.0",
        "database": "connected" if settings.database_url else "not configured",
        "embedding_model": {
            "status": embedding_status["status"],
            "ready": embedding_status["is_ready"],
        },
        "ai_router": {
            "status": ai_router_status,
            "models": ["gemini-flash", "claude-sonnet", "claude-haiku"] if router else [],
        },
        "chat_agent": {
            "ready": chat_ready,
            "requires": "ai_router + embedding_model",
        },
    }


# Root endpoint
@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint with API information."""
    return {
        "message": "EllinCRM AI Document Automation API",
        "docs": "/docs" if settings.is_development else "Disabled in production",
        "health": "/health",
        "api": settings.api_v1_prefix,
    }


# API v1 router
api_v1_router = APIRouter(prefix=settings.api_v1_prefix)


@api_v1_router.get("/status")
async def api_status() -> dict[str, Any]:
    """API status endpoint."""
    return {
        "status": "operational",
        "version": "1.0.0",
        "features": {
            "form_extraction": True,
            "email_extraction": True,
            "invoice_extraction": True,
            "semantic_search": True,
            "embeddings": True,
            "ai_enhancement": settings.enable_ai_extraction,
            "chat_agent": True,
            "llm_router": get_ai_router() is not None,
            "database_persistence": settings.database_url is not None,
        },
        "ai": {
            "embedding_model_primary": settings.embedding_model,
            "embedding_model_fallback": settings.fallback_embedding_model,
            "llm_models": ["gemini-flash", "claude-sonnet", "claude-haiku"] if get_ai_router() else [],
            "vector_database": "pgvector",
            "search_algorithm": "HNSW",
        },
    }


# Include sub-routers
api_v1_router.include_router(extraction_router)
api_v1_router.include_router(records_router)
api_v1_router.include_router(search_router)
api_v1_router.include_router(chat_router)

# Include API v1 router in app
app.include_router(api_v1_router)

# Include WebSocket router (not under API version prefix)
app.include_router(notifications_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.is_development,
    )
