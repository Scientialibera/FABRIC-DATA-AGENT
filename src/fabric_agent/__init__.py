"""Fabric Agent module - client and service."""

from .client import FabricDataAgentClient
from .service import FabricAgentService, get_fabric_service

__all__ = ["FabricDataAgentClient", "FabricAgentService", "get_fabric_service"]
