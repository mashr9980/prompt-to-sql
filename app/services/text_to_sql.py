import time
import logging
from typing import Optional, Dict, Any
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent

from app.services.schema_store import PersistentEnhancedSchemaVectorStore

# from .persistent_vector_store import PersistentEnhancedSchemaVectorStore

from ..schemas.query import QueryResponse
from ..schemas.database import TableInfo
from ..services.database import DatabaseService
from ..config import settings
from ..core.exceptions import QueryExecutionError, LLMServiceError

logger = logging.getLogger(__name__)


class TextToSQLService:
    
    def __init__(self, llm_service, database_service: DatabaseService):
        self.database_service = database_service
        self.llm_service = llm_service
        
        try:
            if settings.DEFAULT_LLM_PROVIDER.lower() == "ollama":
                logger.info("Initializing Ollama LLM for text-to-SQL")
                self.llm = ChatOllama(
                    model=settings.OLLAMA_MODEL,
                    base_url=settings.OLLAMA_BASE_URL,
                    temperature=settings.OLLAMA_TEMPERATURE,
                    num_predict=settings.OLLAMA_MAX_TOKENS
                )
            else:
                logger.info("Initializing OpenAI LLM for text-to-SQL")
                self.llm = ChatOpenAI(
                    model=settings.OPENAI_MODEL,
                    temperature=settings.OPENAI_TEMPERATURE,
                    api_key=settings.OPENAI_API_KEY,
                    max_tokens=settings.OPENAI_MAX_TOKENS
                )

            self.sql_db = SQLDatabase.from_uri(settings.DATABASE_URL)
            self.toolkit = SQLDatabaseToolkit(db=self.sql_db, llm=self.llm)
            self.tools = self.toolkit.get_tools()

            self.enhanced_schema_store = PersistentEnhancedSchemaVectorStore(self.database_service)

            self.base_system_message = self._create_system_message()

            logger.info(f"TextToSQLService initialized with {settings.DEFAULT_LLM_PROVIDER.upper()} LLM and Persistent Enhanced Schema Store")
            
        except Exception as e:
            logger.error(f"Failed to initialize TextToSQLService: {str(e)}")
            self.enhanced_schema_store = None
    
    def _create_system_message(self, schema_context: str = "") -> str:
        base = f"""
        You are an agent designed to interact with a Microsoft SQL Server database.
        Given an input question, create a syntactically correct T-SQL query to run,
        then look at the results of the query and return the answer. Unless the user
        specifies a specific number of examples they wish to obtain, always limit your
        query to at most 10 results.

        You can order the results by a relevant column to return the most interesting
        examples in the database. Never query for all the columns from a specific table,
        only ask for the relevant columns given the question.

        You MUST double check your query before executing it. If you get an error while
        executing a query, rewrite the query and try again.

        DO NOT make any DML statements (INSERT, UPDATE, DELETE, DROP etc.) to the
        database.

        To start you should ALWAYS look at the tables in the database to see what you
        can query. Do NOT skip this step.
        Then you should query the schema of the most relevant tables.

        IMPORTANT T-SQL SPECIFIC RULES:
        1. Use square brackets [] for table/column names with spaces or special characters
        2. Use TOP instead of LIMIT
        3. For Arabic text searches, use LIKE with COLLATE SQL_Latin1_General_CP1_CI_AS
        4. Handle mixed language content appropriately
        5. Use proper T-SQL syntax and functions
        6. Consider NULL values in conditions
        7. Use appropriate JOINs when querying multiple related tables
        8. For date queries, use proper DATETIME formatting
        9. For money/financial queries, use MONEY data type appropriately
        10. Always use column names that actually exist in the database schema

        CONTEXT: This is a business management system with:
        - Arabic/English mixed content
        - Project management (projects, PO, quotations)
        - Employee management (attendance, salaries, tasks)
        - Inventory management
        - Financial transactions
        - Supplier management
        - Cafe/restaurant operations

        ENHANCED METADATA CONTEXT:
        The system has access to comprehensive table metadata including:
        - Detailed column information with types and constraints
        - Primary and foreign key relationships
        - LLM analysis describing table purposes and data patterns
        - Sample data patterns and observations
        - Relationship mappings between tables
        
        Use this enhanced context to make more informed decisions about which tables
        to query and how to structure your queries for maximum accuracy.
        """

        if schema_context:
            base += "\n\nRELEVANT SCHEMA CONTEXT:\n" + schema_context

        return base
    
    def get_quick_health_status(self) -> dict:
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
        start_time = time.time()
        
        logger.info(f"Processing query with {settings.DEFAULT_LLM_PROVIDER.upper()} LLM: {command[:50]}...")
        
        try:
            schema_context = ""
            
            if self.enhanced_schema_store and self.enhanced_schema_store.is_metadata_loaded:
                logger.info("Using enhanced metadata for query processing")
                results = self.enhanced_schema_store.search(command, k=5)
                
                context_parts = []
                for table_name, schema_text, metadata in results:
                    context_parts.append(f"--- {table_name} ---")
                    context_parts.append(schema_text)
                    
                    if metadata.get("llm_analysis"):
                        analysis = metadata["llm_analysis"]
                        if analysis.get("purpose"):
                            context_parts.append(f"Purpose: {analysis['purpose']}")
                        if analysis.get("data_patterns"):
                            context_parts.append(f"Patterns: {'; '.join(analysis['data_patterns'])}")
                        if analysis.get("relationships"):
                            rel_texts = []
                            for rel in analysis['relationships']:
                                if isinstance(rel, dict):
                                    rel_texts.append(f"Related to {rel.get('table', '')} via {rel.get('relationship_type', '')}")
                                else:
                                    rel_texts.append(str(rel))
                            if rel_texts:
                                context_parts.append(f"Relationships: {'; '.join(rel_texts)}")
                    
                    context_parts.append("")
                
                schema_context = "\n".join(context_parts)
                logger.info(f"Enhanced context prepared with {len(results)} relevant tables")
            else:
                logger.info("Using basic schema store for query processing")
                if hasattr(self, 'schema_store'):
                    results = self.schema_store.search(command, k=5)
                    schema_context = "\n".join([s for _, s in results])

            prompt = self._create_system_message(schema_context)
            agent = create_react_agent(
                self.llm,
                self.tools,
                prompt=prompt,
            )

            messages = [{"role": "user", "content": command}]
            
            final_message = None
            sql_query = None
            
            for step in agent.stream(
                {"messages": messages},
                stream_mode="values",
            ):
                final_message = step["messages"][-1]
            
            if hasattr(final_message, 'content'):
                result = final_message.content
            else:
                result = str(final_message)
            
            if include_sql:
                try:
                    for step in agent.stream(
                        {"messages": messages},
                        stream_mode="updates",
                    ):
                        if "agent" in step:
                            for message in step["agent"]["messages"]:
                                if hasattr(message, 'tool_calls') and message.tool_calls:
                                    for tool_call in message.tool_calls:
                                        if tool_call["name"] == "sql_db_query":
                                            sql_query = tool_call["args"].get("query", "")
                                            break
                except Exception as e:
                    logger.warning(f"Could not extract SQL query: {e}")
                    pass
            
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
        start_time = time.time()
        
        logger.info(f"Executing direct SQL: {sql_query[:50]}...")
        
        try:
            result = self.sql_db.run(sql_query)
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
        try:
            logger.debug("Retrieving database information")
            
            table_names = self.sql_db.get_usable_table_names()
            schema_info = self.sql_db.get_table_info()
            
            return TableInfo(
                table_names=table_names,
                schema_info=schema_info
            )
         
        except Exception as e:
            logger.error(f"Failed to get database info: {str(e)}")
            raise QueryExecutionError(f"Failed to retrieve database information: {str(e)}")
    
    def get_table_description(self, table_name: str) -> dict:
        try:
            logger.debug(f"Getting description for table: {table_name}")
            
            result = self.sql_db.get_table_info([table_name])
            
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
        try:
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
            
            if include_table_count:
                try:
                    table_names = self.sql_db.get_usable_table_names()
                    result["tables_count"] = len(table_names)
                except Exception as e:
                    logger.warning(f"Could not get table count: {str(e)}")
                    result["tables_count"] = None
            
            if self.enhanced_schema_store:
                kb_status = self.enhanced_schema_store.get_status()
                result["knowledge_base"] = {
                    "metadata_loaded": kb_status["metadata_loaded"],
                    "indexed_tables": kb_status["total_tables"],
                    "upload_time": kb_status["upload_time"]
                }
            
            return result
        
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "database_connected": False,
                "error": str(e)
            }
    
    def get_enhanced_schema_store(self):
        """Get the enhanced schema store instance"""
        return self.enhanced_schema_store
    
    def rebuild_knowledge_base(self):
        """Rebuild the knowledge base vector index"""
        if self.enhanced_schema_store:
            try:
                self.enhanced_schema_store.rebuild_index()
                logger.info("Knowledge base rebuilt successfully")
                return {"success": True, "message": "Knowledge base rebuilt successfully"}
            except Exception as e:
                logger.error(f"Failed to rebuild knowledge base: {e}")
                return {"success": False, "error": str(e)}
        else:
            return {"success": False, "error": "Enhanced schema store not available"}
    
    def clear_knowledge_base(self):
        """Clear the knowledge base completely"""
        if self.enhanced_schema_store:
            try:
                self.enhanced_schema_store.clear_all()
                logger.info("Knowledge base cleared successfully")
                return {"success": True, "message": "Knowledge base cleared successfully"}
            except Exception as e:
                logger.error(f"Failed to clear knowledge base: {e}")
                return {"success": False, "error": str(e)}
        else:
            return {"success": False, "error": "Enhanced schema store not available"}
    
    def get_knowledge_base_stats(self) -> dict:
        """Get detailed statistics about the knowledge base"""
        if not self.enhanced_schema_store:
            return {
                "available": False,
                "error": "Enhanced schema store not available"
            }
        
        try:
            status = self.enhanced_schema_store.get_status()
            
            stats = {
                "available": True,
                "metadata_loaded": status["metadata_loaded"],
                "total_tables": status["total_tables"],
                "index_built": status["index_built"],
                "upload_time": status["upload_time"],
                "storage_path": status["storage_path"],
                "files_exist": status["files_exist"]
            }
            
            if status["metadata_loaded"]:
                stats["table_names"] = self.enhanced_schema_store.table_names[:10]  # First 10 table names
                stats["sample_purposes"] = []
                
                for table_name in self.enhanced_schema_store.table_names[:5]:
                    details = self.enhanced_schema_store.get_table_details(table_name)
                    if details and details.get("llm_analysis", {}).get("purpose"):
                        stats["sample_purposes"].append({
                            "table": table_name,
                            "purpose": details["llm_analysis"]["purpose"]
                        })
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get knowledge base stats: {e}")
            return {
                "available": True,
                "error": str(e)
            }
    
    def search_knowledge_base(self, query: str, limit: int = 5) -> dict:
        """Search the knowledge base for relevant tables"""
        if not self.enhanced_schema_store:
            return {
                "success": False,
                "error": "Enhanced schema store not available"
            }
        
        if not self.enhanced_schema_store.is_metadata_loaded:
            return {
                "success": False,
                "error": "No metadata loaded in knowledge base"
            }
        
        try:
            results = self.enhanced_schema_store.search(query, k=limit)
            
            formatted_results = []
            for table_name, schema_text, metadata in results:
                result_item = {
                    "table_name": table_name,
                    "schema_summary": schema_text[:300] + "..." if len(schema_text) > 300 else schema_text
                }
                
                if metadata.get("llm_analysis"):
                    analysis = metadata["llm_analysis"]
                    result_item["purpose"] = analysis.get("purpose", "")
                    result_item["data_patterns"] = analysis.get("data_patterns", [])
                    result_item["relationships"] = analysis.get("relationships", [])
                    result_item["observations"] = analysis.get("observations", [])
                
                formatted_results.append(result_item)
            
            return {
                "success": True,
                "query": query,
                "results": formatted_results,
                "total_found": len(formatted_results)
            }
            
        except Exception as e:
            logger.error(f"Failed to search knowledge base: {e}")
            return {
                "success": False,
                "error": str(e)
            }