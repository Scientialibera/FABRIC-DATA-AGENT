"""
Multi-source AI Assistant using Microsoft Agent Framework.

This module provides a flexible AI assistant that can integrate ANY data sources
via a simple tool + service injection pattern. The agent autonomously reasons,
calls appropriate tools in sequence, chains results, and synthesizes comprehensive answers.

ARCHITECTURE - Tool + Service Pattern
=====================================

Each tool requires two components:

1. A SERVICE class that knows HOW to query a data source
   - Handles connection/authentication
   - Executes queries
   - Returns results
   - Handles errors

2. A TOOL function that defines the LLM-callable interface
   - Annotated parameters (what the LLM passes)
   - Delegates to the service
   - Returns results to the LLM

Tools and services communicate through well-defined interfaces.
Services are injected via dependency injection at initialization.

ADDING NEW TOOLS
================

To add a new data source to the assistant:

Step 1: Create a Service Class
   Location: src/your_source/service.py
   Purpose: Handles all interactions with the data source

   Example:
   ```
   class SQLDatabaseService:
       def __init__(self, connection_string: str):
           self.connection_string = connection_string
       
       def query(self, question: str) -> str:
           # Execute query logic here
           return results
   ```

Step 2: Create the Tool Function
   Location: src/ai/assistant.py _load_tools() method
   Purpose: Defines the LLM-callable interface

   Example:
   ```
   def query_sql_database(
       query: Annotated[str, Field(
           description="SQL query or natural language question"
       )]
   ) -> str:
       '''Query the SQL database for business data.'''
       return self.sql_database_service.query(query)
   ```

Step 3: Register Tool + Inject Service
   In AIAssistant.__init__():
   - Create service instance: self.sql_database_service = SQLDatabaseService(...)
   - Call self._load_tools() (automatically loads all registered tools)
   - Add tool function reference: self.tools.append(query_sql_database)

Step 4: Update System Prompt (Optional)
   Location: config/system_prompt.txt
   Purpose: Help LLM understand when to use this tool

The Agent Framework handles:
- Reasoning logic (when to use tools, when to answer)
- Tool selection and calling
- Parameter validation and type checking
- Multi-step reasoning and tool chaining
- Context management across multiple calls

MULTI-SOURCE EXAMPLE
====================

If you have these tools:
- query_fabric_data_agent() → Financial/business data from Fabric
- query_sql_database()      → Operational data from SQL
- search_api()              → External market data
- calculate_metrics()       → Statistical computations

When a user asks: "Show Q4 revenue trends vs industry averages"

The agent might:
1. Call query_fabric_data_agent("Q4 revenue by month")
2. Call search_api("Q4 industry average revenue")
3. Call calculate_metrics(both results) for comparison
4. Synthesize and return complete answer

The agent decides the sequence automatically based on the question.
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

    Common Approaches:
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

    Then the agent can call query_database() alongside other tools.
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
        1. Receives parameters from the LLM with annotated types and descriptions
        2. Delegates to a service (injected in __init__)
        3. Returns results back to the LLM as strings

        Tool Pattern:
        - Define tool function with parameters annotated using Annotated[type, Field(...)]
        - Include descriptive docstring for the LLM
        - Implement try/except for error handling
        - Call self.tools.append(tool_function) to register

        Current tools registered:
        - query_fabric_data_agent: Query business/financial data from Fabric
        - query_sql_database: Query operational data from SQL (template)

        To add more tools, follow the existing pattern in this method.
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
        # TOOL 2: Query SQL Database (Operational Data Source)
        # ====================================================================
        # UNCOMMENT AND CONFIGURE WHEN YOU HAVE A SQL DATABASE SERVICE
        # def query_sql_database(
        #     question: Annotated[
        #         str,
        #         Field(
        #             description=(
        #                 "Natural language question about operational data. "
        #                 "Use for questions about records, aggregations, or analysis "
        #                 "from SQL databases."
        #             )
        #         ),
        #     ]
        # ) -> str:
        #     """Query the SQL database for operational data."""
        #     try:
        #         logger.info("SQL Database query", question=question)
        #         result = self.sql_database_service.query(question)
        #         return result
        #     except Exception as e:
        #         logger.error("SQL Database query failed", error=str(e))
        #         return f"Error: {str(e)}"
        #
        # self.tools.append(query_sql_database)

        # ====================================================================
        # TOOL ADDITION TEMPLATE - Copy/paste and customize for each source
        # ====================================================================
        # def query_my_source(
        #     query: Annotated[
        #         str,
        #         Field(
        #             description="Natural language query for my data source"
        #         ),
        #     ]
        # ) -> str:
        #     """Query my custom data source."""
        #     try:
        #         logger.info("My source query", query=query)
        #         result = self.my_service.query(query)
        #         return result
        #     except Exception as e:
        #         logger.error("My source query failed", error=str(e))
        #         return f"Error: {str(e)}"
        #
        # self.tools.append(query_my_source)

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


