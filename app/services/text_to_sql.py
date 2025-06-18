import logging
import time
from typing import Any, Dict, Optional

from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent

from ..config import settings
from ..core.exceptions import LLMServiceError, QueryExecutionError
from ..schemas.database import TableInfo
from ..schemas.query import QueryResponse
from ..services.database import DatabaseService
from .schema_store import SchemaVectorStore

logger = logging.getLogger(__name__)


class TextToSQLService:

    def __init__(self, llm_service, database_service: DatabaseService):
        self.database_service = database_service
        self.llm_service = llm_service

        try:
            # self.llm = ChatOpenAI(
            #     model=settings.OPENAI_MODEL,
            #     temperature=settings.OPENAI_TEMPERATURE,
            #     api_key=settings.OPENAI_API_KEY
            # )
            self.llm = ChatGoogleGenerativeAI(
                model=settings.GEMINI_MODEL,
                temperature=settings.GEMINI_TEMPERATURE,
                google_api_key=settings.GEMINI_API_KEY,
            )

            self.sql_db = SQLDatabase.from_uri(settings.DATABASE_URL)

            self.toolkit = SQLDatabaseToolkit(db=self.sql_db, llm=self.llm)
            self.tools = self.toolkit.get_tools()

            # Build schema vector store for retrieval
            self.schema_store = SchemaVectorStore(self.database_service)
            self.schema_store.build()

            self.base_system_message = self._create_system_message()

            logger.info("TextToSQLService initialized with LangChain SQL Agent")

        except Exception as e:
            logger.error(f"Failed to initialize TextToSQLService: {str(e)}")
            self.schema_store = None

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

        KEY TABLES LIKELY INCLUDE:
        - 'PO Transactions$': Purchase orders with projects, payments, dates
        - users: Employee information
        - project: Project details
        - po: Purchase orders
        - attendance: Employee attendance
        - salary: Salary information
        - supplier: Supplier data
        - quotations: Quotation details
        - tasks: Task management
        - inventory: Inventory items
        """

        if schema_context:
            base += "\nRelevant Schemas:\n" + schema_context

        return base

    def get_quick_health_status(self) -> dict:
        try:
            is_connected = self.database_service.test_connection()

            return {"status": "healthy" if is_connected else "unhealthy", "database_connected": is_connected}

        except Exception as e:
            logger.error(f"Quick health check failed: {str(e)}")
            return {"status": "unhealthy", "database_connected": False, "error": str(e)}

    async def process_query(self, command: str, include_sql: bool = True) -> QueryResponse:
        start_time = time.time()

        logger.info(f"Processing query: {command[:50]}...")

        try:
            schemas = self.schema_store.search(command, k=5)
            schema_text = "\n".join([s for _, s in schemas])

            prompt = self._create_system_message(schema_text)
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

            if hasattr(final_message, "content"):
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
                                if hasattr(message, "tool_calls") and message.tool_calls:
                                    for tool_call in message.tool_calls:
                                        if tool_call["name"] == "sql_db_query":
                                            sql_query = tool_call["args"].get("query", "")
                                            break
                except:
                    pass

            execution_time = time.time() - start_time

            logger.info(f"Query processed successfully in {execution_time:.3f} seconds")

            return QueryResponse(
                success=True,
                command=command,
                sql_query=sql_query if include_sql else None,
                result=result,
                execution_time=round(execution_time, 3),
            )

        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = str(e)

            logger.error(f"Query processing failed: {error_msg}")

            return QueryResponse(
                success=False, command=command, error=error_msg, execution_time=round(execution_time, 3)
            )

    async def execute_direct_sql(self, sql_query: str) -> QueryResponse:
        start_time = time.time()

        logger.info(f"Executing direct SQL: {sql_query[:50]}...")

        try:
            result = self.sql_db.run(sql_query)
            execution_time = time.time() - start_time

            logger.info(f"Direct SQL executed successfully in {execution_time:.3f} seconds")

            return QueryResponse(
                success=True, sql_query=sql_query, result=result, execution_time=round(execution_time, 3)
            )

        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = str(e)

            logger.error(f"Direct SQL execution failed: {error_msg}")

            return QueryResponse(
                success=False, sql_query=sql_query, error=error_msg, execution_time=round(execution_time, 3)
            )

    def get_database_info(self) -> TableInfo:
        try:
            logger.debug("Retrieving database information")

            table_names = self.sql_db.get_usable_table_names()
            schema_info = self.sql_db.get_table_info()

            return TableInfo(table_names=table_names, schema_info=schema_info)

        except Exception as e:
            logger.error(f"Failed to get database info: {str(e)}")
            raise QueryExecutionError(f"Failed to retrieve database information: {str(e)}")

    def get_table_description(self, table_name: str) -> dict:
        try:
            logger.debug(f"Getting description for table: {table_name}")

            result = self.sql_db.get_table_info([table_name])

            return {"table_name": table_name, "schema": result, "success": True}

        except Exception as e:
            logger.error(f"Failed to describe table {table_name}: {str(e)}")
            return {"table_name": table_name, "error": str(e), "success": False}

    def get_health_status(self, include_table_count: bool = True) -> dict:
        try:
            is_connected = self.database_service.test_connection()

            if not is_connected:
                return {"status": "unhealthy", "database_connected": False, "error": "Database connection failed"}

            result = {"status": "healthy", "database_connected": True}

            if include_table_count:
                try:
                    table_names = self.sql_db.get_usable_table_names()
                    result["tables_count"] = len(table_names)
                except Exception as e:
                    logger.warning(f"Could not get table count: {str(e)}")
                    result["tables_count"] = None

            return result

        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return {"status": "unhealthy", "database_connected": False, "error": str(e)}
