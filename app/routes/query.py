"""Query execution routes - Modified for SQL-only output"""

import logging
from fastapi import APIRouter, Depends, HTTPException

from ..schemas.query import QueryRequest, SQLRequest, QueryResponse
from ..services.text_to_sql import TextToSQLService
from ..core.dependencies import get_text_to_sql_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/query", tags=["Query"])


@router.post("/", response_model=QueryResponse, summary="Generate SQL query from natural language")
async def execute_natural_language_query(
    request: QueryRequest,
    service: TextToSQLService = Depends(get_text_to_sql_service)
) -> QueryResponse:
    """
    Convert natural language to SQL query only (no execution).
    
    **Features:**
    - Fast SQL generation using AI
    - Support for complex business queries
    - Arabic/English mixed content support
    - Optimized for business management systems
    - Returns only the SQL query for manual testing
    
    **Example queries:**
    - "Show me all employees with salary greater than 5000"
    - "List projects completed this month"
    - "Get attendance records for last week"
    
    **Response:**
    The response will contain only the generated SQL query in the `result` field.
    You can then test this query manually in your database client or use the
    Direct SQL execution endpoint.
    """
    try:
        logger.info(f"Processing natural language query for SQL generation: {request.command[:100]}...")
        
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
            logger.warning(f"SQL generation failed: {response.error}")
        else:
            logger.info(f"SQL generated successfully: {response.result[:100]}...")
        
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
    Execute SQL query directly against the database.
    
    **Use cases:**
    - When you already have a SQL query
    - For testing generated SQL statements
    - For advanced users who prefer writing SQL
    
    **Supported SQL features:**
    - T-SQL syntax
    - Complex JOINs
    - Stored procedures
    - Functions and aggregations
    
    **Security Note:**
    This endpoint has basic protection against dangerous operations.
    Use with caution in production environments.
    """
    try:
        logger.info(f"Executing direct SQL query: {request.sql_query[:100]}...")
        
        if not request.sql_query.strip():
            raise HTTPException(
                status_code=400,
                detail="SQL query cannot be empty"
            )
        
        # Basic SQL injection protection (enhanced)
        dangerous_keywords = ['DROP', 'DELETE', 'TRUNCATE', 'ALTER', 'CREATE', 'INSERT', 'UPDATE']
        sql_upper = request.sql_query.upper()
        
        for keyword in dangerous_keywords:
            if keyword in sql_upper:
                logger.warning(f"Potentially dangerous SQL detected: {keyword}")
                # In production, you might want to block these entirely
                # For now, we'll just log and proceed with caution
        
        response = await service.execute_direct_sql(request.sql_query)
        
        if not response.success:
            logger.warning(f"SQL execution failed: {response.error}")
        else:
            logger.info(f"SQL executed successfully")
        
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
    Useful for understanding the capabilities and testing the SQL generation.
    """
    return {
        "examples": [
            {
                "category": "Employee Management",
                "queries": [
                    "Show me all employees with salary greater than 5000",
                    "List employees who joined this year",
                    "Get attendance records for employees in IT department",
                    "Show employees with more than 5 years experience",
                    "Find employees who haven't attended today"
                ]
            },
            {
                "category": "Project Management",
                "queries": [
                    "List all active projects",
                    "Show projects completed this month",
                    "Get project budget summaries",
                    "Find overdue projects",
                    "Show projects by status"
                ]
            },
            {
                "category": "Financial Queries",
                "queries": [
                    "Show total revenue for this quarter",
                    "List unpaid invoices",
                    "Get expense summary by category",
                    "Show profit margins by project",
                    "Find transactions over 10000"
                ]
            },
            {
                "category": "Inventory Management",
                "queries": [
                    "Show items with low stock",
                    "List most expensive inventory items",
                    "Get inventory turnover rates",
                    "Show items that need reordering",
                    "Find items added this week"
                ]
            },
            {
                "category": "Supplier Management",
                "queries": [
                    "List all active suppliers",
                    "Show supplier performance metrics",
                    "Get pending purchase orders",
                    "Find suppliers with overdue payments",
                    "Show top suppliers by volume"
                ]
            },
            {
                "category": "Time & Attendance",
                "queries": [
                    "Show today's attendance",
                    "List employees who worked overtime",
                    "Get weekly attendance summary",
                    "Find employees with perfect attendance",
                    "Show late arrivals this month"
                ]
            }
        ],
        "tips": [
            "Be specific about date ranges (e.g., 'this month', 'last quarter')",
            "Use clear column names when possible",
            "Specify sorting preferences (e.g., 'highest salary first')",
            "Include filtering criteria for better results",
            "The system generates SQL only - test the query separately",
            "Arabic and English text are both supported",
            "Use business terms rather than technical database terms"
        ],
        "workflow": [
            "1. Enter your natural language query",
            "2. Get the generated SQL query",
            "3. Copy or move the SQL to the Direct SQL tab",
            "4. Execute the SQL to see actual results",
            "5. Modify the SQL if needed for better results"
        ],
        "note": "This endpoint generates SQL queries only. Use the Direct SQL endpoint to execute and see results."
    }


