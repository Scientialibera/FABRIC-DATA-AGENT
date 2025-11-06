# Multi-Source AI Assistant

Enterprise-grade Python application using Microsoft's Agent Framework. The LLM autonomously decides which tools to call, chains them, and synthesizes answers. That's the entire pattern.

## Documentation

**Start here:**
- **[ADD_NEW_TOOL.md](docs/ADD_NEW_TOOL.md)** - Step-by-step guide to add a new tool (recommended first read)
- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System design, data flows, and component relationships
- **[TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** - Debug guide and common issues
- **[SUMMARY.md](docs/SUMMARY.md)** - System overview and quick reference

## Quick Start

```bash
# Setup
git clone <repo>
cd fabric-data-agent
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your settings

# Run tests
python tests/test_agentic_queries.py
```

---

# The Pattern

```
Query comes in
       ↓
LLM sees question + available tools
       ↓
LLM decides: "Do I need a tool?"
       ├─ NO  → Return answer (DONE)
       └─ YES → Call tool(s)
              ↓
           Tool executes → returns result
              ↓
           Result added to conversation context
              (LLM will see it)
              ↓
           LLM decides: "Answer or call another tool?"
              ├─ ANSWER → Return answer (DONE)
              └─ TOOL   → Loop (go back)
```

This pattern applies to any LLM-based agent: the LLM makes tool decisions automatically because it sees all results in context.

---

# Adding Tools - Dynamic Discovery Pattern

This system uses **automatic tool discovery** based on a strict naming convention. Add a new tool by simply creating 3 files - no code changes needed!

## The Naming Convention

Tools are auto-discovered using this 1:1:1 mapping:

```
config/tools/<NAME>.json         ← Tool config (metadata)
         ↓
src/<NAME>/service.py            ← Service implementation  
         ↓
self.<name>_service              ← Service instance (optional - auto-created if missing)
```

## Step 1: Create Tool Configuration

**File: `config/tools/<NAME>.json`**

```json
{
  "type": "function",
  "function": {
    "name": "query_sql_database",
    "description": "Query SQL database for operational data",
    "parameters": {
      "type": "object",
      "properties": {
        "reasoning": {
          "type": "string",
          "description": "Why are you calling this tool?"
        },
        "query": {
          "type": "string",
          "description": "Natural language question (NOT SQL)"
        }
      },
      "required": ["reasoning", "query"]
    }
  }
}
```

## Step 2: Create Service Class

**File: `src/<NAME>/service.py`**

```python
class SqlDatabaseService:
    """Query operational data from SQL database."""
    
    def run(self, tool_call: dict) -> str:
        """
        Execute query.
        
        Args:
            tool_call: Dict with parameters (query, reasoning, etc)
        
        Returns:
            String result
        """
        query = tool_call.get('query', '')
        reasoning = tool_call.get('reasoning', '')
        
        # Your query logic here
        results = self._execute_query(query)
        return str(results)
    
    def _execute_query(self, query: str) -> str:
        # Implementation
        pass


def get_sql_database_service() -> SqlDatabaseService:
    """Factory function for service creation."""
    return SqlDatabaseService()
```

## That's It!

Tool loader automatically:
1. Discovers `config/tools/sql_database.json`
2. Finds or creates `self.sql_database_service`
3. Creates and registers `query_sql_database()` function
4. Agent can now use the tool

No code changes needed to `_load_tools()` or anywhere else! Services are created dynamically using the naming convention.

---

## System Prompt Configuration

After adding tools, update `config/system_prompt.txt` to help the LLM understand the available tools and when to use them.

**Why update the system prompt?**
- Tells the LLM which tools exist and what they're for
- Provides context about data sources (Fabric, SQL, API, etc.)
- Helps the LLM decide which tool to use for different questions
- Enables better tool chaining (combining results from multiple tools)

**Example system prompt snippet:**

```
You are an AI assistant with access to multiple data sources:

1. Fabric Data Agent - Query business/financial data
   - Use for: revenue, sales, customer data, KPIs
   - Available in: Power BI semantic models, warehouses, lakehouses

2. SQL Database - Query operational data
   - Use for: customer records, orders, transactions
   - Available in: Corporate SQL Server

3. External API - Search market data
   - Use for: industry benchmarks, competitor data, market trends

When a user asks a question:
- Determine which tool(s) have the data they need
- Call the appropriate tool(s)
- Combine results if needed
- Provide a synthesized answer

Example: "Show Q4 revenue vs industry average"
  → Call: query_fabric_data_agent("Q4 revenue")
  → Call: search_api("Q4 industry average")
  → Synthesize and compare both results
```

**Key tips:**
- Be specific about what data each tool accesses
- Give examples of questions for each tool
- Explain when to use multiple tools together
- Update this whenever you add or remove tools

---

## Done!

Agent Framework automatically:
- Adds tool to LLM's available tools
- LLM calls it when needed
- Feeds result back to LLM context
- LLM chains with other tools (because it sees all results)

No routing. No orchestration. Just services + tools.

---

# Example: SQL Database Tool

To add SQL database querying capability:

## File: `config/tools/database.json`

```json
{
  "name": "query_sql_database",
  "description": "Query the SQL database for business operational data",
  "connection": {
    "server": "your-server.database.windows.net",
    "database": "your_database",
    "auth": "managed_identity"
  },
  "example_queries": [
    "How many orders in Q4?",
    "Top 10 customers by revenue",
    "Monthly sales trend"
  ]
}
```

## File: `src/database/service.py`

```python
import pyodbc
from typing import Optional

class SQLDatabaseService:
    """Query SQL database using natural language."""
    
    def __init__(self, server: str, database: str, auth_type: str = "managed_identity"):
        self.server = server
        self.database = database
        self.auth_type = auth_type
        self.connection: Optional[pyodbc.Connection] = None
    
    def connect(self):
        """Establish database connection."""
        if self.auth_type == "managed_identity":
            # Use DefaultAzureCredential for managed identity
            from azure.identity import DefaultAzureCredential
            token = DefaultAzureCredential().get_token("https://database.windows.net")
            connection_string = (
                f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={self.server};"
                f"DATABASE={self.database};UID=;PWD={token.token};"
            )
        else:
            # Use connection string
            connection_string = (
                f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={self.server};"
                f"DATABASE={self.database};"
            )
        
        self.connection = pyodbc.connect(connection_string)
    
    def query(self, question: str) -> str:
        """Execute query based on natural language question."""
        try:
            if not self.connection:
                self.connect()
            
            # TODO: Convert natural language to SQL using LLM
            # Or: Execute predefined queries based on keywords
            
            cursor = self.connection.cursor()
            # cursor.execute(sql_query)
            # results = cursor.fetchall()
            # return format_results(results)
            
            return "Query results..."
        except Exception as e:
            return f"Error querying database: {str(e)}"
    
    def close(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
```

## File: `src/ai/assistant.py` - Update `__init__`

```python
def __init__(self, aoai_settings: AzureOpenAISettings) -> None:
    self.fabric_service = get_fabric_service()
    
    # ADD THIS - New SQL database service
    self.sql_database_service = SQLDatabaseService(
        server="your-server.database.windows.net",
        database="your_database"
    )
    
    # ... rest of init ...
```

## File: `src/ai/assistant.py` - Update `_load_tools()`

```python
def _load_tools(self) -> None:
    """Register all tools."""
    
    # ... existing tools ...
    
    # ADD THIS - New SQL database tool
    def query_sql_database(
        question: Annotated[
            str,
            Field(
                description=(
                    "Natural language question about business data. "
                    "Use for operational queries (orders, customers, inventory, etc)"
                )
            )
        ]
    ) -> str:
        """Query SQL database for operational business data."""
        try:
            logger.info("SQL database query", question=question)
            result = self.sql_database_service.query(question)
            logger.info("SQL query completed", question=question)
            return result
        except Exception as e:
            logger.error("SQL database query failed", error=str(e))
            return f"Error: {str(e)}"
    
    self.tools.append(query_sql_database)
```

## Result

Now the LLM can use multiple tools:
- `query_fabric_data_agent()` - For financial/business metrics from Fabric
- `query_sql_database()` - For operational data from SQL

When user asks "Compare Q4 revenue with monthly sales trends", the LLM will:
1. Call `query_fabric_data_agent()` for revenue
2. Call `query_sql_database()` for monthly sales
3. Synthesize both results into final answer

---

# Multi-Tool Scenario

**User**: "Show Q4 revenue and compare to monthly sales trend"

```
LLM sees available tools:
  - query_fabric_data_agent()
  - query_sql_database()

LLM reasoning:
  "Need financial metrics AND operational trends"

1. Calls query_fabric_data_agent("Q4 revenue")
   → Returns: "Q4 revenue: $50M (up 15% QoQ)"
   → Added to context

2. Calls query_sql_database("monthly sales trend 2024")
   → Returns: "Jan: $10M, Feb: $11M, ... Dec: $15M"
   → Added to context

3. LLM sees both results
   → Synthesizes: "Q4 (Oct-Dec avg: $13.3M) shows strong 
                   growth trend throughout year"
   → Returns answer
```

The LLM combines results automatically because it sees all tool outputs in context.

---

# Multi-Tool Scenario

**User**: "Show Q4 revenue and compare to industry average"

```
LLM sees available tools:
  - query_fabric_data_agent()
  - search_external_api()

LLM reasoning:
  "Need both internal and external data"

1. Calls query_fabric_data_agent("Q4 revenue")
   → Returns: "$50M"
   → Added to context

2. Calls search_external_api("industry average")
   → Returns: "$45M"
   → Added to context

3. LLM sees both results in context
   → Synthesizes: "Our $50M is 11% above industry $45M"
   → Returns answer
```

**The LLM did all the combining automatically** because it saw both tool results.

---

# Project Structure

```
src/
├── ai/
│   └── assistant.py              # All tools registered here
├── fabric_agent/
│   ├── client.py
│   └── service.py
├── database/                     # YOUR new service
│   └── service.py
└── config/
    └── settings.py

tests/
└── test_agentic_queries.py

config/
├── system_prompt.txt
└── .env

requirements.txt
README.md (this file)
```

---

# Naming

**Services**: `{Source}Service`
- `FabricAgentService`
- `DatabaseService`
- `ExternalAPIService`

**Tools**: `query_{source}` or `{action}_{source}`
- `query_fabric_data_agent`
- `query_database`
- `search_external_api`

---

# Configuration

## `.env` (Your Settings)

```bash
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4o
DATA_AGENT_URL=https://api.fabric.microsoft.com/v1/workspaces/xxx/...
TENANT_ID=your-tenant-id

# Optional (uses defaults if not set)
# AZURE_OPENAI_TEMPERATURE=0.7
# AZURE_OPENAI_MAX_TOKENS=2000
```

## `config/src/settings.py`

Contains defaults and validation. Load with:

```python
from config.src.settings import AzureOpenAISettings
settings = AzureOpenAISettings.from_env()
```

---

# System Prompt

**File: `config/system_prompt.txt`**

Tells LLM what tools exist and when to use them:

```
You have access to:

1. query_fabric_data_agent() - Financial data (revenue, expenses, balances)
2. query_database() - Operational data (orders, customers, inventory)

Use the tools you need. Results are added to conversation.
Call multiple tools if you need different data sources.
```

---

# Using as MCP Server

Expose the AI Assistant as a Model Context Protocol (MCP) server to use it as a tool in MCP-compatible clients (VS Code Copilot Agents, Claude, etc.).

## Enable MCP

**Option 1: Environment Variable (`recommended for production`)**

```bash
# In .env file
ENABLE_MCP_SERVER=true
```

**Option 2: Configuration File**

**File: `src/config/settings.py`**

```python
# Set to True to expose the agent as an MCP server
ENABLE_MCP_SERVER = True
```

## Run MCP Server

```bash
python tests/mcp_server.py
```

The agent is now available as a tool to any MCP-compatible client.

---

# Testing

```python
import asyncio
from src.ai.assistant import AIAssistant
from config.src.settings import AzureOpenAISettings


async def test():
    settings = AzureOpenAISettings.from_env()
    assistant = AIAssistant(aoai_settings=settings)
    
    result = await assistant.process_question(
        "Show top 5 orders"
    )
    
    print(f"Success: {result['success']}")
    print(f"Response: {result['response']}")


asyncio.run(test())
```

---

# How Agent Framework Works Behind The Scenes

When you call `process_question(question)`:

1. All functions in `self.tools` are registered with the LLM
2. LLM receives: question + list of available tools
3. LLM decides: "Which tool(s) do I need?"
4. If tool chosen: Execute it, get result
5. Add result to conversation context
6. Go to step 2 (LLM sees everything: original question + all tool results)
7. Repeat until LLM answers without tools

**You provide**: Services (data access) + Tools (function signatures)
**Agent Framework provides**: Looping, context management, routing

---

# That's Everything

The whole architecture:
- **Services**: Know how to query data sources
- **Tools**: Wrap services with Annotated parameters so LLM can call them
- **LLM**: Decides which tools to use and chains them automatically
- **Agent Framework**: Handles all the complex looping and context management

No patterns. No orchestration. No routing logic. Just define tools, let LLM use them.

---

**Built with:** Python 3.12 | Azure OpenAI | Microsoft Agent Framework

**Status:** Production Ready ✨
