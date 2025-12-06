"""FastAPI main application for monitoring and control."""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from logger import configure_logging
from routes import simulation_router, status_router, logs_router

# Configure logging
configure_logging()
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Airline Kit Management API",
    version="1.0.0",
    description="API for managing airline kit optimization simulation",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Airline Kit Management API", "status": "running"}


# Include routers
app.include_router(simulation_router)
app.include_router(status_router)
app.include_router(logs_router)


if __name__ == "__main__":
    logger.info("Starting FastAPI application...")
    logger.info("Run with: python -m fastapi dev main.py")
    logger.info("Or use: python -m fastapi run main.py")

