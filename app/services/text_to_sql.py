import time
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, date, timedelta
from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama

from app.services.schema_store import PersistentEnhancedSchemaVectorStore

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
            self.enhanced_schema_store = PersistentEnhancedSchemaVectorStore(self.database_service)

            logger.info(f"TextToSQLService initialized with {settings.DEFAULT_LLM_PROVIDER.upper()} LLM and Vector Database")
            
        except Exception as e:
            logger.error(f"Failed to initialize TextToSQLService: {str(e)}")
            self.enhanced_schema_store = None
    
    def _get_current_date_context(self) -> str:
        """Get current date context for SQL generation"""
        now = datetime.now()
        today = date.today()
        
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)
        year_start = today.replace(month=1, day=1)
        
        return f"""
CURRENT DATE CONTEXT (Use these exact values in SQL):
- Today: '{today.strftime('%Y-%m-%d')}'
- Current Year: {now.year}
- Current Month: {now.month}
- Current Day: {now.day}
- Week Start: '{week_start.strftime('%Y-%m-%d')}'
- Month Start: '{month_start.strftime('%Y-%m-%d')}'
- Year Start: '{year_start.strftime('%Y-%m-%d')}'
"""

    def _build_table_context_from_metadata(self, search_results: List) -> str:
        """Build detailed table context from vector search results"""
        context_parts = []
        
        for table_name, schema_text, metadata in search_results:
            context_parts.append(f"=== TABLE: {table_name} ===")
            
            if metadata and metadata.get("schema"):
                schema = metadata["schema"]
                
                context_parts.append(f"PURPOSE: {metadata.get('llm_analysis', {}).get('purpose', 'General data storage')}")
                
                # Build exact column list with emphasis
                context_parts.append("EXACT COLUMNS (USE THESE NAMES ONLY):")
                available_columns = []
                date_columns = []
                id_columns = []
                name_columns = []
                
                for col in schema.get("columns", []):
                    col_name = col['name']
                    col_type = col['type'].upper()
                    
                    col_info = f"  - {col_name} ({col['type']}"
                    if not col.get("nullable", True):
                        col_info += ", NOT NULL"
                    if col.get("autoincrement"):
                        col_info += ", AUTO_INCREMENT"
                    col_info += ")"
                    context_parts.append(col_info)
                    available_columns.append(col_name)
                    
                    # Categorize columns for easier reference
                    if ('DATE' in col_type or 'TIME' in col_type or 
                        col_name.lower().endswith('_at') or 
                        col_name.lower().endswith('_date') or 
                        'date' in col_name.lower()):
                        date_columns.append(col_name)
                    
                    if (col_name.lower().endswith('_id') or 
                        col_name.lower().endswith('id') or
                        'id' in col_name.lower()):
                        id_columns.append(col_name)
                    
                    if (col_name.lower().endswith('_name') or 
                        col_name.lower().endswith('name') or
                        'name' in col_name.lower()):
                        name_columns.append(col_name)
                
                # Add categorized column lists for easy reference
                context_parts.append(f"ALL COLUMN NAMES: {', '.join(available_columns)}")
                
                if date_columns:
                    context_parts.append(f"DATE COLUMNS (use for time queries): {', '.join(date_columns)}")
                if id_columns:
                    context_parts.append(f"ID COLUMNS (use for joins): {', '.join(id_columns)}")
                if name_columns:
                    context_parts.append(f"NAME COLUMNS (use for display): {', '.join(name_columns)}")
                
                if schema.get("primary_keys"):
                    context_parts.append(f"PRIMARY KEY: {', '.join(schema['primary_keys'])}")
                
                if schema.get("foreign_keys"):
                    context_parts.append("FOREIGN KEYS:")
                    for fk in schema["foreign_keys"]:
                        if isinstance(fk, dict):
                            context_parts.append(f"  - {fk.get('column')} -> {fk.get('referenced_table')}.{fk.get('referenced_column')}")
                        else:
                            context_parts.append(f"  - {str(fk)}")
                
                if schema.get("sample_data") and len(schema["sample_data"]) > 0:
                    context_parts.append("SAMPLE DATA (shows actual column names and values):")
                    sample = schema["sample_data"][0]
                    for key, value in list(sample.items())[:5]:  # Show first 5 columns
                        if value is not None:
                            context_parts.append(f"  {key}: {value}")
                
                analysis = metadata.get("llm_analysis", {})
                if analysis.get("data_patterns"):
                    context_parts.append(f"DATA PATTERNS: {'; '.join(analysis['data_patterns'][:2])}")
                
                if analysis.get("relationships"):
                    rel_info = []
                    for rel in analysis["relationships"][:2]:
                        if isinstance(rel, dict):
                            rel_info.append(f"{rel.get('table')} via {rel.get('relationship_type')}")
                        else:
                            rel_info.append(str(rel))
                    if rel_info:
                        context_parts.append(f"RELATIONSHIPS: {'; '.join(rel_info)}")
            
            context_parts.append("")
        
        return "\n".join(context_parts)

    def _create_enhanced_sql_prompt(self, table_context: str, user_query: str) -> str:
        """Create enhanced prompt using vector database metadata"""
        
        date_context = self._get_current_date_context()
        now = datetime.now()
        today = date.today()
        
        return f"""You are an expert SQL query generator for Microsoft SQL Server. 

ABSOLUTE REQUIREMENTS:
1. Return ONLY the SQL query - NO thinking, explanations, comments, or extra text
2. Do NOT use <think> tags or any explanatory text
3. Start your response directly with SELECT (or other SQL command)
4. Use ONLY the EXACT column names listed in the metadata below
5. DO NOT use placeholder names like 'date_column', 'id_column', etc.
6. DO NOT guess or assume column names - only use what's explicitly shown
7. Query must be 100% syntactically correct and executable

CRITICAL COLUMN USAGE:
- NEVER use generic names like 'date_column', 'id', 'name', etc.
- Use the EXACT column names from the "COLUMN NAMES:" sections
- For dates: Look for columns ending in '_at', '_date', or containing 'date'
- For IDs: Use the exact ID column names shown (like 'salary_id', 'qproj_id', etc.)
- For names: Use exact name columns shown (like 'employee_name', 'projectName', etc.)

T-SQL DATE FUNCTIONS (use with ACTUAL column names):
- Current month: WHERE MONTH(actual_date_column) = {now.month} AND YEAR(actual_date_column) = {now.year}
- Today: WHERE CAST(actual_date_column AS DATE) = '{today.strftime('%Y-%m-%d')}'
- This year: WHERE YEAR(actual_date_column) = {now.year}
- Date range: WHERE actual_date_column >= '2024-02-01' AND actual_date_column < '2025-03-01'

{date_context}

AVAILABLE TABLES WITH EXACT COLUMN NAMES:
{table_context}

USER QUERY: {user_query}

CRITICAL: Replace 'actual_date_column' with the real date column name from the tables above. Use ONLY the exact column names shown:"""

    def _validate_sql_columns(self, sql_query: str, search_results: List) -> tuple[bool, str]:
        """Validate that the SQL query only uses existing column names"""
        
        # Extract all available columns from metadata
        table_columns = {}
        all_columns = set()
        
        for table_name, schema_text, metadata in search_results:
            if metadata and metadata.get("schema"):
                schema = metadata["schema"]
                columns = [col['name'] for col in schema.get("columns", [])]
                table_columns[table_name.lower()] = columns
                all_columns.update([col.lower() for col in columns])
        
        # More comprehensive validation using regex
        import re
        
        validation_issues = []
        sql_lower = sql_query.lower()
        
        # Pattern 1: table.column references
        table_col_pattern = r'(\w+)\.(\w+)'
        matches = re.findall(table_col_pattern, sql_lower)
        
        for table_ref, column_ref in matches:
            # Find matching table (could be alias or actual table name)
            matching_table = None
            for table_name in table_columns.keys():
                if (table_ref == table_name.lower() or 
                    table_ref in table_name.lower() or 
                    table_name.lower().startswith(table_ref) or
                    # Check for common alias patterns
                    (len(table_ref) <= 3 and table_name.lower().startswith(table_ref))):
                    matching_table = table_name
                    break
            
            if matching_table:
                # Check if column exists in that table
                available_cols = [col.lower() for col in table_columns[matching_table]]
                if column_ref not in available_cols:
                    validation_issues.append(f"Column '{column_ref}' not found in table '{matching_table}'. Available: {', '.join(table_columns[matching_table])}")
        
        # Pattern 2: Standalone column references (more comprehensive)
        # Look for words that appear after SELECT, WHERE, JOIN ON, ORDER BY, GROUP BY
        sql_parts = re.split(r'\b(SELECT|FROM|WHERE|JOIN|ON|ORDER BY|GROUP BY|HAVING)\b', sql_query, flags=re.IGNORECASE)
        
        for i, part in enumerate(sql_parts):
            if i > 0 and sql_parts[i-1].upper() in ['SELECT', 'WHERE', 'ON', 'ORDER BY', 'GROUP BY']:
                # Extract potential column names from this part
                # Remove common SQL keywords and operators
                cleaned_part = re.sub(r'\b(AND|OR|NOT|IN|IS|NULL|LIKE|BETWEEN|AS|ASC|DESC|DISTINCT|TOP|COUNT|SUM|AVG|MAX|MIN)\b', '', part, flags=re.IGNORECASE)
                
                # Find word patterns that could be column names
                potential_columns = re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b', cleaned_part)
                
                for col in potential_columns:
                    col_lower = col.lower()
                    # Skip common SQL keywords and table names
                    if (col_lower not in ['select', 'from', 'where', 'join', 'on', 'order', 'by', 'group', 'having', 'and', 'or', 'not', 'in', 'is', 'null', 'like', 'between', 'as', 'asc', 'desc', 'distinct', 'top', 'count', 'sum', 'avg', 'max', 'min'] and
                        col_lower not in [t.lower() for t in table_columns.keys()] and
                        len(col) > 2):  # Ignore very short words
                        
                        # Check if this column exists in any table
                        if col_lower not in all_columns:
                            # Check for common incorrect patterns
                            common_mistakes = {
                                'fk_proj_id': 'Check available foreign key columns',
                                'project_id': 'Check available project reference columns', 
                                'fk_project_id': 'Check available project foreign key columns',
                                'user_id': 'Check available user reference columns',
                                'fk_user_id': 'Check available user foreign key columns'
                            }
                            
                            if col_lower in common_mistakes:
                                validation_issues.append(f"Column '{col}' not found. {common_mistakes[col_lower]}")
                            else:
                                # Only flag if it really looks like a column name
                                if '_' in col or col.endswith('id') or col.endswith('name') or col.endswith('date'):
                                    validation_issues.append(f"Column '{col}' not found in any available table")
        
        if validation_issues:
            return False, "; ".join(validation_issues[:3])  # Limit to first 3 issues
        
        return True, "Valid"

    async def process_query(self, command: str, include_sql: bool = True) -> QueryResponse:
        start_time = time.time()
        
        logger.info(f"Processing query with vector database: {command[:50]}...")
        
        try:
            if not self.enhanced_schema_store or not self.enhanced_schema_store.is_metadata_loaded:
                logger.warning("Vector database not available, falling back to basic schema")
                return await self._process_query_fallback(command, include_sql)
            
            logger.info("Searching vector database for relevant tables...")
            search_results = self.enhanced_schema_store.search(command, k=8)
            
            if not search_results:
                logger.warning("No relevant tables found in vector database")
                return QueryResponse(
                    success=False,
                    command=command,
                    error="No relevant tables found for this query",
                    execution_time=round(time.time() - start_time, 3)
                )
            
            logger.info(f"Found {len(search_results)} relevant tables: {[r[0] for r in search_results]}")
            
            table_context = self._build_table_context_from_metadata(search_results)
            
            # Log the table context for debugging
            logger.info("=== AVAILABLE TABLES AND COLUMNS ===")
            for table_name, schema_text, metadata in search_results:
                if metadata and metadata.get("schema"):
                    schema = metadata["schema"]
                    columns = [col['name'] for col in schema.get("columns", [])]
                    logger.info(f"Table '{table_name}': {', '.join(columns)}")
            logger.info("=== END TABLE INFO ===")
            
            logger.debug(f"Table context built: {table_context[:500]}...")
            
            prompt_text = self._create_enhanced_sql_prompt(table_context, command)
            
            if hasattr(self.llm, 'ainvoke'):
                sql_response = await self.llm.ainvoke(prompt_text)
            else:
                sql_response = self.llm.invoke(prompt_text)
            
            if hasattr(sql_response, 'content'):
                sql_query = sql_response.content
            elif isinstance(sql_response, dict) and 'content' in sql_response:
                sql_query = sql_response['content']
            else:
                sql_query = str(sql_response)
            
            sql_query = self._clean_sql_output(sql_query)
            
            if not sql_query.strip():
                raise Exception("Generated SQL query is empty")
            
            # Validate the SQL query against metadata
            is_valid, validation_message = self._validate_sql_columns(sql_query, search_results)
            
            if not is_valid:
                logger.warning(f"SQL validation failed: {validation_message}")
                # Log the invalid query for debugging
                logger.warning(f"Invalid SQL generated: {sql_query}")
                
                # Try to provide helpful error message
                error_msg = f"Generated SQL contains invalid column names: {validation_message}"
                return QueryResponse(
                    success=False,
                    command=command,
                    error=error_msg,
                    sql_query=sql_query if include_sql else None,
                    execution_time=round(time.time() - start_time, 3)
                )
            
            execution_time = time.time() - start_time
            
            logger.info(f"SQL query generated and validated successfully in {execution_time:.3f} seconds")
            logger.info(f"Generated SQL: {sql_query[:200]}...")
            
            return QueryResponse(
                success=True,
                command=command,
                sql_query=sql_query if include_sql else None,
                result=sql_query,
                execution_time=round(execution_time, 3)
            )
        
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = str(e)
            
            logger.error(f"SQL generation failed: {error_msg}")
            
            return QueryResponse(
                success=False,
                command=command,
                error=error_msg,
                execution_time=round(execution_time, 3)
            )

    async def _process_query_fallback(self, command: str, include_sql: bool = True) -> QueryResponse:
        """Fallback method when vector database is not available"""
        try:
            table_names = self.sql_db.get_usable_table_names()[:10]
            basic_context = f"Available tables: {', '.join(table_names)}"
            
            prompt_text = self._create_enhanced_sql_prompt(basic_context, command)
            
            if hasattr(self.llm, 'ainvoke'):
                sql_response = await self.llm.ainvoke(prompt_text)
            else:
                sql_response = self.llm.invoke(prompt_text)
            
            if hasattr(sql_response, 'content'):
                sql_query = sql_response.content
            else:
                sql_query = str(sql_response)
            
            sql_query = self._clean_sql_output(sql_query)
            
            return QueryResponse(
                success=True,
                command=command,
                sql_query=sql_query if include_sql else None,
                result=sql_query,
                execution_time=round(time.time() - time.time(), 3)
            )
        
        except Exception as e:
            return QueryResponse(
                success=False,
                command=command,
                error=f"Fallback query generation failed: {str(e)}",
                execution_time=0
            )

    def _clean_sql_output(self, sql_output: str) -> str:
        """Clean the SQL output to ensure it contains only the SQL query"""
        
        sql_output = sql_output.strip()
        
        # Remove thinking tags and content
        if "<think>" in sql_output.lower():
            # Find the end of thinking section
            think_end = sql_output.lower().find("</think>")
            if think_end != -1:
                sql_output = sql_output[think_end + 8:].strip()
            else:
                # If no closing tag, remove from <think> onwards until we find SQL
                think_start = sql_output.lower().find("<think>")
                if think_start != -1:
                    before_think = sql_output[:think_start].strip()
                    after_think = sql_output[think_start:].strip()
                    
                    # Look for SELECT after <think>
                    select_pos = after_think.upper().find("SELECT")
                    if select_pos != -1:
                        sql_output = after_think[select_pos:].strip()
                    else:
                        sql_output = before_think
        
        # Remove markdown code blocks
        if sql_output.startswith("```sql"):
            sql_output = sql_output[6:]
        if sql_output.startswith("```"):
            sql_output = sql_output[3:]
        if sql_output.endswith("```"):
            sql_output = sql_output[:-3]
        
        # Remove any trailing markdown or artifacts
        lines = sql_output.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if line.startswith('```') or line.endswith('```'):
                continue
            if line:
                cleaned_lines.append(line)
        
        sql_output = '\n'.join(cleaned_lines)
        
        # Remove common prefixes
        prefixes_to_remove = [
            "Here's the SQL query:",
            "Here is the SQL query:",
            "The SQL query is:",
            "SQL Query:",
            "Query:",
            "SQL:",
            "T-SQL:",
            "Generate the SQL query using the exact table and column names from the metadata above:",
        ]
        
        for prefix in prefixes_to_remove:
            if sql_output.lower().startswith(prefix.lower()):
                sql_output = sql_output[len(prefix):].strip()
        
        # Process line by line to extract only SQL
        lines = sql_output.split('\n')
        sql_lines = []
        found_sql_start = False
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Skip comment lines
            if line.startswith('--'):
                continue
            
            # Skip thinking or explanation content
            if ("<think>" in line.lower() or "</think>" in line.lower() or
                line.lower().startswith("okay,") or
                line.lower().startswith("first,") or
                line.lower().startswith("let me") or
                line.lower().startswith("i need to")):
                continue
                
            # Stop at explanation indicators
            explanation_indicators = [
                "this query",
                "the above",
                "explanation:",
                "note:",
                "this will",
                "this returns",
                "the result",
                "this sql",
                "let me break",
                "here's what"
            ]
            
            if any(indicator in line.lower() for indicator in explanation_indicators):
                break
            
            # Check if this looks like SQL
            if (line.upper().startswith(('SELECT', 'WITH', 'INSERT', 'UPDATE', 'DELETE'))):
                found_sql_start = True
                sql_lines.append(line)
            elif found_sql_start and (
                line.upper().startswith(('FROM', 'WHERE', 'JOIN', 'INNER JOIN', 'LEFT JOIN', 'RIGHT JOIN', 
                                        'ORDER BY', 'GROUP BY', 'HAVING', 'UNION', 'EXCEPT', 'INTERSECT')) or
                line.strip().endswith((';', ',', ')', '(')) or
                'FROM' in line.upper() or 'WHERE' in line.upper() or
                any(keyword in line.upper() for keyword in ['AND', 'OR', 'ON', 'AS', 'TOP', 'DISTINCT', 'COUNT', 'SUM', 'AVG', 'MAX', 'MIN'])):
                sql_lines.append(line)
            elif found_sql_start and sql_lines:
                # Continue adding lines if we're in the middle of a SQL query
                sql_lines.append(line)
        
        # If we found SQL lines, use them
        if sql_lines:
            sql_output = '\n'.join(sql_lines)
        else:
            # Last resort: try to find SELECT statement
            select_pos = sql_output.upper().find("SELECT")
            if select_pos != -1:
                sql_output = sql_output[select_pos:]
                # Cut off at first explanation
                for indicator in ["this query", "explanation:", "note:", "here's what"]:
                    pos = sql_output.lower().find(indicator)
                    if pos != -1:
                        sql_output = sql_output[:pos].strip()
                        break
        
        sql_output = sql_output.strip()
        
        # Remove trailing semicolon
        if sql_output.endswith(';'):
            sql_output = sql_output[:-1].strip()
        
        return sql_output
    
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
                stats["table_names"] = self.enhanced_schema_store.table_names[:10]
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