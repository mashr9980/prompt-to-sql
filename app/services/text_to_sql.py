import time
import logging
from typing import Optional

from ..schemas.query import QueryResponse
from ..schemas.database import TableInfo
from ..services.database import DatabaseService
from ..services.llm import LLMService
from ..core.exceptions import QueryExecutionError

logger = logging.getLogger(__name__)


class TextToSQLService:
    """Main service for converting natural language to SQL and executing queries"""
    
    def __init__(self, llm_service: LLMService, database_service: DatabaseService):
        self.llm_service = llm_service
        self.database_service = database_service
        logger.info("TextToSQLService initialized successfully")
    
    def get_quick_health_status(self) -> dict:
        """Get quick health status without expensive operations"""
        try:
            is_connected = self.database_service.test_connection()
            
            return {
                "status": "healthy" if is_connected else "unhealthy",
                "database_connected": is_connected
            }
        
        except Exception as e:
            logger.error(f"Quick health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "database_connected": False,
                "error": str(e)
            }
    
    async def process_query(self, command: str, include_sql: bool = True) -> QueryResponse:
        """Process natural language query and return results"""
        start_time = time.time()
        
        logger.info(f"Processing query: {command[:50]}...")
        
        try:
            # Get table information for context
            table_info = self.database_service.get_table_info()
            
            # Generate SQL using LLM
            logger.debug("Generating SQL query using LLM")
            sql_query = self.llm_service.generate_sql(command, table_info)
            
            # Execute the generated SQL
            logger.debug("Executing generated SQL query")
            result = self.database_service.execute_sql(sql_query)
            
            execution_time = time.time() - start_time
            
            logger.info(f"Query processed successfully in {execution_time:.3f} seconds")
            
            return QueryResponse(
                success=True,
                command=command,
                sql_query=sql_query if include_sql else None,
                result=result,
                execution_time=round(execution_time, 3)
            )
        
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = str(e)
            
            logger.error(f"Query processing failed: {error_msg}")
            
            return QueryResponse(
                success=False,
                command=command,
                error=error_msg,
                execution_time=round(execution_time, 3)
            )
    
    async def execute_direct_sql(self, sql_query: str) -> QueryResponse:
        """Execute SQL query directly without LLM processing"""
        start_time = time.time()
        
        logger.info(f"Executing direct SQL: {sql_query[:50]}...")
        
        try:
            result = self.database_service.execute_sql(sql_query)
            execution_time = time.time() - start_time
            
            logger.info(f"Direct SQL executed successfully in {execution_time:.3f} seconds")
            
            return QueryResponse(
                success=True,
                sql_query=sql_query,
                result=result,
                execution_time=round(execution_time, 3)
            )
        
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = str(e)
            
            logger.error(f"Direct SQL execution failed: {error_msg}")
            
            return QueryResponse(
                success=False,
                sql_query=sql_query,
                error=error_msg,
                execution_time=round(execution_time, 3)
            )
    
    def get_database_info(self) -> TableInfo:
        """Get comprehensive database information"""
        try:
            logger.debug("Retrieving database information")
            
            table_names = self.database_service.get_table_names()
            schema_info = self.database_service.get_table_info()
            
            return TableInfo(
                table_names=table_names,
                schema_info=schema_info
            )
        
        except Exception as e:
            logger.error(f"Failed to get database info: {str(e)}")
            raise QueryExecutionError(f"Failed to retrieve database information: {str(e)}")
    
    def get_table_description(self, table_name: str) -> dict:
        """Get detailed description of a specific table"""
        try:
            logger.debug(f"Getting description for table: {table_name}")
            
            result = self.database_service.describe_table(table_name)
            
            return {
                "table_name": table_name,
                "schema": result,
                "success": True
            }
        
        except Exception as e:
            logger.error(f"Failed to describe table {table_name}: {str(e)}")
            return {
                "table_name": table_name,
                "error": str(e),
                "success": False
            }
    
    def get_health_status(self, include_table_count: bool = True) -> dict:
        """Get comprehensive health status"""
        try:
            # Test database connection
            is_connected = self.database_service.test_connection()
            
            if not is_connected:
                return {
                    "status": "unhealthy",
                    "database_connected": False,
                    "error": "Database connection failed"
                }
            
            result = {
                "status": "healthy",
                "database_connected": True
            }
            
            # Include table count if requested
            if include_table_count:
                try:
                    table_names = self.database_service.get_table_names()
                    result["tables_count"] = len(table_names)
                except Exception as e:
                    logger.warning(f"Could not get table count: {str(e)}")
                    result["tables_count"] = None
            
            return result
        
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return