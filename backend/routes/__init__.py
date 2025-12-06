"""Routes package for API endpoints."""

from .simulation_routes import router as simulation_router
from .status_routes import router as status_router
from .logs_routes import router as logs_router

__all__ = ["simulation_router", "status_router", "logs_router"]

