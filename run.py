#!/usr/bin/env python3
"""
Text-to-SQL API Runner

This script starts the FastAPI application with optimized settings for production.
"""

import logging
import uvicorn
from app.config import settings

# Configure logging for the runner
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format=settings.LOG_FORMAT
)

logger = logging.getLogger(__name__)


def main():
    """Main function to run the application"""
    logger.info(f"Starting {settings.API_TITLE} v{settings.API_VERSION}")
    logger.info(f"Host: {settings.API_HOST}:{settings.API_PORT}")
    logger.info(f"Log Level: {settings.LOG_LEVEL}")
    
    try:
        uvicorn.run(
            "app.main:app",
            host=settings.API_HOST,
            port=settings.API_PORT,
            log_level=settings.LOG_LEVEL.lower(),
            reload=False,  # Set to True for development
            workers=1,     # Increase for production
            # Additional production settings
            access_log=True,
            use_colors=True,
            server_header=False,
            date_header=False,
        )
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Failed to start application: {str(e)}")
        raise


if __name__ == "__main__":
    main()