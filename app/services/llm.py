import logging
from abc import ABC, abstractmethod
from typing import Optional

from ..config import settings
from ..core.exceptions import LLMServiceError, ConfigurationError

logger = logging.getLogger(__name__)


class LLMService(ABC):
    """Abstract base class for LLM services"""
    
    @abstractmethod
    def generate_sql(self, natural_language_query: str, table_info: str) -> str:
        """Generate SQL query from natural language"""
        pass


class OpenAILLMService(LLMService):
    """OpenAI-based LLM service for SQL generation"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.OPENAI_API_KEY
        
        if not self.api_key:
            raise ConfigurationError("OpenAI API key not configured")
        
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.api_key)
            logger.info("OpenAI LLM service initialized successfully")
        except ImportError:
            raise ConfigurationError("OpenAI package not installed. Run: pip install openai")
        except Exception as e:
            raise LLMServiceError(f"Failed to initialize OpenAI client: {str(e)}")
    
    def generate_sql(self, natural_language_query: str, table_info: str) -> str:
        """Generate SQL query using OpenAI GPT model"""
        try:
            sql_prompt = self._build_prompt(natural_language_query, table_info)
            
            logger.debug("Sending request to OpenAI")
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[{"role": "user", "content": sql_prompt}],
                temperature=settings.OPENAI_TEMPERATURE,
                max_tokens=settings.OPENAI_MAX_TOKENS
            )
            
            sql_query = response.choices[0].message.content.strip()
            
            # Clean up the response
            sql_query = self._clean_sql_response(sql_query)
            
            logger.debug(f"Generated SQL: {sql_query[:100]}...")
            return sql_query
            
        except Exception as e:
            logger.error(f"Failed to generate SQL with OpenAI: {str(e)}")
            raise LLMServiceError(f"SQL generation failed: {str(e)}")
    
    def _build_prompt(self, natural_language_query: str, table_info: str) -> str:
        """Build the prompt for SQL generation"""
        return f"""
        You are an expert MSSQL Server database analyst. Based on the database schema below, generate a precise T-SQL query.

        DATABASE SCHEMA:
        {table_info}

        CONTEXT: This is a business management system with:
        - Arabic/English mixed content (use COLLATE SQL_Latin1_General_CP1_CI_AS for Arabic text searches)
        - Project management (projects, PO, quotations)
        - Employee management (attendance, salaries, tasks)
        - Inventory management
        - Financial transactions
        - Supplier management
        - Cafe/restaurant operations

        KEY TABLES:
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

        QUERY: {natural_language_query}

        RULES:
        1. Use square brackets [] for table/column names with spaces or special characters
        2. Use TOP instead of LIMIT
        3. For Arabic text searches, use LIKE with COLLATE SQL_Latin1_General_CP1_CI_AS
        4. Handle mixed language content appropriately
        5. Use proper T-SQL syntax
        6. Consider NULL values in conditions
        7. Use appropriate JOINs when querying multiple related tables
        8. For date queries, use proper DATETIME formatting
        9. For money/financial queries, use MONEY data type appropriately
        10. Be specific with column names based on the schema provided
        11. Always include proper error handling in complex queries
        12. Use parameterized approaches when possible

        Return ONLY the SQL query without any explanations or markdown formatting:
        """
    
    def _clean_sql_response(self, sql_response: str) -> str:
        """Clean up the SQL response from the LLM"""
        # Remove common markdown formatting
        sql_response = sql_response.replace('```sql', '').replace('```', '')
        
        # Remove extra whitespace
        sql_response = sql_response.strip()
        
        # Remove any explanatory text that might be included
        lines = sql_response.split('\n')
        sql_lines = []
        
        for line in lines:
            line = line.strip()
            if line and not line.startswith('--') and not line.lower().startswith('note:'):
                sql_lines.append(line)
        
        return '\n'.join(sql_lines)


class GeminiLLMService(LLMService):
    """Google Gemini-based LLM service (placeholder for future implementation)"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        if not self.api_key:
            raise ConfigurationError("Gemini API key not configured")
        logger.info("Gemini LLM service initialized (placeholder)")
    
    def generate_sql(self, natural_language_query: str, table_info: str) -> str:
        """Generate SQL query using Google Gemini (placeholder)"""
        raise NotImplementedError("Gemini LLM service not yet implemented")


def create_llm_service(service_type: str = "openai") -> LLMService:
    """Factory function to create LLM service instances"""
    service_type = service_type.lower()
    
    if service_type == "openai":
        return OpenAILLMService()
    elif service_type == "gemini":
        return GeminiLLMService()
    else:
        raise ConfigurationError(f"Unsupported LLM service type: {service_type}")