"""Custom exceptions for the application"""

class DatabaseConnectionError(Exception):
    """Raised when database connection fails"""
    pass


class LLMServiceError(Exception):
    """Raised when LLM service encounters an error"""
    pass


class QueryExecutionError(Exception):
    """Raised when SQL query execution fails"""
    pass


class SchemaRetrievalError(Exception):
    """Raised when database schema retrieval fails"""
    pass


class ConfigurationError(Exception):
    """Raised when configuration is invalid"""
    pass