"""
Multi-source AI Assistant using Microsoft Agent Framework.

This module provides a flexible AI assistant that can integrate ANY data sources
via a simple tool + service injection pattern. The agent can autonomously reason,
call multiple tools in sequence, chain results, and synthesize comprehensive answers.

ARCHITECTURE - Tool + Service Pattern
=====================================

Each tool requires:
1. A function definition with Annotated parameters (the tool contract)
2. A service class to execute the tool (the implementation)

Tools communicate ONLY through their parameters/return types.
Services are injected via dependency injection at initialization.

ADDING NEW TOOLS - 3 Simple Steps
==================================

Step 1: Create a Service Class
   Example: DataWarehouseService for querying a data warehouse

   class DataWarehouseService:
       def query(self, query: str) -> str:
           # Execute query, return results
           return results

Step 2: Create the Tool Function
   The function signature defines the LLM-callable interface.
   The function body delegates to the service.

   def query_data_warehouse(
       query: Annotated[str, Field(
           description="SQL query or natural language query"
       )]
   ) -> str:
       '''Query corporate data warehouse.'''
       return self.data_warehouse_service.query(query)

Step 3: Register Tool + Inject Service in __init__
   In AIAssistant.__init__:

   self.data_warehouse_service = DataWarehouseService(config)
   self._load_tools()  # Loads all tools

Step 4: Update system prompt (optional)
   Add documentation in config/system_prompt.txt for the new tool

THAT'S IT! The Agent Framework handles:
- Deciding which tools to call and when
- Parameter passing and type validation
- Multi-step reasoning and tool chaining
- Context management across calls

EXAMPLE MULTI-SOURCE SCENARIO:
==============================

Tools Available:
- query_fabric_data_agent(query) -> str        [Financial data]
- query_data_warehouse(query) -> str           [Corporate data]
- search_external_api(query) -> str            [External sources]
- calculate_statistics(data) -> str            [Computations]

User Query: "Show me Q4 revenue trends and compare to industry averages"

Agent Flow (automatic):
1. Calls query_fabric_data_agent("Q4 revenue") -> gets internal revenue
2. Calls search_external_api("Q4 industry revenue trends") -> gets external data
3. Calls calculate_statistics([internal, external]) -> computes comparison
4. Synthesizes final answer

No code changes needed - just services + tools!
"""

from pathlib import Path
from typing import Annotated, Dict, Any

import structlog
from pydantic import Field
from agent_framework import ChatAgent
from agent_framework.azure import AzureOpenAIChatClient
from azure.identity import DefaultAzureCredential

from src.config.settings import AzureOpenAISettings
from src.fabric_agent.service import get_fabric_service

logger = structlog.get_logger(__name__)

SYSTEM_PROMPT_FILE = "config/system_prompt.txt"


def _load_system_prompt() -> str:
    """Load system prompt from configuration file."""
    try:
        prompt_path = Path(SYSTEM_PROMPT_FILE)
        if not prompt_path.exists():
            raise FileNotFoundError(
                f"System prompt file not found: {SYSTEM_PROMPT_FILE}"
            )
        return prompt_path.read_text(encoding="utf-8").strip()
    except Exception as e:
        logger.error("Failed to load system prompt", error=str(e))
        raise


