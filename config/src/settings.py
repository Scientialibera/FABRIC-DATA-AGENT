"""
Configuration settings for Azure OpenAI and Fabric Data Agent.

This module provides Pydantic models for validating and managing application
configuration from environment variables and runtime parameters.

Configuration Hierarchy:
1. Environment variables (.env file)
2. Hardcoded defaults in this file
3. Runtime parameter overrides

This is the SINGLE SOURCE OF TRUTH for all configuration values.
"""

import os
from pydantic import BaseModel, Field, validator
from typing import Optional


# ============================================================================
# APPLICATION DEFAULTS
# ============================================================================

DEFAULT_AZURE_OPENAI_API_VERSION = "2024-10-01-preview"
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 2000
DEFAULT_LOG_LEVEL = "INFO"

# Maximum iterations for agentic reasoning loop
MAX_AGENTIC_ITERATIONS = 5

# MCP Server Configuration
# Set to True to expose the agent as an MCP server (Model Context Protocol)
# When enabled, run with: python mcp_server.py
ENABLE_MCP_SERVER = True

# Default timeout (seconds) for Fabric Data Agent queries
FABRIC_AGENT_QUERY_TIMEOUT = 300

# Tool definition JSON file path
TOOL_DEFINITION_FILE = "config/tools/fabric_data.json"

# Retry configuration
MAX_RETRY_ATTEMPTS = 3
RETRY_INITIAL_DELAY = 4
RETRY_MAX_DELAY = 10
RETRY_MULTIPLIER = 1

# Azure OpenAI API Details
AZURE_OPENAI_TOKEN_SCOPE = "https://cognitiveservices.azure.com/.default"
AOAI_ENDPOINT_OLD_DOMAIN = ".cognitiveservices.azure.com"
AOAI_ENDPOINT_NEW_DOMAIN = ".openai.azure.com"
DEFAULT_TOOL_CHOICE = "auto"

# Logging
HTTP_LOGGING_LEVEL = "WARNING"
LOGGERS_TO_SUPPRESS = [
    "httpx",
    "azure.core.pipeline.policies.http_logging_policy",
    "asyncio",
    "azure.identity",
]
AZURE_CLI_AUTH_SOURCE = "Azure CLI / Managed Identity"

# HTTP
HTTP_UNAUTHORIZED = 401
AUTH_FAILURE_INDICATORS = ["401", "Unauthorized", "expired"]

# Output formatting
OUTPUT_WIDTH = 80
OUTPUT_SEPARATOR = "=" * OUTPUT_WIDTH
UNKNOWN_TOOL_ERROR_TEMPLATE = "Unknown tool: {tool_name}"


class AzureOpenAISettings(BaseModel):
    """
    Azure OpenAI configuration settings.

    Reads from environment variables with intelligent defaults.
    This is the single source of truth for all config values.

    Attributes:
        endpoint: Azure OpenAI service endpoint URL (from env)
        api_key: Optional API key (from env, not used with managed identity)
        api_version: Azure OpenAI API version (from env or default)
        chat_deployment: Name of the chat deployment model (from env)
        temperature: LLM temperature for sampling 0.0-2.0 (from env or default)
        max_tokens: Maximum tokens in LLM response (from env or default)
    """

    endpoint: str = Field(..., description="Azure OpenAI endpoint URL")
    api_key: Optional[str] = Field(
        default=None,
        description="Azure OpenAI API key (not used with managed identity)"
    )
    api_version: str = Field(
        default=DEFAULT_AZURE_OPENAI_API_VERSION,
        description="Azure OpenAI API version"
    )
    chat_deployment: str = Field(..., description="Chat model deployment name")
    temperature: float = Field(
        default=DEFAULT_TEMPERATURE,
        ge=0.0,
        le=2.0,
        description="Temperature for LLM sampling (0.0-2.0)"
    )
    max_tokens: int = Field(
        default=DEFAULT_MAX_TOKENS,
        gt=0,
        description="Maximum tokens in LLM response"
    )

    @validator("endpoint")
    def validate_endpoint(cls, value: str) -> str:
        """Validate and normalize Azure OpenAI endpoint."""
        if not value:
            raise ValueError("Endpoint cannot be empty")
        return value.rstrip("/")

    @validator("chat_deployment")
    def validate_deployment(cls, value: str) -> str:
        """Validate chat deployment name."""
        if not value:
            raise ValueError("Chat deployment cannot be empty")
        return value

    class Config:
        """Pydantic model configuration."""

        extra = "allow"
        case_sensitive = False

    @classmethod
    def from_env(cls) -> "AzureOpenAISettings":
        """
        Load settings from environment variables.

        Returns:
            AzureOpenAISettings: Validated configuration from environment

        Raises:
            ValueError: If required environment variables are missing
        """
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        if not endpoint:
            raise ValueError("AZURE_OPENAI_ENDPOINT environment variable is required")

        deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT")
        if not deployment:
            raise ValueError("AZURE_OPENAI_CHAT_DEPLOYMENT environment variable is required")

        return cls(
            endpoint=endpoint,
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", DEFAULT_AZURE_OPENAI_API_VERSION),
            chat_deployment=deployment,
            temperature=float(os.getenv("AZURE_OPENAI_TEMPERATURE", DEFAULT_TEMPERATURE)),
            max_tokens=int(os.getenv("AZURE_OPENAI_MAX_TOKENS", DEFAULT_MAX_TOKENS)),
        )
