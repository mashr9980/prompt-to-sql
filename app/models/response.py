"""Response models for API endpoints with comprehensive data structures"""

from typing import Optional, Any, Dict, List, Union
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict


class ResponseStatus(str, Enum):
    """Standard response status codes"""
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    PARTIAL = "partial"


class ErrorType(str, Enum):
    """Types of errors that can occur"""
    VALIDATION_ERROR = "validation_error"
    DATABASE_ERROR = "database_error"
    LLM_ERROR = "llm_error"
    AUTHENTICATION_ERROR = "authentication_error"
    AUTHORIZATION_ERROR = "authorization_error"
    TIMEOUT_ERROR = "timeout_error"
    CONFIGURATION_ERROR = "configuration_error"
    INTERNAL_ERROR = "internal_error"


class BaseResponse(BaseModel):
    """Base response model with common fields"""
    model_config = ConfigDict(
        use_enum_values=True,
        arbitrary_types_allowed=True
    )
    
    status: ResponseStatus = Field(
        ...,
        description="Response status"
    )
    
    message: Optional[str] = Field(
        default=None,
        description="Human-readable response message"
    )
    
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Response timestamp"
    )
    
    request_id: Optional[str] = Field(
        default=None,
        description="Unique request identifier for tracking"
    )
    
    execution_time: Optional[float] = Field(
        default=None,
        description="Request execution time in seconds",
        ge=0
    )


class ErrorDetail(BaseModel):
    """Detailed error information"""
    
    type: ErrorType = Field(
        ...,
        description="Type of error"
    )
    
    code: Optional[str] = Field(
        default=None,
        description="Specific error code"
    )
    
    message: str = Field(
        ...,
        description="Error message"
    )
    
    details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional error details"
    )
    
    field: Optional[str] = Field(
        default=None,
        description="Field that caused the error (for validation errors)"
    )
    
    suggestion: Optional[str] = Field(
        default=None,
        description="Suggestion for fixing the error"
    )


class QueryExecutionResponse(BaseResponse):
    """Response model for query execution"""
    
    data: Optional[Any] = Field(
        default=None,
        description="Query result data"
    )
    
    sql_query: Optional[str] = Field(
        default=None,
        description="Executed SQL query"
    )
    
    result_metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Metadata about the query results"
    )
    
    rows_affected: Optional[int] = Field(
        default=None,
        description="Number of rows affected",
        ge=0
    )
    
    rows_returned: Optional[int] = Field(
        default=None,
        description="Number of rows returned",
        ge=0
    )
    
    columns: Optional[List[str]] = Field(
        default=None,
        description="Column names in result set"
    )
    
    errors: Optional[List[ErrorDetail]] = Field(
        default=None,
        description="List of errors that occurred"
    )
    
    warnings: Optional[List[str]] = Field(
        default=None,
        description="Warning messages"
    )
    
    cache_info: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Cache hit/miss information"
    )


class DatabaseInfoResponse(BaseResponse):
    """Response model for database information"""
    
    database_name: Optional[str] = Field(
        default=None,
        description="Name of the database"
    )
    
    database_type: Optional[str] = Field(
        default=None,
        description="Type of database (e.g., MSSQL, PostgreSQL)"
    )
    
    total_tables: int = Field(
        ...,
        description="Total number of tables",
        ge=0
    )
    
    table_names: List[str] = Field(
        default_factory=list,
        description="List of table names"
    )
    
    schema_info: Optional[str] = Field(
        default=None,
        description="Detailed schema information"
    )
    
    connection_info: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Database connection metadata"
    )


class TableSchemaResponse(BaseResponse):
    """Response model for table schema information"""
    
    table_name: str = Field(
        ...,
        description="Name of the table"
    )
    
    columns: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Column definitions"
    )
    
    primary_keys: Optional[List[str]] = Field(
        default=None,
        description="Primary key columns"
    )
    
    foreign_keys: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Foreign key relationships"
    )
    
    indexes: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Table indexes"
    )
    
    row_count: Optional[int] = Field(
        default=None,
        description="Approximate number of rows",
        ge=0
    )
    
    size_info: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Table size information"
    )


class HealthCheckResponse(BaseResponse):
    """Response model for health checks"""
    
    service_status: Dict[str, bool] = Field(
        default_factory=dict,
        description="Status of individual services"
    )
    
    database_connected: bool = Field(
        ...,
        description="Database connection status"
    )
    
    llm_service_available: Optional[bool] = Field(
        default=None,
        description="LLM service availability"
    )
    
    cache_status: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Cache system status"
    )
    
    system_metrics: Optional[Dict[str, Any]] = Field(
        default=None,
        description="System performance metrics"
    )
    
    uptime: Optional[float] = Field(
        default=None,
        description="Service uptime in seconds",
        ge=0
    )
    
    version: Optional[str] = Field(
        default=None,
        description="API version"
    )


