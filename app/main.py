"""
Main application entry point.

This module sets up the FastAPI application and configures the server
for handling webhook events related to resource reservation management.
"""
import uvicorn
from fastapi import FastAPI

from . import config
from .api import router


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Returns:
        Configured FastAPI application instance
    """
    app = FastAPI(
        title="Server Webhook Client",
        description="Service to handle webhook events for \'Server\' resource",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    
    # Add router to the FastAPI application
    app.include_router(router)
    
    return app


# Create the application instance
app = create_app()


def main() -> None:
    """Run the application server."""
    # Configure logging to filter healthz logs if enabled
    if config.DISABLE_HEALTHZ_LOGS:
        import logging
        from .config import HealthzFilter
        uvicorn_access_logger = logging.getLogger("uvicorn.access")
        uvicorn_access_logger.addFilter(HealthzFilter())
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",  # Bind to all interfaces
        port=config.PORT,
        reload=False,
        log_level="info"
    )


if __name__ == "__main__":
    main()