class AIAssistant:
    """
    Multi-source AI Assistant using Microsoft Agent Framework + Service Injection.

    Architecture:
    - Each data source needs a SERVICE that knows how to query it
    - Each service gets wrapped in a TOOL (a Python function the LLM can call)
    - The Agent Framework handles reasoning, tool selection, and chaining

    Service Injection Pattern:
    - Services are initialized in __init__ (one per data source)
    - Tools reference services via closure (Python function scope)
    - Agent Framework automatically calls tools as needed
    - No hardcoded tool routing or if/else logic needed

    Benefits:
    - Add new sources: Create service + tool function
    - Remove sources: Delete service initialization + tool function
    - Test sources: Mock service in unit tests
    - Swap sources: Replace service implementation, keep tool interface
    - Tool chaining: Agent automatically sequences multiple tool calls

    Example - Adding a Database Service:
    ====================================
    1. Create service in src/database/service.py:
       class DatabaseService:
           def query(self, query: str) -> str: ...

    2. Initialize in __init__:
       self.database_service = DatabaseService(config)

    3. Add tool in _load_tools():
       def query_database(query: Annotated[str, Field(...)]) -> str:
           return self.database_service.query(query)
       self.tools.append(query_database)

    4. Update system prompt (optional)

    Done! Agent can now call query_database() alongside other tools.
    """

    def __init__(self, aoai_settings: AzureOpenAISettings) -> None:
        """
        Initialize the AI Assistant with services and tools.

        Services initialized here can be injected into tool functions.

        Args:
            aoai_settings: Azure OpenAI configuration settings
        """
        self.aoai_settings = aoai_settings
        
        # ====================================================================
        # SERVICE INITIALIZATION - Inject all data source services here
        # ====================================================================
        self.fabric_service = get_fabric_service()
        # TODO: Add more services as needed
        # self.database_service = DatabaseService(config)
        # self.api_service = APIService(config)
        # self.search_service = SearchService(config)
        
        self.system_prompt = _load_system_prompt()
        self.tools: list = []
        
        # Initialize Azure OpenAI client via Agent Framework
        self.chat_client = AzureOpenAIChatClient(
            endpoint=aoai_settings.endpoint,
            deployment_name=aoai_settings.chat_deployment,
            credential=DefaultAzureCredential(),
        )
        
        # Load all tools (which delegate to services)
        self._load_tools()
        
        # Create agent with tools
        self.agent = ChatAgent(
            chat_client=self.chat_client,
            instructions=self.system_prompt,
            tools=self.tools,
        )
        
        logger.info("Initialized AI Assistant with Agent Framework")

    def _load_tools(self) -> None:
        """
        Register all tools for the agent.

        Each tool function:
        1. Receives parameters from LLM
        2. Delegates to a service (injected in __init__)
        3. Returns results to LLM

        TOOL ADDITION PATTERN - Add as many tools as needed:
        ====================================================

        1. Simple Tool (Single Service):
           def query_my_source(
               param: Annotated[str, Field(description="...")]
           ) -> str:
               '''Tool documentation for LLM.'''
               return self.my_service.query(param)

        2. Complex Tool (Multiple Services):
           def analyze_data(
               query: Annotated[str, Field(description="...")]
           ) -> str:
               '''Combine data from multiple sources.'''
               data1 = self.service1.fetch(query)
               data2 = self.service2.fetch(query)
               return self.analysis_service.combine(data1, data2)

        3. Computation Tool:
           def calculate_metrics(
               data: Annotated[str, Field(description="...")]
           ) -> str:
               '''Process and compute statistics.'''
               return self.compute_service.analyze(data)

        Register with: self.tools.append(tool_function)
        """
        
        # ====================================================================
        # TOOL 1: Query Fabric Data Agent (Financial Data Source)
        # ====================================================================
        def query_fabric_data_agent(
            query: Annotated[
                str,
                Field(
                    description=(
                        "Natural language query for the Fabric Data Agent. "
                        "Use for questions about specific data values, "
                        "aggregations, data analysis, or data exploration."
                    )
                ),
            ]
        ) -> str:
            """Query the Fabric Data Agent for business data."""
            try:
                logger.info("Fabric Data Agent query", query=query)
                result = self.fabric_service.query(query, include_details=True)

                if result.get("success"):
                    logger.info("Fabric query completed", query=query)
                    return result.get("answer", "No data returned")
                else:
                    error_msg = result.get("error", "Unknown error")
                    logger.error("Fabric query failed", query=query, error=error_msg)
                    return f"Error: {error_msg}"
            except Exception as e:
                logger.error("Failed to query Fabric Data Agent", error=str(e))
                return f"Exception: {str(e)}"

        # Register Tool 1
        self.tools.append(query_fabric_data_agent)

        # ====================================================================
        # TOOL ADDITION TEMPLATE - Copy/paste and customize for each source
        # ====================================================================
        # def query_database(
        #     query: Annotated[
        #         str,
        #         Field(
        #             description="SQL or natural language query for database"
        #         ),
        #     ]
        # ) -> str:
        #     """Query the corporate database for operational data."""
        #     try:
        #         logger.info("Database query", query=query)
        #         result = self.database_service.query(query)
        #         return result
        #     except Exception as e:
        #         logger.error("Database query failed", error=str(e))
        #         return f"Error: {str(e)}"
        #
        # self.tools.append(query_database)

    async def process_question(self, question: str) -> Dict[str, Any]:
        """
        Process a question using the Agent Framework.

        The Agent Framework automatically handles:
        - Agentic reasoning loop
        - Tool selection and calling
        - Context management
        - Multi-step reasoning
        - Loop termination

        Args:
            question: User's question to process

        Returns:
            Dictionary containing:
                - question: Original question
                - response: Agent's response text
                - success: Whether processing succeeded
        """
        logger.info("Starting agent processing", question=question)

        try:
            # Run the agent - it handles all reasoning and tool calls internally
            result = await self.agent.run(question)

            logger.info("Agent processing completed", question=question)

            return {
                "question": question,
                "response": result.text,
                "success": True,
            }
        except Exception as e:
            logger.error("Agent processing failed", error=str(e), question=question)
            return {
                "question": question,
                "response": f"Error: {str(e)}",
                "success": False,
            }

    async def close(self) -> None:
        """Close resources and cleanup."""
        self.fabric_service.close()
        logger.info("AI Assistant closed")


