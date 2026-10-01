"""Health check API routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.database import get_async_session
from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "app_name": settings.app_name,
        "app_version": settings.app_version,
        "environment": settings.environment,
    }


@router.get("/health/db")
async def health_check_db(session: AsyncSession = Depends(get_async_session)) -> dict:
    """Database health check endpoint."""
    try:
        result = await session.execute(text("SELECT 1"))
        result.scalar_one()
        return {
            "status": "healthy",
            "database": "connected",
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e),
        }


@router.get("/health/storage")
async def health_check_storage() -> dict:
    """Object storage health check endpoint."""
    from app.services.storage import storage_service

    try:
        # Check if documents bucket exists
        exists = await storage_service.bucket_exists(settings.s3_bucket_documents)
        return {
            "status": "healthy" if exists else "degraded",
            "storage": "connected" if exists else "bucket_missing",
            "bucket_documents": exists,
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "storage": "disconnected",
            "error": str(e),
        }


@router.get("/health/all")
async def health_check_all(
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Comprehensive health check for all services."""
    from app.services.storage import storage_service

    # Check database
    db_healthy = True
    db_error = None
    try:
        result = await session.execute(text("SELECT 1"))
        result.scalar_one()
    except Exception as e:
        db_healthy = False
        db_error = str(e)

    # Check storage
    storage_healthy = True
    storage_error = None
    bucket_exists = False
    try:
        bucket_exists = await storage_service.bucket_exists(settings.s3_bucket_documents)
        if not bucket_exists:
            storage_healthy = False
            storage_error = "documents bucket not found"
    except Exception as e:
        storage_healthy = False
        storage_error = str(e)

    overall_status = "healthy" if db_healthy and storage_healthy else "unhealthy"

    return {
        "status": overall_status,
        "app_name": settings.app_name,
        "app_version": settings.app_version,
        "environment": settings.environment,
        "database": {
            "status": "connected" if db_healthy else "disconnected",
            "error": db_error,
        },
        "storage": {
            "status": "connected" if storage_healthy else "disconnected",
            "bucket_documents": bucket_exists,
            "error": storage_error,
        },
    }