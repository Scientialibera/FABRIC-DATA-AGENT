"""Fabric Agent module - client and service."""

from .client import FabricDataAgentClient
from .service import FabricDataService, get_fabric_service

__all__ = ["FabricDataAgentClient", "FabricDataService", "get_fabric_service"]
