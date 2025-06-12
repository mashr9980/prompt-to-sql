from typing import List, Any, Optional
from pydantic import BaseModel, Field


class TableInfo(BaseModel):
    """Schema for table information"""
    table_names: List[str] = Field(..., description="List of available table names")
    schema_info: str = Field(..., description="Detailed schema information")
    
    class Config:
        json_schema_extra = {
            "example": {
                "table_names": ["users", "projects", "attendance"],
                "schema_info": "Table: users\nColumns: id, name, salary..."
            }
        }


class TableSchema(BaseModel):
    """Schema for individual table description"""
    table_name: str = Field(..., description="Name of the table")
    schema: Any = Field(..., description="Table schema details")
    
    class Config:
        json_schema_extra = {
            "example": {
                "table_name": "users",
                "schema": "COLUMN_NAME | DATA_TYPE | IS_NULLABLE\nid | int | NO\nname | varchar | YES"
            }
        }


class HealthStatus(BaseModel):
    """Schema for health check response"""
    status: str = Field(..., description="Health status", pattern="^(healthy|unhealthy)$")
    database_connected: bool = Field(..., description="Database connection status")
    tables_count: Optional[int] = Field(None, description="Number of tables in database")
    error: Optional[str] = Field(None, description="Error message if unhealthy")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "database_connected": True,
                "tables_count": 15,
                "error": None
            }
        }


class QuickHealthStatus(BaseModel):
    """Schema for quick health check response"""
    status: str = Field(..., description="Health status", pattern="^(healthy|unhealthy)$")
    database_connected: bool = Field(..., description="Database connection status")
    error: Optional[str] = Field(None, description="Error message if unhealthy")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "database_connected": True,
                "error": None
            }
        }