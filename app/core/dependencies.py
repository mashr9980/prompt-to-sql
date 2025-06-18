"""Dependency injection for FastAPI application"""

import logging
from functools import lru_cache
from typing import Optional

from ..core.exceptions import ConfigurationError
from ..services.database import DatabaseService
from ..services.llm import LLMService, create_llm_service
from ..services.text_to_sql import TextToSQLService

logger = logging.getLogger(__name__)

# Global singleton instances
_database_service: Optional[DatabaseService] = None
_llm_service: Optional[LLMService] = None
_text_to_sql_service: Optional[TextToSQLService] = None


@lru_cache()
def get_database_service() -> DatabaseService:
    """Get or create database service singleton"""
    global _database_service

    if _database_service is None:
        logger.info("Initializing database service")
        try:
            _database_service = DatabaseService()
            logger.info("Database service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database service: {str(e)}")
            raise ConfigurationError(f"Database service initialization failed: {str(e)}")

    return _database_service


@lru_cache()
def get_llm_service() -> LLMService:
    """Get or create LLM service singleton"""
    global _llm_service

    if _llm_service is None:
        logger.info("Initializing LLM service")
        try:
            _llm_service = create_llm_service("gemini")
            logger.info("LLM service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize LLM service: {str(e)}")
            raise ConfigurationError(f"LLM service initialization failed: {str(e)}")

    return _llm_service


@lru_cache()
def get_text_to_sql_service() -> TextToSQLService:
    """Get or create TextToSQL service singleton"""
    global _text_to_sql_service

    if _text_to_sql_service is None:
        logger.info("Initializing TextToSQL service")
        try:
            database_service = get_database_service()
            llm_service = get_llm_service()
            _text_to_sql_service = TextToSQLService(llm_service, database_service)
            logger.info("TextToSQL service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize TextToSQL service: {str(e)}")
            raise ConfigurationError(f"TextToSQL service initialization failed: {str(e)}")

    return _text_to_sql_service


def reset_services():
    """Reset all service singletons (useful for testing)"""
    global _database_service, _llm_service, _text_to_sql_service

    logger.info("Resetting all service singletons")
    _database_service = None
    _llm_service = None
    _text_to_sql_service = None

    # Clear lru_cache
    get_database_service.cache_clear()
    get_llm_service.cache_clear()
    get_text_to_sql_service.cache_clear()


def get_service_status() -> dict:
    """Get status of all services"""
    return {
        "database_service_initialized": _database_service is not None,
        "llm_service_initialized": _llm_service is not None,
        "text_to_sql_service_initialized": _text_to_sql_service is not None,
    }
