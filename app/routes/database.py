"""Database-related routes"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Path

from ..schemas.database import TableInfo, TableSchema
from ..services.text_to_sql import TextToSQLService
from ..core.dependencies import get_text_to_sql_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/database", tags=["Database"])


@router.get("/tables", response_model=TableInfo, summary="Get all tables information")
async def get_tables(
    service: TextToSQLService = Depends(get_text_to_sql_service)
) -> TableInfo:
    """
    Get comprehensive information about all tables in the database:
    - List of table names
    - Detailed schema information
    
    Results are cached for better performance.
    """
    try:
        logger.info("Retrieving database tables information")
        return service.get_database_info()
    
    except Exception as e:
        logger.error(f"Failed to get tables information: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve tables information: {str(e)}"
        )


@router.get("/tables/names", summary="Get table names only")
async def get_table_names(
    service: TextToSQLService = Depends(get_text_to_sql_service)
):
    """
    Get only the list of table names (faster than full table info).
    Useful when you only need table names without schema details.
    """
    try:
        logger.info("Retrieving table names")
        table_names = service.database_service.get_table_names()
        
        return {
            "table_names": table_names,
            "count": len(table_names)
        }
    
    except Exception as e:
        logger.error(f"Failed to get table names: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve table names: {str(e)}"
        )


@router.get("/tables/{table_name}", response_model=TableSchema, summary="Get specific table schema")
async def describe_table(
    table_name: str = Path(..., description="Name of the table to describe"),
    service: TextToSQLService = Depends(get_text_to_sql_service)
) -> TableSchema:
    """
    Get detailed schema information for a specific table:
    - Column names and data types
    - Nullable constraints
    - Default values
    - Character limits
    """
    try:
        logger.info(f"Describing table: {table_name}")
        result = service.get_table_description(table_name)
        
        if not result.get("success", True):
            raise HTTPException(
                status_code=404,
                detail=result.get("error", f"Table '{table_name}' not found or not accessible")
            )
        
        return TableSchema(
            table_name=table_name,
            schema=result["schema"]
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to describe table {table_name}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to describe table '{table_name}': {str(e)}"
        )


@router.get("/schema", summary="Get complete database schema")
async def get_database_schema(
    service: TextToSQLService = Depends(get_text_to_sql_service)
):
    """
    Get the complete database schema information.
    This is an alias for /database/tables but with additional metadata.
    """
    try:
        logger.info("Retrieving complete database schema")
        table_info = service.get_database_info()
        
        return {
            "database_type": "Microsoft SQL Server",
            "total_tables": len(table_info.table_names),
            "tables": table_info.table_names,
            "schema_details": table_info.schema_info,
            "generated_at": "2025-06-12T00:00:00Z"  # This would be dynamic in real implementation
        }
    
    except Exception as e:
        logger.error(f"Failed to get database schema: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve database schema: {str(e)}"
        )