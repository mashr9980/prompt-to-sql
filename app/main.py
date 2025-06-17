"""Main FastAPI application"""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from .config import settings
from .routes import health, database, query
from .core.dependencies import get_text_to_sql_service, reset_services
from .core.exceptions import (
    DatabaseConnectionError,
    LLMServiceError,
    QueryExecutionError,
    SchemaRetrievalError,
    ConfigurationError
)

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format=settings.LOG_FORMAT,
    handlers=[
        logging.StreamHandler(),
        # Add file handler if needed
        # logging.FileHandler("app.log")
    ]
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    logger.info("Starting Text-to-SQL API...")
    
    try:
        # Initialize services during startup
        logger.info("Initializing services...")
        service = get_text_to_sql_service()
        
        # Test database connection
        if service.database_service.test_connection():
            logger.info("Database connection successful")
        else:
            logger.warning("Database connection failed during startup")
        
        logger.info("Application startup completed successfully")
        
        yield
        
    except Exception as e:
        logger.error(f"Startup failed: {str(e)}")
        raise
    
    finally:
        logger.info("Shutting down Text-to-SQL API...")
        # Cleanup if needed
        reset_services()
        logger.info("Application shutdown completed")


def create_app() -> FastAPI:
    """Create and configure FastAPI application"""
    
    app = FastAPI(
        title=settings.API_TITLE,
        version=settings.API_VERSION,
        description="""
        ## Text-to-SQL API

        Convert natural language queries to SQL and execute them against your database.

        ### Features
        - 🤖 AI-powered natural language to SQL conversion
        - 🏢 Optimized for business management systems
        - 🌐 Arabic/English mixed content support
        - ⚡ High-performance caching
        - 📊 Comprehensive database schema exploration
        - 🔍 Direct SQL execution capabilities

        ### Quick Start
        1. Check API health: `GET /health/quick`
        2. View available tables: `GET /database/tables/names`
        3. Execute a query: `POST /query/`

        ### Example Query
        ```json
        {
            "command": "Show me all employees with salary greater than 5000",
            "include_sql": true
        }
        ```
        """,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=settings.CORS_METHODS,
        allow_headers=settings.CORS_HEADERS,
    )
    
    # Add request logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start_time = time.time()
        
        # Log request
        logger.info(f"Request: {request.method} {request.url.path}")
        
        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            
            # Log response
            logger.info(
                f"Response: {request.method} {request.url.path} "
                f"- {response.status_code} - {process_time:.3f}s"
            )
            
            # Add timing header
            response.headers["X-Process-Time"] = str(process_time)
            
            return response
        
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                f"Request failed: {request.method} {request.url.path} "
                f"- {process_time:.3f}s - {str(e)}"
            )
            raise
    
    # Include routers
    app.include_router(health.router)
    app.include_router(database.router)
    app.include_router(query.router)
    
    # Root endpoint
    @app.get("/app")
    async def serve_user_app():
        return FileResponse("static/index.html")
    
    # Global exception handlers
    @app.exception_handler(DatabaseConnectionError)
    async def database_connection_error_handler(request: Request, exc: DatabaseConnectionError):
        logger.error(f"Database connection error: {str(exc)}")
        return JSONResponse(
            status_code=503,
            content={
                "error": "Database Connection Error",
                "message": "Unable to connect to the database. Please try again later.",
                "detail": str(exc)
            }
        )
    
    @app.exception_handler(LLMServiceError)
    async def llm_service_error_handler(request: Request, exc: LLMServiceError):
        logger.error(f"LLM service error: {str(exc)}")
        return JSONResponse(
            status_code=502,
            content={
                "error": "AI Service Error",
                "message": "The AI service is temporarily unavailable. Please try again later.",
                "detail": str(exc)
            }
        )
    
    @app.exception_handler(QueryExecutionError)
    async def query_execution_error_handler(request: Request, exc: QueryExecutionError):
        logger.error(f"Query execution error: {str(exc)}")
        return JSONResponse(
            status_code=400,
            content={
                "error": "Query Execution Error",
                "message": "Failed to execute the query. Please check your input and try again.",
                "detail": str(exc)
            }
        )
    
    @app.exception_handler(SchemaRetrievalError)
    async def schema_retrieval_error_handler(request: Request, exc: SchemaRetrievalError):
        logger.error(f"Schema retrieval error: {str(exc)}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "Schema Retrieval Error",
                "message": "Failed to retrieve database schema information.",
                "detail": str(exc)
            }
        )
    
    @app.exception_handler(ConfigurationError)
    async def configuration_error_handler(request: Request, exc: ConfigurationError):
        logger.error(f"Configuration error: {str(exc)}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "Configuration Error",
                "message": "Server configuration error. Please contact the administrator.",
                "detail": str(exc)
            }
        )
    
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        logger.error(f"Value error: {str(exc)}")
        return JSONResponse(
            status_code=400,
            content={
                "error": "Invalid Input",
                "message": "The provided input is invalid.",
                "detail": str(exc)
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal Server Error",
                "message": "An unexpected error occurred. Please try again later.",
                "detail": "Internal server error" if not settings.LOG_LEVEL == "DEBUG" else str(exc)
            }
        )
    
    return app


# Create app instance
app = create_app()