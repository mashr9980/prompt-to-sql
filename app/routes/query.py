"""Query execution routes"""

import logging
from fastapi import APIRouter, Depends, HTTPException

from ..schemas.query import QueryRequest, SQLRequest, QueryResponse
from ..services.text_to_sql import TextToSQLService
from ..core.dependencies import get_text_to_sql_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/query", tags=["Query"])


@router.post("/", response_model=QueryResponse, summary="Execute natural language query")
async def execute_natural_language_query(
    request: QueryRequest,
    service: TextToSQLService = Depends(get_text_to_sql_service)
) -> QueryResponse:
    """
    Convert natural language to SQL and execute the query.
    
    **Features:**
    - Automatic SQL generation using AI
    - Support for complex business queries
    - Arabic/English mixed content support
    - Optimized for business management systems
    
    **Example queries:**
    - "Show me all employees with salary greater than 5000"
    - "List projects completed this month"
    - "Get attendance records for last week"
    """
    try:
        logger.info(f"Processing natural language query: {request.command[:100]}...")
        
        if not request.command.strip():
            raise HTTPException(
                status_code=400,
                detail="Query command cannot be empty"
            )
        
        response = await service.process_query(
            command=request.command,
            include_sql=request.include_sql
        )
        
        if not response.success:
            logger.warning(f"Query failed: {response.error}")
        
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to process natural language query: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Query processing failed: {str(e)}"
        )


@router.post("/sql", response_model=QueryResponse, summary="Execute direct SQL query")
async def execute_direct_sql_query(
    request: SQLRequest,
    service: TextToSQLService = Depends(get_text_to_sql_service)
) -> QueryResponse:
    """
    Execute SQL query directly without AI processing.
    
    **Use cases:**
    - When you already have a SQL query
    - For testing specific SQL statements
    - For advanced users who prefer writing SQL
    
    **Supported SQL features:**
    - T-SQL syntax
    - Complex JOINs
    - Stored procedures
    - Functions and aggregations
    """
    try:
        logger.info(f"Executing direct SQL query: {request.sql_query[:100]}...")
        
        if not request.sql_query.strip():
            raise HTTPException(
                status_code=400,
                detail="SQL query cannot be empty"
            )
        
        # Basic SQL injection protection (not comprehensive)
        dangerous_keywords = ['DROP', 'DELETE', 'TRUNCATE', 'ALTER', 'CREATE', 'INSERT', 'UPDATE']
        sql_upper = request.sql_query.upper()
        
        for keyword in dangerous_keywords:
            if keyword in sql_upper:
                logger.warning(f"Potentially dangerous SQL detected: {keyword}")
                # You might want to implement more sophisticated checking here
        
        response = await service.execute_direct_sql(request.sql_query)
        
        if not response.success:
            logger.warning(f"SQL execution failed: {response.error}")
        
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to execute direct SQL: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"SQL execution failed: {str(e)}"
        )


@router.get("/examples", summary="Get example queries")
async def get_example_queries():
    """
    Get example natural language queries that work well with this system.
    Useful for understanding the capabilities and testing.
    """
    return {
        "examples": [
            {
                "category": "Employee Management",
                "queries": [
                    "Show me all employees with salary greater than 5000",
                    "List employees who joined this year",
                    "Get attendance records for employees in IT department",
                    "Show employees with more than 5 years experience"
                ]
            },
            {
                "category": "Project Management",
                "queries": [
                    "List all active projects",
                    "Show projects completed this month",
                    "Get project budget summaries",
                    "Find overdue projects"
                ]
            },
            {
                "category": "Financial Queries",
                "queries": [
                    "Show total revenue for this quarter",
                    "List unpaid invoices",
                    "Get expense summary by category",
                    "Show profit margins by project"
                ]
            },
            {
                "category": "Inventory Management",
                "queries": [
                    "Show items with low stock",
                    "List most expensive inventory items",
                    "Get inventory turnover rates",
                    "Show items that need reordering"
                ]
            },
            {
                "category": "Supplier Management",
                "queries": [
                    "List all active suppliers",
                    "Show supplier performance metrics",
                    "Get pending purchase orders",
                    "Find suppliers with overdue payments"
                ]
            }
        ],
        "tips": [
            "Be specific about date ranges (e.g., 'this month', 'last quarter')",
            "Use clear column names when possible",
            "Specify sorting preferences (e.g., 'highest salary first')",
            "Include filtering criteria for better results"
        ]
    }


@router.get("/history", summary="Get query history")
async def get_query_history():
    """
    Get recent query history (placeholder for future implementation).
    This would typically store and retrieve query logs from a database.
    """
    return {
        "message": "Query history feature not implemented yet",
        "suggestion": "Consider implementing query logging for analytics and debugging"
    }