class ValidationResponse(BaseResponse):
    """Response model for query validation"""
    
    is_valid: bool = Field(
        ...,
        description="Whether the query is valid"
    )
    
    generated_sql: Optional[str] = Field(
        default=None,
        description="Generated SQL query"
    )
    
    validation_errors: Optional[List[ErrorDetail]] = Field(
        default=None,
        description="Validation error details"
    )
    
    suggestions: Optional[List[str]] = Field(
        default=None,
        description="Improvement suggestions"
    )
    
    complexity_score: Optional[int] = Field(
        default=None,
        description="Query complexity score (1-10)",
        ge=1,
        le=10
    )
    
    estimated_performance: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Estimated performance metrics"
    )


class BatchOperationResponse(BaseResponse):
    """Response model for batch operations"""
    
    total_operations: int = Field(
        ...,
        description="Total number of operations in batch",
        ge=0
    )
    
    successful_operations: int = Field(
        ...,
        description="Number of successful operations",
        ge=0
    )
    
    failed_operations: int = Field(
        ...,
        description="Number of failed operations",
        ge=0
    )
    
    results: List[Union[QueryExecutionResponse, ErrorDetail]] = Field(
        default_factory=list,
        description="Individual operation results"
    )
    
    summary: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Batch operation summary"
    )


class ExportResponse(BaseResponse):
    """Response model for data export operations"""
    
    export_format: str = Field(
        ...,
        description="Format of exported data (CSV, JSON, Excel, etc.)"
    )
    
    file_url: Optional[str] = Field(
        default=None,
        description="URL to download the exported file"
    )
    
    file_size: Optional[int] = Field(
        default=None,
        description="Size of exported file in bytes",
        ge=0
    )
    
    record_count: Optional[int] = Field(
        default=None,
        description="Number of records exported",
        ge=0
    )
    
    expires_at: Optional[datetime] = Field(
        default=None,
        description="When the export file expires"
    )


class QueryAnalyticsResponse(BaseResponse):
    """Response model for query analytics"""
    
    query_count: int = Field(
        ...,
        description="Total number of queries analyzed",
        ge=0
    )
    
    avg_execution_time: Optional[float] = Field(
        default=None,
        description="Average execution time in seconds",
        ge=0
    )
    
    most_common_tables: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Most frequently queried tables"
    )
    
    error_rate: Optional[float] = Field(
        default=None,
        description="Query error rate as percentage",
        ge=0,
        le=100
    )
    
    performance_trends: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Performance trend data"
    )
    
    user_activity: Optional[Dict[str, Any]] = Field(
        default=None,
        description="User activity statistics"
    )


class ConfigurationResponse(BaseResponse):
    """Response model for configuration information"""
    
    api_version: str = Field(
        ...,
        description="API version"
    )
    
    database_type: Optional[str] = Field(
        default=None,
        description="Database type"
    )
    
    llm_provider: Optional[str] = Field(
        default=None,
        description="LLM service provider"
    )
    
    features_enabled: Dict[str, bool] = Field(
        default_factory=dict,
        description="Enabled features"
    )
    
    limits: Optional[Dict[str, Any]] = Field(
        default=None,
        description="API limits and quotas"
    )
    
    cache_settings: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Cache configuration"
    )


class MetricsResponse(BaseResponse):
    """Response model for system metrics"""
    
    request_count: int = Field(
        ...,
        description="Total request count",
        ge=0
    )
    
    error_count: int = Field(
        ...,
        description="Total error count",
        ge=0
    )
    
    avg_response_time: float = Field(
        ...,
        description="Average response time in seconds",
        ge=0
    )
    
    cache_hit_rate: Optional[float] = Field(
        default=None,
        description="Cache hit rate as percentage",
        ge=0,
        le=100
    )
    
    database_connections: Optional[int] = Field(
        default=None,
        description="Active database connections",
        ge=0
    )
    
    memory_usage: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Memory usage statistics"
    )
    
    cpu_usage: Optional[float] = Field(
        default=None,
        description="CPU usage percentage",
        ge=0,
        le=100
    )


# Utility functions for creating standard responses

def create_success_response(
    data: Any = None,
    message: str = "Operation completed successfully",
    **kwargs
) -> BaseResponse:
    """Create a standard success response"""
    return BaseResponse(
        status=ResponseStatus.SUCCESS,
        message=message,
        **kwargs
    )


def create_error_response(
    error_type: ErrorType,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    **kwargs
) -> BaseResponse:
    """Create a standard error response"""
    error_detail = ErrorDetail(
        type=error_type,
        message=message,
        details=details
    )
    
    return BaseResponse(
        status=ResponseStatus.ERROR,
        message=message,
        **kwargs
    )


def create_validation_error_response(
    field: str,
    message: str,
    suggestion: Optional[str] = None
) -> BaseResponse:
    """Create a validation error response"""
    error_detail = ErrorDetail(
        type=ErrorType.VALIDATION_ERROR,
        message=message,
        field=field,
        suggestion=suggestion
    )
    
    return BaseResponse(
        status=ResponseStatus.ERROR,
        message=f"Validation error in field '{field}': {message}"
    )