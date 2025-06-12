"""Health check routes"""

import logging
from fastapi import APIRouter, Depends

from ..schemas.database import HealthStatus, QuickHealthStatus
from ..services.text_to_sql import TextToSQLService
from ..core.dependencies import get_text_to_sql_service, get_service_status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/", response_model=HealthStatus, summary="Comprehensive health check")
async def health_check(
    service: TextToSQLService = Depends(get_text_to_sql_service)
) -> HealthStatus:
    """
    Comprehensive health check that includes:
    - Database connection status
    - Table count
    - Service initialization status
    
    This endpoint may take longer as it counts tables.
    """
    try:
        logger.debug("Performing comprehensive health check")
        status_data = service.get_health_status(include_table_count=True)
        
        return HealthStatus(**status_data)
    
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return HealthStatus(
            status="unhealthy",
            database_connected=False,
            error=str(e)
        )


@router.get("/quick", response_model=QuickHealthStatus, summary="Quick health check")
async def quick_health_check(
    service: TextToSQLService = Depends(get_text_to_sql_service)
) -> QuickHealthStatus:
    """
    Quick health check that only tests:
    - Database connection with a simple query
    
    This endpoint is optimized for speed and should respond in < 100ms.
    """
    try:
        logger.debug("Performing quick health check")
        status_data = service.get_quick_health_status()
        
        return QuickHealthStatus(**status_data)
    
    except Exception as e:
        logger.error(f"Quick health check failed: {str(e)}")
        return QuickHealthStatus(
            status="unhealthy",
            database_connected=False,
            error=str(e)
        )


@router.get("/services", summary="Service initialization status")
async def service_status():
    """
    Get the initialization status of all services.
    Useful for debugging and monitoring.
    """
    try:
        status = get_service_status()
        
        # Add database connection details if available
        try:
            service = get_text_to_sql_service()
            db_status = service.database_service.get_connection_status()
            status.update({"database_connection_details": db_status})
        except Exception as e:
            status.update({"database_connection_details": {"error": str(e)}})
        
        return {
            "status": "healthy",
            "services": status
        }
    
    except Exception as e:
        logger.error(f"Service status check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "services": get_service_status()
        }