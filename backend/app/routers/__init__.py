"""API routers for the EllinCRM API."""

from app.routers.extraction import router as extraction_router
from app.routers.records import router as records_router

__all__ = ["extraction_router", "records_router"]
