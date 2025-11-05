"""
Fabric Data Agent Service

Handles all interactions with the Fabric Data Agent, including:
- Client initialization
- Query execution
- Response formatting
- Error handling
"""

import os
import json
from typing import Dict, Any, Optional
import structlog
from .client import FabricDataAgentClient

logger = structlog.get_logger(__name__)


class FabricAgentService:
    """Service for interacting with Fabric Data Agent."""
    
    def __init__(self, tenant_id: str, data_agent_url: str):
        """
        Initialize the Fabric Agent Service.
        
        Args:
            tenant_id: Azure tenant ID
            data_agent_url: Published Fabric Data Agent URL
        """
        self.tenant_id = tenant_id
        self.data_agent_url = data_agent_url
        self.client: Optional[FabricDataAgentClient] = None
        
        logger.info(
            "Initialized Fabric Agent Service",
            tenant_id=tenant_id,
            data_agent_url=data_agent_url
        )
    
    def _ensure_client(self):
        """Ensure client is initialized."""
        if self.client is None:
            try:
                logger.info("Initializing Fabric Data Agent client")
                self.client = FabricDataAgentClient(
                    tenant_id=self.tenant_id,
                    data_agent_url=self.data_agent_url
                )
                logger.info(" Fabric Data Agent client initialized")
            except Exception as e:
                logger.error("Failed to initialize client", error=str(e))
                raise
    
    def query(self, question: str, include_details: bool = False) -> Dict[str, Any]:
        """
        Query the Fabric Data Agent.
        
        Args:
            question: Natural language question
            include_details: If True, include detailed run information
            
        Returns:
            Dictionary with answer and optional details
        """
        try:
            self._ensure_client()
            
            logger.info(
                " Querying Fabric Data Agent",
                question=question,
                include_details=include_details
            )
            
            # Get the response
            response = self.client.ask(question)
            
            result = {
                "question": question,
                "answer": response,
                "success": True,
                "error": None,
            }
            
            # Get detailed information if requested
            if include_details:
                try:
                    run_details = self.client.get_run_details(question)
                    
                    # Format the run details
                    result["run_details"] = {
                        "run_id": run_details.get("run_id"),
                        "thread_id": run_details.get("thread_id"),
                        "status": run_details.get("status"),
                        "message_count": len(run_details.get("messages", {}).get("data", [])),
                        "step_count": len(run_details.get("run_steps", {}).get("data", [])),
                        "steps": [
                            {
                                "id": step.get("id"),
                                "type": step.get("type"),
                                "status": step.get("status"),
                                "error": step.get("error"),
                            }
                            for step in run_details.get("run_steps", {}).get("data", [])
                        ],
                    }
                    
                    logger.info(
                        " Query completed with details",
                        question=question,
                        step_count=result["run_details"]["step_count"]
                    )
                    
                except Exception as e:
                    logger.warning(
                        "Could not retrieve detailed run information",
                        error=str(e)
                    )
                    result["details_error"] = str(e)
            else:
                logger.info(" Query completed", question=question)
            
            return result
            
        except Exception as e:
            logger.error(
                " Query failed",
                error=str(e),
                question=question
            )
            
            return {
                "question": question,
                "answer": None,
                "success": False,
                "error": str(e),
            }
    
    def close(self):
        """Clean up resources."""
        if self.client:
            self.client = None
        logger.info("Fabric Agent Service closed")


# Singleton instance
_service: Optional[FabricAgentService] = None


def get_fabric_service() -> FabricAgentService:
    """Get or create Fabric Agent service instance."""
    global _service
    
    if _service is None:
        tenant_id = os.getenv("TENANT_ID")
        data_agent_url = os.getenv("DATA_AGENT_URL")
        
        if not tenant_id or not data_agent_url:
            raise ValueError(
                "TENANT_ID and DATA_AGENT_URL environment variables required"
            )
        
        _service = FabricAgentService(
            tenant_id=tenant_id,
            data_agent_url=data_agent_url
        )
    
    return _service
