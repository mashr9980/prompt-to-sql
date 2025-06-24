import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routes import health, database, query, knowledge_base
from app.core.dependencies import get_text_to_sql_service, reset_services
from app.core.exceptions import (
    DatabaseConnectionError,
    LLMServiceError,
    QueryExecutionError,
    SchemaRetrievalError,
    ConfigurationError
)

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format=settings.LOG_FORMAT,
    handlers=[
        logging.StreamHandler(),
    ]
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting AI Database Query System...")
    
    try:
        logger.info("Initializing services...")
        service = get_text_to_sql_service()
        
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
        logger.info("Shutting down AI Database Query System...")
        reset_services()
        logger.info("Application shutdown completed")


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Database Query System",
        version="1.0.0",
        description="""
        ## AI Database Query System
        Convert natural language queries to SQL and execute them against your database.
        """,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan
    )
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start_time = time.time()
        
        logger.info(f"Request: {request.method} {request.url.path}")
        
        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            
            logger.info(
                f"Response: {request.method} {request.url.path} "
                f"- {response.status_code} - {process_time:.3f}s"
            )
            
            response.headers["X-Process-Time"] = str(process_time)
            
            return response
        
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                f"Request failed: {request.method} {request.url.path} "
                f"- {process_time:.3f}s - {str(e)}"
            )
            raise
    
    static_path = Path(__file__).parent / "static"
    if static_path.exists():
        app.mount("/static", StaticFiles(directory=str(static_path)), name="static")
        logger.info(f"Static files mounted from: {static_path}")
    else:
        static_path.mkdir(parents=True, exist_ok=True)
        logger.warning(f"Created static directory: {static_path}")
        logger.warning("Please add your frontend files to the static directory")
    
    app.include_router(health.router, prefix="/api")
    app.include_router(database.router, prefix="/api")
    app.include_router(query.router, prefix="/api")
    app.include_router(knowledge_base.router, prefix="/api")
    
    @app.get("/", tags=["Root"])
    async def root():
        return {
            "message": "AI Database Query System is running",
            "version": "1.0.0",
            "frontend": "/app",
            "docs": "/docs",
            "health": "/api/health/quick",
            "knowledge_base": "/api/knowledge-base/status",
            "status": "operational"
        }
    
    @app.get("/app", tags=["Frontend"])
    async def serve_frontend():
        static_index = static_path / "index.html"
        if static_index.exists():
            return FileResponse(str(static_index))
        else:
            return JSONResponse(
                status_code=404,
                content={
                    "error": "Frontend not found",
                    "message": "Please ensure the following files exist:",
                    "required_files": [
                        "static/index.html",
                        "static/js/app.js", 
                        "static/styles/style.css"
                    ],
                    "current_path": str(static_path),
                    "setup_instructions": "1. Create 'static' folder in project root, 2. Add HTML, CSS, JS files, 3. Restart server"
                }
            )
    
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
                "detail": "Internal server error" if settings.LOG_LEVEL != "DEBUG" else str(exc)
            }
        )
    
    return app


app = create_app()