import re
import time
import logging
from typing import List, Optional
from sqlalchemy import create_engine, text
from langchain_community.utilities import SQLDatabase

from ..config import settings
from ..core.exceptions import DatabaseConnectionError, QueryExecutionError, SchemaRetrievalError

logger = logging.getLogger(__name__)


class DatabaseService:
    """Service for database operations with caching and connection management"""
    
    def __init__(self):
        self.db: Optional[SQLDatabase] = None
        self._table_names_cache: Optional[List[str]] = None
        self._table_info_cache: Optional[str] = None
        self._cache_timestamp: Optional[float] = None
        self._schema_cache_timestamp: Optional[float] = None
        self._connection_established = False
        
        # Connection strings to try
        self.connection_strings = [
            settings.DATABASE_URL,
            # *settings.DATABASE_FALLBACK_URLS
        ]
        
        self._establish_connection()
    
    def _establish_connection(self) -> None:
        """Establish database connection with fallback options"""
        last_error = None
        
        for i, conn_str in enumerate(self.connection_strings):
            try:
                logger.info(f"Attempting database connection {i + 1}/{len(self.connection_strings)}")
                self.db = SQLDatabase.from_uri(conn_str)
                
                # Test the connection
                self.db.run("SELECT 1")
                
                self._connection_established = True
                logger.info("Database connection established successfully")
                return
                
            except Exception as e:
                last_error = e
                logger.warning(f"Connection attempt {i + 1} failed: {str(e)}")
                continue
        
        raise DatabaseConnectionError(f"All database connection attempts failed. Last error: {last_error}")
    
    def _is_cache_valid(self, cache_type: str = "default") -> bool:
        """Check if cache is still valid"""
        if cache_type == "schema":
            if not self._schema_cache_timestamp:
                return False
            return time.time() - self._schema_cache_timestamp < settings.SCHEMA_CACHE_TTL
        else:
            if not self._cache_timestamp:
                return False
            return time.time() - self._cache_timestamp < settings.CACHE_TTL
    
    def _ensure_connection(self) -> None:
        """Ensure database connection is available"""
        if not self._connection_established or not self.db:
            logger.warning("Database connection lost, attempting to reconnect...")
            self._establish_connection()
    
    def test_connection(self) -> bool:
        """Quick connection test using a simple query"""
        try:
            self._ensure_connection()
            self.db.run("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {str(e)}")
            self._connection_established = False
            return False
    
    def get_table_names(self) -> List[str]:
        """Get list of table names with caching"""
        try:
            # Return cached result if valid
            if self._table_names_cache and self._is_cache_valid():
                logger.debug("Returning cached table names")
                return self._table_names_cache
            
            self._ensure_connection()
            
            logger.info("Fetching table names from database")
            self._table_names_cache = self.db.get_usable_table_names()
            self._cache_timestamp = time.time()
            
            logger.info(f"Found {len(self._table_names_cache)} tables")
            return self._table_names_cache
            
        except Exception as e:
            logger.error(f"Failed to get table names: {str(e)}")
            raise SchemaRetrievalError(f"Failed to retrieve table names: {str(e)}")
    
    def get_table_info(self) -> str:
        """Get detailed table information with caching"""
        try:
            # Return cached result if valid
            if self._table_info_cache and self._is_cache_valid("schema"):
                logger.debug("Returning cached table info")
                return self._table_info_cache
            
            self._ensure_connection()
            
            logger.info("Fetching table info from database")
            self._table_info_cache = self.db.get_table_info()
            self._schema_cache_timestamp = time.time()
            
            return self._table_info_cache
            
        except Exception as e:
            logger.error(f"Failed to get table info: {str(e)}")
            raise SchemaRetrievalError(f"Failed to retrieve table information: {str(e)}")
    
    def describe_table(self, table_name: str) -> str:
        """Get detailed description of a specific table"""
        try:
            self._ensure_connection()
            
            # Sanitize table name to prevent SQL injection
            if not re.match(r"^[\w\s$]+$", table_name, re.UNICODE):
                raise ValueError("Invalid table name")
            
            escaped_table = table_name.replace("'", "''")
            
            schema_query = f"""
            SELECT 
                COLUMN_NAME,
                DATA_TYPE,
                IS_NULLABLE,
                COLUMN_DEFAULT,
                CHARACTER_MAXIMUM_LENGTH
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = N'{escaped_table}'
            ORDER BY ORDINAL_POSITION
            """
            
            return self.execute_sql(schema_query)
            
        except Exception as e:
            logger.error(f"Failed to describe table {table_name}: {str(e)}")
            raise SchemaRetrievalError(f"Failed to describe table {table_name}: {str(e)}")
    
    def execute_sql(self, sql_query: str) -> str:
        """Execute SQL query with error handling"""
        try:
            self._ensure_connection()
            
            logger.debug(f"Executing SQL query: {sql_query[:100]}...")
            start_time = time.time()
            
            result = self.db.run(sql_query)
            
            execution_time = time.time() - start_time
            logger.debug(f"Query executed in {execution_time:.3f} seconds")
            
            return result
            
        except Exception as e:
            logger.error(f"SQL execution failed: {str(e)}")
            raise QueryExecutionError(f"Failed to execute SQL query: {str(e)}")
    
    def get_connection_status(self) -> dict:
        """Get detailed connection status"""
        return {
            "connected": self._connection_established,
            "cache_valid": self._is_cache_valid(),
            "schema_cache_valid": self._is_cache_valid("schema"),
            "cached_tables_count": len(self._table_names_cache) if self._table_names_cache else 0
        }