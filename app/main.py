"""
Main entry point for the server provisioning webhook.

This module starts the FastAPI application for handling server provisioning events.
"""
import logging
import uvicorn

from .api import app
from .config import AppConfig

# Load configuration
config = AppConfig()

def main():
    """Main entry point for the application."""
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    uvicorn.run(
        "app.api:app",
        host="0.0.0.0",
        port=config.port,
        reload=False,
        access_log=True
    )

if __name__ == "__main__":
    main()