@router.get("/validate/{sql_query}", summary="Validate SQL query syntax")
async def validate_sql_query(
    sql_query: str,
    service: TextToSQLService = Depends(get_text_to_sql_service)
):
    """
    Validate SQL query syntax without executing it.
    
    This is a basic validation that checks for obvious syntax errors
    and dangerous operations.
    """
    try:
        # Basic validation
        if not sql_query.strip():
            return {
                "valid": False,
                "error": "SQL query cannot be empty",
                "suggestions": ["Enter a valid SQL query"]
            }
        
        sql_upper = sql_query.upper().strip()
        
        # Check for dangerous operations
        dangerous_ops = ['DROP', 'DELETE', 'TRUNCATE', 'ALTER', 'CREATE']
        dangerous_found = [op for op in dangerous_ops if op in sql_upper]
        
        if dangerous_found:
            return {
                "valid": False,
                "error": f"Potentially dangerous operations detected: {', '.join(dangerous_found)}",
                "suggestions": ["Use SELECT queries for data retrieval", "Avoid data modification operations"]
            }
        
        # Check for basic SQL structure
        if not any(keyword in sql_upper for keyword in ['SELECT', 'WITH']):
            return {
                "valid": False,
                "error": "Query must start with SELECT or WITH",
                "suggestions": ["Start your query with SELECT", "Use proper SQL syntax"]
            }
        
        # Basic parentheses matching
        if sql_query.count('(') != sql_query.count(')'):
            return {
                "valid": False,
                "error": "Unmatched parentheses in query",
                "suggestions": ["Check that all parentheses are properly closed"]
            }
        
        return {
            "valid": True,
            "message": "Query syntax appears valid",
            "suggestions": ["Execute the query to see results"]
        }
        
    except Exception as e:
        logger.error(f"Failed to validate SQL query: {str(e)}")
        return {
            "valid": False,
            "error": f"Validation failed: {str(e)}",
            "suggestions": ["Check your SQL syntax"]
        }


@router.post("/generate-variations", summary="Generate SQL query variations")
async def generate_query_variations(
    request: QueryRequest,
    service: TextToSQLService = Depends(get_text_to_sql_service)
):
    """
    Generate multiple SQL query variations for the same natural language input.
    
    This can help you find the best query approach for your needs.
    """
    try:
        if not request.command.strip():
            raise HTTPException(
                status_code=400,
                detail="Query command cannot be empty"
            )
        
        variations = []
        
        # Generate 3 different variations with slightly different prompts
        variation_prompts = [
            f"{request.command}",
            f"{request.command} (optimize for performance)",
            f"{request.command} (include relevant joins)"
        ]
        
        for i, prompt in enumerate(variation_prompts):
            try:
                response = await service.process_query(
                    command=prompt,
                    include_sql=True
                )
                
                if response.success and response.result:
                    variations.append({
                        "variation": i + 1,
                        "sql_query": response.result,
                        "prompt_hint": ["Basic query", "Performance optimized", "With joins"][i],
                        "execution_time": response.execution_time
                    })
            except Exception as e:
                logger.warning(f"Failed to generate variation {i + 1}: {str(e)}")
                continue
        
        if not variations:
            raise HTTPException(
                status_code=500,
                detail="Failed to generate any query variations"
            )
        
        return {
            "original_query": request.command,
            "variations": variations,
            "total_variations": len(variations),
            "note": "Test each variation to find the best one for your needs"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate query variations: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Variation generation failed: {str(e)}"
        )


@router.get("/history", summary="Get query generation history")
async def get_query_history():
    """
    Get recent query generation history (placeholder for future implementation).
    
    This would typically store and retrieve query logs from a database
    to help users track their query patterns and reuse successful queries.
    """
    return {
        "message": "Query history feature not implemented yet",
        "suggestion": "Consider implementing query logging for analytics and reuse",
        "planned_features": [
            "Store generated SQL queries",
            "Track query success rates",
            "Provide query suggestions based on history",
            "Export query history",
            "Search through previous queries"
        ]
    }


@router.get("/stats", summary="Get query generation statistics")
async def get_query_stats():
    """
    Get statistics about query generation performance and usage.
    """
    # This would typically come from a database or monitoring system
    return {
        "message": "Query statistics feature not implemented yet",
        "planned_metrics": [
            "Total queries generated",
            "Average generation time",
            "Most common query patterns",
            "Success rate",
            "Popular table usage",
            "Query complexity distribution"
        ],
        "note": "Implement logging and analytics for production use"
    }