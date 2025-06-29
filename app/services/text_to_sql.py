import time
import logging
import json
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, date, timedelta
from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langchain_google_genai import ChatGoogleGenerativeAI

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
                self.llm = ChatOllama(
                    model=settings.OLLAMA_MODEL,
                    base_url=settings.OLLAMA_BASE_URL,
                    temperature=0.0,
                    num_predict=settings.OLLAMA_MAX_TOKENS
                )
            elif settings.DEFAULT_LLM_PROVIDER.lower() == "gemini":
                self.llm = ChatGoogleGenerativeAI(
                    model=settings.GEMINI_MODEL,
                    temperature=0.0,
                    google_api_key=settings.GEMINI_API_KEY,
                    max_output_tokens=settings.GEMINI_MAX_TOKENS
                )
            else:
                self.llm = ChatOpenAI(
                    model=settings.OPENAI_MODEL,
                    temperature=0.0,
                    api_key=settings.OPENAI_API_KEY,
                    max_tokens=settings.OPENAI_MAX_TOKENS
                )

            self.sql_db = SQLDatabase.from_uri(settings.DATABASE_URL)
            self.enhanced_schema_store = PersistentEnhancedSchemaVectorStore(self.database_service)

            logger.info(f"TextToSQLService initialized with {settings.DEFAULT_LLM_PROVIDER.upper()} LLM")
            
        except Exception as e:
            logger.error(f"Failed to initialize TextToSQLService: {str(e)}")
            self.enhanced_schema_store = None
    
    def _get_current_date_context(self) -> str:
        now = datetime.now()
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)
        year_start = today.replace(month=1, day=1)
        
        return f"""Current Date and Time Information:
Today's Date: {today.strftime('%Y-%m-%d')}
Current Year: {now.year}
Current Month: {now.month} ({now.strftime('%B')})
Current Day: {now.day}
Current Time: {now.strftime('%H:%M:%S')}
Week Start (Monday): {week_start.strftime('%Y-%m-%d')}
Month Start: {month_start.strftime('%Y-%m-%d')}
Year Start: {year_start.strftime('%Y-%m-%d')}
Day of Week: {now.strftime('%A')}"""

    async def _analyze_user_intent(self, user_query: str) -> Dict[str, Any]:
        """Use LLM to analyze user intent and requirements"""
        
        intent_prompt = f"""Analyze this database query request and extract the user's intent and requirements.

User Query: "{user_query}"

Analyze and provide a JSON response with the following structure:
{{
    "query_type": "select|insert|update|delete|aggregate|reporting",
    "main_entities": ["entity1", "entity2"],
    "time_filters": {{
        "has_time_filter": true/false,
        "time_period": "today|this_week|this_month|this_year|specific_date|date_range",
        "time_description": "description of time requirement"
    }},
    "aggregations": {{
        "has_aggregation": true/false,
        "functions": ["count", "sum", "avg", "max", "min"],
        "group_by_needed": true/false
    }},
    "filters": {{
        "has_filters": true/false,
        "filter_types": ["comparison", "contains", "equals", "range"],
        "filter_description": "description of filtering needs"
    }},
    "relationships": {{
        "needs_joins": true/false,
        "relationship_description": "description of data relationships needed"
    }},
    "output_requirements": {{
        "limit_needed": true/false,
        "suggested_limit": 100,
        "sorting_needed": true/false,
        "sort_description": "description of sorting requirements"
    }},
    "business_context": "description of what user wants to achieve"
}}

Provide only the JSON response:"""

        try:
            if hasattr(self.llm, 'ainvoke'):
                response = await self.llm.ainvoke(intent_prompt)
            else:
                response = self.llm.invoke(intent_prompt)
            
            if hasattr(response, 'content'):
                analysis_text = response.content
            else:
                analysis_text = str(response)
            
            try:
                analysis_text = analysis_text.strip()
                if analysis_text.startswith('```json'):
                    analysis_text = analysis_text[7:]
                if analysis_text.startswith('```'):
                    analysis_text = analysis_text[3:]
                if analysis_text.endswith('```'):
                    analysis_text = analysis_text[:-3]
                
                return json.loads(analysis_text.strip())
            except json.JSONDecodeError:
                logger.warning("Failed to parse intent analysis JSON")
                return self._get_default_intent()
                
        except Exception as e:
            logger.warning(f"Intent analysis failed: {e}")
            return self._get_default_intent()

    def _get_default_intent(self) -> Dict[str, Any]:
        """Default intent structure when LLM analysis fails"""
        return {
            "query_type": "select",
            "main_entities": [],
            "time_filters": {"has_time_filter": False, "time_period": "", "time_description": ""},
            "aggregations": {"has_aggregation": False, "functions": [], "group_by_needed": False},
            "filters": {"has_filters": False, "filter_types": [], "filter_description": ""},
            "relationships": {"needs_joins": False, "relationship_description": ""},
            "output_requirements": {"limit_needed": True, "suggested_limit": 100, "sorting_needed": False, "sort_description": ""},
            "business_context": "General data retrieval"
        }

    async def _select_relevant_tables(self, user_query: str, search_results: List[Tuple], intent_analysis: Dict) -> List[Tuple]:
        """Use LLM to intelligently select the most relevant tables"""
        
        if not search_results:
            return []
        
        table_descriptions = []
        for i, (table_name, schema_text, metadata) in enumerate(search_results):
            purpose = metadata.get('llm_analysis', {}).get('purpose', 'Data storage') if metadata else 'Data storage'
            columns = []
            if metadata and metadata.get("schema"):
                columns = [col['name'] for col in metadata["schema"].get("columns", [])]
            
            table_descriptions.append(f"{i+1}. {table_name}: {purpose} (Key columns: {', '.join(columns[:8])})")
        
        selection_prompt = f"""You are a database expert. Select the most relevant tables for this query.

User Query: "{user_query}"

User Intent Analysis: {json.dumps(intent_analysis, indent=2)}

Available Tables:
{chr(10).join(table_descriptions)}

Instructions:
1. Analyze which tables are most relevant to answer the user's query
2. Consider the user's intent and requirements
3. Select 3-5 most relevant tables
4. Prioritize tables that contain the main entities and required data

Respond with a JSON array of the most relevant table numbers (1-{len(search_results)}):
Example: [1, 3, 5]

Selected table numbers:"""

        try:
            if hasattr(self.llm, 'ainvoke'):
                response = await self.llm.ainvoke(selection_prompt)
            else:
                response = self.llm.invoke(selection_prompt)
            
            if hasattr(response, 'content'):
                selection_text = response.content
            else:
                selection_text = str(response)
            
            try:
                selection_text = selection_text.strip()
                if selection_text.startswith('```json'):
                    selection_text = selection_text[7:]
                if selection_text.startswith('```'):
                    selection_text = selection_text[3:]
                if selection_text.endswith('```'):
                    selection_text = selection_text[:-3]
                
                selected_indices = json.loads(selection_text.strip())
                
                if isinstance(selected_indices, list):
                    selected_tables = []
                    for idx in selected_indices:
                        if isinstance(idx, int) and 1 <= idx <= len(search_results):
                            selected_tables.append(search_results[idx - 1])
                    return selected_tables[:5]
                
            except (json.JSONDecodeError, ValueError):
                logger.warning("Failed to parse table selection")
        
        except Exception as e:
            logger.warning(f"Table selection failed: {e}")
        
        return search_results[:5]

    def _build_comprehensive_schema_context(self, selected_tables: List[Tuple]) -> str:
        """Build detailed schema context for selected tables"""
        
        context_parts = ["COMPREHENSIVE DATABASE SCHEMA INFORMATION:"]
        context_parts.append("=" * 60)
        
        for table_name, schema_text, metadata in selected_tables:
            context_parts.append(f"\nTABLE: {table_name}")
            context_parts.append("-" * 40)
            
            if metadata and metadata.get("schema"):
                schema = metadata["schema"]
                
                purpose = metadata.get('llm_analysis', {}).get('purpose', 'Data storage table')
                context_parts.append(f"Business Purpose: {purpose}")
                
                context_parts.append("Column Definitions:")
                for col in schema.get("columns", []):
                    col_name = col['name']
                    col_type = col['type']
                    nullable = "NULL" if col.get("nullable", True) else "NOT NULL"
                    extra_info = ""
                    if col.get("autoincrement"):
                        extra_info += " AUTO_INCREMENT"
                    context_parts.append(f"  - {col_name}: {col_type} ({nullable}){extra_info}")
                
                if schema.get("primary_keys"):
                    context_parts.append(f"Primary Key: {', '.join(schema['primary_keys'])}")
                
                if schema.get("foreign_keys"):
                    context_parts.append("Foreign Key Relationships:")
                    for fk in schema["foreign_keys"]:
                        if isinstance(fk, dict):
                            context_parts.append(f"  - {fk.get('column')} references {fk.get('referenced_table')}.{fk.get('referenced_column')}")
                
                if schema.get("sample_data") and len(schema["sample_data"]) > 0:
                    context_parts.append("Sample Data (showing data patterns):")
                    sample = schema["sample_data"][0]
                    for key, value in list(sample.items())[:5]:
                        if value is not None:
                            context_parts.append(f"  - {key}: {repr(value)}")
                
                analysis = metadata.get("llm_analysis", {})
                if analysis.get("data_patterns"):
                    context_parts.append("Data Patterns:")
                    for pattern in analysis["data_patterns"][:3]:
                        context_parts.append(f"  - {pattern}")
                
                if analysis.get("relationships"):
                    context_parts.append("Business Relationships:")
                    for rel in analysis["relationships"][:2]:
                        if isinstance(rel, dict):
                            context_parts.append(f"  - Related to {rel.get('table')} via {rel.get('relationship_type')}")
                        else:
                            context_parts.append(f"  - {str(rel)}")
        
        return "\n".join(context_parts)

    async def _generate_optimized_sql(self, user_query: str, intent_analysis: Dict, schema_context: str, date_context: str) -> str:
        """Use LLM to generate optimized SQL with comprehensive context"""
        
        sql_generation_prompt = f"""You are an expert Microsoft SQL Server T-SQL developer. Generate the perfect SQL query based on the comprehensive analysis below.

USER REQUEST: "{user_query}"

USER INTENT ANALYSIS:
{json.dumps(intent_analysis, indent=2)}

{date_context}

{schema_context}

CRITICAL SQL GENERATION REQUIREMENTS:
1. Use ONLY the exact table names and column names from the schema above
2. Generate syntactically perfect Microsoft SQL Server T-SQL
3. Use appropriate JOINs when data spans multiple tables
4. Include proper WHERE clauses for filtering and date conditions
5. Add aggregation functions (COUNT, SUM, AVG, MAX, MIN) if needed
6. Include GROUP BY clauses when using aggregations
7. Add ORDER BY clauses for sorting when appropriate
8. Use TOP clause to limit results (default TOP 100 unless specified)
9. Handle date/time filtering using proper SQL Server date functions
10. Use full table names in format: TableName.ColumnName
11. Do NOT use table aliases or AS clauses for tables
12. Generate clean, executable, production-ready SQL

IMPORTANT NOTES:
- For date filtering, use appropriate functions like CAST, CONVERT, GETDATE(), DATEADD(), DATEDIFF()
- For "today" queries, use: WHERE CAST(DateColumn AS DATE) = CAST(GETDATE() AS DATE)
- For "this month" queries, use: WHERE MONTH(DateColumn) = MONTH(GETDATE()) AND YEAR(DateColumn) = YEAR(GETDATE())
- For aggregations, always include GROUP BY for non-aggregated columns
- Join tables using their foreign key relationships shown in the schema

Generate the SQL query that perfectly fulfills the user's request:"""

        if hasattr(self.llm, 'ainvoke'):
            response = await self.llm.ainvoke(sql_generation_prompt)
        else:
            response = self.llm.invoke(sql_generation_prompt)
        
        if hasattr(response, 'content'):
            return response.content
        return str(response)

    async def _validate_sql_with_llm(self, sql_query: str, schema_context: str, available_tables: List[str]) -> Tuple[bool, str]:
        """Use LLM to validate the generated SQL"""
        
        table_names = [table[0] for table in available_tables] if isinstance(available_tables[0], tuple) else available_tables
        
        validation_prompt = f"""You are a SQL validation expert. Validate this SQL query against the provided schema.

SQL QUERY TO VALIDATE:
{sql_query}

{schema_context}

AVAILABLE TABLE NAMES: {', '.join(table_names)}

VALIDATION REQUIREMENTS:
1. Check if all table names in the SQL exist in the available tables
2. Check if all column names exist in their respective tables
3. Verify JOIN conditions use valid foreign key relationships
4. Ensure syntax is correct for Microsoft SQL Server
5. Check for any syntax errors or invalid constructs

Respond with a JSON object:
{{
    "is_valid": true/false,
    "errors": ["error1", "error2"],
    "suggestions": ["suggestion1", "suggestion2"]
}}

Validation result:"""

        try:
            if hasattr(self.llm, 'ainvoke'):
                response = await self.llm.ainvoke(validation_prompt)
            else:
                response = self.llm.invoke(validation_prompt)
            
            if hasattr(response, 'content'):
                validation_text = response.content
            else:
                validation_text = str(response)
            
            try:
                validation_text = validation_text.strip()
                if validation_text.startswith('```json'):
                    validation_text = validation_text[7:]
                if validation_text.startswith('```'):
                    validation_text = validation_text[3:]
                if validation_text.endswith('```'):
                    validation_text = validation_text[:-3]
                
                validation_result = json.loads(validation_text.strip())
                
                is_valid = validation_result.get("is_valid", False)
                errors = validation_result.get("errors", [])
                error_message = "; ".join(errors) if errors else ""
                
                return is_valid, error_message
                
            except json.JSONDecodeError:
                logger.warning("Failed to parse validation result")
                return False, "Validation parsing failed"
                
        except Exception as e:
            logger.warning(f"LLM validation failed: {e}")
            return False, f"Validation error: {str(e)}"

    async def _fix_sql_with_llm(self, user_query: str, sql_query: str, validation_errors: str, schema_context: str, intent_analysis: Dict) -> str:
        """Use LLM to fix SQL based on validation errors"""
        
        fix_prompt = f"""You are a SQL repair expert. Fix the SQL query based on the validation errors.

ORIGINAL USER REQUEST: "{user_query}"

USER INTENT: {json.dumps(intent_analysis, indent=2)}

BROKEN SQL QUERY:
{sql_query}

VALIDATION ERRORS:
{validation_errors}

{schema_context}

INSTRUCTIONS:
1. Fix all the validation errors mentioned above
2. Use ONLY the exact table and column names from the schema
3. Maintain the original intent and logic of the query
4. Generate syntactically correct Microsoft SQL Server T-SQL
5. Do NOT use table aliases
6. Use full table names in format: TableName.ColumnName

Generate the corrected SQL query:"""

        if hasattr(self.llm, 'ainvoke'):
            response = await self.llm.ainvoke(fix_prompt)
        else:
            response = self.llm.invoke(fix_prompt)
        
        if hasattr(response, 'content'):
            return response.content
        return str(response)

    def _clean_sql_output(self, sql_output: str) -> str:
        """Clean SQL output from LLM"""
        if not sql_output:
            return ""
        
        sql_output = sql_output.strip()
        
        if sql_output.startswith("```sql"):
            sql_output = sql_output[6:]
        if sql_output.startswith("```"):
            sql_output = sql_output[3:]
        if sql_output.endswith("```"):
            sql_output = sql_output[:-3]
        
        lines = sql_output.split('\n')
        sql_lines = []
        found_sql_start = False
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('--'):
                continue
            
            if line.upper().startswith(('SELECT', 'WITH', 'INSERT', 'UPDATE', 'DELETE')):
                found_sql_start = True
                sql_lines.append(line)
            elif found_sql_start:
                if any(indicator in line.lower() for indicator in ["generate the", "instructions:", "fix", "validation"]):
                    break
                sql_lines.append(line)
        
        if sql_lines:
            sql_output = '\n'.join(sql_lines)
        else:
            import re
            select_match = re.search(r'(SELECT.*?)(?:\n\n|\Z)', sql_output, re.DOTALL | re.IGNORECASE)
            if select_match:
                sql_output = select_match.group(1)
        
        sql_output = sql_output.replace('\\n', ' ').replace('\\t', ' ').replace('\\r', '')
        sql_output = ' '.join(sql_output.split())
        
        if sql_output.endswith(';'):
            sql_output = sql_output[:-1].strip()
        
        return sql_output.strip()

    async def process_query(self, command: str, include_sql: bool = True) -> QueryResponse:
        """Main processing method - 100% LLM-driven"""
        start_time = time.time()
        
        logger.info(f"Processing query with intelligent LLM analysis: {command[:100]}...")
        
        try:
            if not self.enhanced_schema_store or not self.enhanced_schema_store.is_metadata_loaded:
                return QueryResponse(
                    success=False,
                    command=command,
                    error="Knowledge base not loaded. Please upload metadata file first.",
                    execution_time=round(time.time() - start_time, 3)
                )
            
            logger.info("Step 1: Analyzing user intent with LLM...")
            intent_analysis = await self._analyze_user_intent(command)
            logger.info(f"Intent analysis: {intent_analysis.get('business_context', 'N/A')}")
            
            logger.info("Step 2: Searching knowledge base for relevant tables...")
            search_results = self.enhanced_schema_store.search(command, k=12)
            if not search_results:
                return QueryResponse(
                    success=False,
                    command=command,
                    error="No relevant tables found in knowledge base",
                    execution_time=round(time.time() - start_time, 3)
                )
            
            logger.info("Step 3: LLM selecting most relevant tables...")
            selected_tables = await self._select_relevant_tables(command, search_results, intent_analysis)
            table_names = [t[0] for t in selected_tables]
            logger.info(f"Selected tables: {table_names}")
            
            logger.info("Step 4: Building comprehensive schema context...")
            schema_context = self._build_comprehensive_schema_context(selected_tables)
            date_context = self._get_current_date_context()
            
            max_attempts = 3
            sql_query = None
            
            for attempt in range(max_attempts):
                logger.info(f"Step 5.{attempt + 1}: Generating SQL with LLM (attempt {attempt + 1})...")
                
                if attempt == 0:
                    sql_query = await self._generate_optimized_sql(command, intent_analysis, schema_context, date_context)
                else:
                    sql_query = await self._fix_sql_with_llm(command, sql_query, last_error, schema_context, intent_analysis)
                
                sql_query = self._clean_sql_output(sql_query)
                
                if not sql_query.strip():
                    if attempt == max_attempts - 1:
                        return QueryResponse(
                            success=False,
                            command=command,
                            error="LLM failed to generate valid SQL query",
                            execution_time=round(time.time() - start_time, 3)
                        )
                    continue
                
                logger.info("Step 6: Validating SQL with LLM...")
                is_valid, validation_error = await self._validate_sql_with_llm(sql_query, schema_context, table_names)
                
                if is_valid:
                    logger.info("SQL validation successful!")
                    break
                else:
                    last_error = validation_error
                    logger.warning(f"Validation failed: {validation_error}")
                    
                    if attempt == max_attempts - 1:
                        return QueryResponse(
                            success=False,
                            command=command,
                            error=f"Failed to generate valid SQL after {max_attempts} attempts. Last error: {validation_error}",
                            sql_query=sql_query,
                            execution_time=round(time.time() - start_time, 3)
                        )
            
            execution_time = time.time() - start_time
            logger.info(f"Intelligent SQL generation completed successfully in {execution_time:.3f} seconds")
            
            return QueryResponse(
                success=True,
                command=command,
                sql_query=sql_query,
                execution_time=round(execution_time, 3)
            )
        
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Intelligent SQL generation failed: {str(e)}")
            
            return QueryResponse(
                success=False,
                command=command,
                error=str(e),
                execution_time=round(execution_time, 3)
            )

    async def execute_direct_sql(self, sql_query: str) -> QueryResponse:
        start_time = time.time()
        
        try:
            result = self.sql_db.run(sql_query)
            execution_time = time.time() - start_time
            
            return QueryResponse(
                success=True,
                sql_query=sql_query,
                execution_time=round(execution_time, 3)
            )
        
        except Exception as e:
            execution_time = time.time() - start_time
            
            return QueryResponse(
                success=False,
                sql_query=sql_query,
                error=str(e),
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
            return {
                "status": "unhealthy",
                "database_connected": False,
                "error": str(e)
            }
    
    def get_database_info(self) -> TableInfo:
        try:
            table_names = self.sql_db.get_usable_table_names()
            schema_info = self.sql_db.get_table_info()
            
            return TableInfo(
                table_names=table_names,
                schema_info=schema_info
            )
        except Exception as e:
            raise QueryExecutionError(f"Failed to retrieve database information: {str(e)}")
    
    def get_table_description(self, table_name: str) -> dict:
        try:
            result = self.sql_db.get_table_info([table_name])
            
            return {
                "table_name": table_name,
                "schema": result,
                "success": True
            }
        except Exception as e:
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
            return {
                "status": "unhealthy",
                "database_connected": False,
                "error": str(e)
            }
    
    def get_enhanced_schema_store(self):
        return self.enhanced_schema_store