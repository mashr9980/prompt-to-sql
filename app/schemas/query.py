from typing import Optional, Any
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    command: str = Field(..., description="Natural language query", min_length=1, max_length=1000)
    include_sql: Optional[bool] = Field(True, description="Whether to include generated SQL in response")
    
    class Config:
        json_schema_extra = {
            "example": {
                "command": "Show me all employees with salary greater than 5000",
                "include_sql": True
            }
        }


class SQLRequest(BaseModel):
    sql_query: str = Field(..., description="SQL query to execute", min_length=1)
    
    class Config:
        json_schema_extra = {
            "example": {
                "sql_query": "SELECT TOP 10 * FROM users WHERE salary > 5000"
            }
        }


class QueryResponse(BaseModel):
    success: bool = Field(..., description="Whether the query was successful")
    command: Optional[str] = Field(None, description="Original natural language command")
    sql_query: Optional[str] = Field(None, description="Generated or executed SQL query")
    error: Optional[str] = Field(None, description="Error message if query failed")
    execution_time: Optional[float] = Field(None, description="Query execution time in seconds")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "command": "Show me all employees",
                "sql_query": "SELECT * FROM users",
                "error": None,
                "execution_time": 0.123
            }
        }