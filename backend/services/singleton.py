"""Singleton pattern for shared service instances."""

from .simulation_service import SimulationService

# Global service instance (singleton pattern)
_simulation_service: SimulationService = None


def get_simulation_service() -> SimulationService:
    """
    Get or create the singleton simulation service instance.
    
    Returns:
        SimulationService instance
    """
    global _simulation_service
    if _simulation_service is None:
        _simulation_service = SimulationService()
    return _simulation_service

