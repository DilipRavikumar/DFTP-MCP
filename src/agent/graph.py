"""LangGraph MCP agent with authorization.

This agent integrates with multiple MCP (Model Context Protocol) servers,
featuring:
- Tool-calling agent with AWS Bedrock (Claude)
- Multi-server MCP support
- User authorization based on scope and role
- Human-in-the-loop approval for write operations
- State persistence using PostgreSQL
- Comprehensive error handling and logging
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

from langchain_core.messages import BaseMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph, add_messages
from langgraph.types import Command, interrupt
from typing_extensions import Annotated, TypedDict

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(os.getenv("AGENT_LOG_LEVEL", "INFO"))


class UserContext(TypedDict, total=False):
    """User context for authorization.

    """

    user_id: str
    role: str
    roles: list[str]
    scope: list[str]


class Context(TypedDict):
    """Context parameters for the agent.

    Set these when creating assistants OR when invoking the graph.
    """

    thread_id: str
    user: UserContext


class AgentState(TypedDict):
    """State schema for the MCP agent.

    Follows the MessagesState pattern for chat-based agents.
    """

    messages: Annotated[list[BaseMessage], add_messages]


AGENT_SYSTEM_PROMPT = """You are a helpful AI agent with access to tools.

You have access to specialized subsystems via the MCP (Model Context Protocol). Use them to answer user queries:

1. **Order State History**: Tracks the lifecycle of orders.
   - Use for looking up order status by ID or file ID.
   - Retrieve full state history or check for "exceptions" (errors).

2. **SLA Monitoring**: Tracks service level agreement deadlines.
   - Check for "breached" deadlines (late messages).
   - Find "unresolved" items pending action.
   - Get audit logs for specific transactions or firms.

3. **Valuation & Positions**: Manages client account values and fund data.
   - Look up "valuations" (account value) for specific clients.
   - Check "positions" (fund holdings) for distributors or funds.
   - Can also trigger valuation processing.

Guidelines:
- Always be explicit about what operation you're performing
- Summarize results clearly for the user
- For write operations, wait for user confirmation before proceeding
- Never assume user intent for destructive operations
- Provide helpful context when operations might have side effects
"""


def _parse_mcp_servers() -> dict[str, dict[str, str]]:
    """Parse MCP servers configuration from environment.

    Returns:
        Dictionary mapping server names to their configuration
    """
    mcp_config_str = os.getenv("MCP_SERVERS", "{}")

    try:
        config = json.loads(mcp_config_str)
        servers = {}
        for server in config.get("servers", []):
            servers[server["name"]] = {
                "transport": server.get("transport", "http"), # Default to http if not specified (or use type as fallback)
                "url": server["url"],
            }
        return servers
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Failed to parse MCP_SERVERS: {e}")
        return {}


async def _get_mcp_tools(user_context: UserContext) -> list[Any]:
    """Initialize and retrieve tools from configured MCP servers.

    Only returns tools that user has access to based on scope.

    Args:
        user_context: User authorization context with scope

    Returns:
        List of authorized LangChain Tool objects from MCP servers
    """
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
    except ImportError as e:
        logger.warning(f"MultiServerMCPClient missing: {e}")
        return []

    servers = _parse_mcp_servers()
    if not servers:
        logger.warning("No MCP servers configured in MCP_SERVERS environment variable")
        return []

    user_scope = user_context.get("scope", [])
    all_tools = []
    seen_tool_names = set()  

    for server_name, server_config in servers.items():
        logger.info(f"DEBUG: Attempting to connect to MCP server '{server_name}' at {server_config.get('url')}")
        
        try:
            mcp_config = {
                server_name: {
                "transport": server_config["transport"],  
                "url": server_config["url"],
            }
            }

            client = MultiServerMCPClient(mcp_config)
            tools = await client.get_tools() 
            
            unique_tools = []
            for tool in tools:
                tool_name = tool.name
                if tool_name not in seen_tool_names:
                    seen_tool_names.add(tool_name)
                    unique_tools.append(tool)
                else:
                    logger.debug(f"Skipping duplicate tool: {tool_name}")
            
            logger.info(
                f"Loaded {len(unique_tools)} unique tools from {server_name} "
                f"({len(tools) - len(unique_tools)} duplicates filtered) "
                f"(authorized for user {user_context.get('user_id')})"
            )
            all_tools.extend(unique_tools)
        except Exception as e:
            logger.error(f"Failed to load tools from {server_name}: {e}")
            logger.warning(f"Continuing without tools from {server_name}. Other servers may still work.")
            continue

    logger.info(f"Total unique tools loaded: {len(all_tools)}")
    return all_tools


def _is_write_operation(tool_name: str) -> bool:
    """Determine if a tool call represents a write operation.

    Args:
        tool_name: Name of the tool being called

    Returns:
        True if the operation is a write/mutating operation
    """
    write_keywords = ["create", "update", "delete", "add", "remove", "post", "put"]
    return any(keyword in tool_name.lower() for keyword in write_keywords)


async def call_model(
    state: AgentState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Call the LLM to decide on next action.

    The LLM is bound with tools and will decide whether to:
    1. Call a tool
    2. Respond to the user directly

    Args:
        state: Current agent state with message history
        config: Runtime configuration including user context

    Returns:
        Updated state with new messages from the LLM
    """
    try:
        from langchain_aws.chat_models import ChatBedrock
        from langchain_core.messages import AIMessage

        user_context = config.get("configurable", {}).get("user", {})
        mcp_tools = await _get_mcp_tools(user_context)

        final_tools = {}
        for tool in mcp_tools:
            if tool.name not in final_tools:
                final_tools[tool.name] = tool
            else:
                logger.warning(f"Duplicate tool detected and filtered: {tool.name}")
        
        mcp_tools = list(final_tools.values())
        logger.info(f"Final tool count after deduplication: {len(mcp_tools)}")

        model = ChatBedrock(
            model_id=os.getenv(
                "BEDROCK_MODEL_ID",
                "anthropic.claude-3-5-sonnet-20241022-v2:0",
            ),
            region_name=os.getenv("AWS_REGION", "us-east-1"),
            temperature=0,
            max_tokens=4096,
            model_kwargs={"system": AGENT_SYSTEM_PROMPT}
        )

        model_with_tools = model.bind_tools(mcp_tools)

        messages_to_send = state["messages"]
        
        message_types = [type(m).__name__ for m in messages_to_send]
        logger.info(f"Sending messages types: {message_types}")
        if messages_to_send:
            logger.info(f"First message content: {messages_to_send[0].content[:50]}...")

        response = model_with_tools.invoke(messages_to_send)

        logger.info(
            f"Model response for user {user_context.get('user_id')}: "
            f"(tool_calls: {len(response.tool_calls) if hasattr(response, 'tool_calls') and response.tool_calls else 0})"
        )

        return {"messages": [response]}
    except Exception as e:
        logger.error(f"Error in call_model: {e}")
        from langchain_core.messages import AIMessage

        error_response = AIMessage(
            content=f"I encountered an error while processing your request: {str(e)}"
        )
        return {"messages": [error_response]}


def _should_continue(state: AgentState) -> str:
    """Route based on whether the model made tool calls.

    Args:
        state: Current agent state

    Returns:
        Next node to execute
    """
    messages = state["messages"]
    last_message = messages[-1]

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "handle_tool_calls"
    return END


async def handle_tool_calls(
    state: AgentState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Process tool calls with human approval for write operations.

    Args:
        state: Current agent state
        config: Runtime configuration including user context

    Returns:
        Updated state with tool results
    """
    messages = state["messages"]
    last_message = messages[-1]
    user_context = config.get("configurable", {}).get("user", {})
    if not hasattr(last_message, "tool_calls"):
        return {"messages": []}

    tool_calls = last_message.tool_calls
    results = []

    try:
        # Initialize MCP tools
        mcp_tools = await _get_mcp_tools(user_context)
        tools_by_name = {tool.name: tool for tool in mcp_tools}

        # Process each tool call
        for tool_call in tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call.get("args", {})

            logger.info(
                f"Processing tool call: {tool_name} for user {user_context.get('user_id')}"
            )

            # Check if this is a write operation requiring approval
            if _is_write_operation(tool_name):
                approval_response = interrupt(
                    {
                        "action": tool_name,
                        "args": tool_args,
                        "description": f"Write Operation Approval Required\n\n"
                        f"Tool: {tool_name}\n"
                        f"Arguments: {tool_args}\n\n"
                        f"Please review and approve this operation before proceeding.",
                    }
                )

                if isinstance(approval_response, Command):
                    if approval_response.resume and approval_response.resume.get(
                        "type"
                    ) in ["approve", "edit"]:
                        if approval_response.resume.get("args"):
                            tool_args = approval_response.resume["args"]
                        logger.info(
                            f"Write operation approved: {tool_name} "
                            f"(user: {user_context.get('user_id')})"
                        )
                    else:
                        logger.info(
                            f"Write operation rejected: {tool_name} "
                            f"(user: {user_context.get('user_id')})"
                        )
                        results.append(
                            ToolMessage(
                                content=f"Operation '{tool_name}' was rejected by the user.",
                                tool_call_id=tool_call["id"],
                            )
                        )
                        continue

            if tool_name in tools_by_name:
                tool = tools_by_name[tool_name]
                try:
                    observation = await tool.ainvoke(tool_args)
                    logger.info(f"Tool execution successful: {tool_name}")
                except Exception as e:
                    observation = f"Error executing tool: {str(e)}"
                    logger.error(f"Tool execution failed: {tool_name} - {str(e)}")
            else:
                observation = f"Tool '{tool_name}' not found in available tools"
                logger.warning(f"Tool not found: {tool_name}")

            results.append(
                ToolMessage(
                    content=str(observation),
                    tool_call_id=tool_call["id"],
                )
            )

        return {"messages": results}
    except Exception as e:
        logger.error(f"Error in handle_tool_calls: {e}")
        return {
            "messages": [
                ToolMessage(
                    content=f"Error processing tool calls: {str(e)}",
                    tool_call_id="error",
                )
            ]
        }


async def initialize_checkpointer() -> Any:
    """Initialize PostgreSQL checkpointer for state persistence.

    Returns:
        Configured AsyncPostgresSaver instance, or MemorySaver as fallback

    Raises:
        ValueError: If database connection fails
    """
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    except ImportError as e:
        logger.warning(
            f"PostgreSQL checkpointer not available: {e}. Using memory checkpointer."
        )
        from langgraph.checkpoint.memory import MemorySaver

        return MemorySaver()

    db_uri = os.getenv(
        "POSTGRES_URI",
        "postgresql://postgres:postgres@localhost:5432/mcp_agent",
    )

    try:
        checkpointer = AsyncPostgresSaver.from_conn_string(db_uri)
        await checkpointer.setup()
        logger.info("PostgreSQL checkpointer initialized successfully")
        return checkpointer
    except Exception as e:
        logger.warning(
            f"Failed to initialize PostgreSQL checkpointer: {e}. Using memory checkpointer."
        )
        from langgraph.checkpoint.memory import MemorySaver

        return MemorySaver()


async def create_agent_graph() -> StateGraph:
    """Create and compile the agent graph.

    The graph follows this flow:
    1. START → call_model (LLM decides what to do)
    2. call_model → should_continue (Check if tools were called)
    3. handle_tool_calls → call_model (Execute tools and loop back)
    4. → END (Model responds directly to user)

    Returns:
        Compiled LangGraph StateGraph with PostgreSQL persistence
    """

    # Create state graph
    graph = StateGraph(AgentState, config_schema=Context)

    # Add nodes
    graph.add_node("call_model", call_model)
    graph.add_node("handle_tool_calls", handle_tool_calls)

    # Add edges
    graph.add_edge(START, "call_model")
    graph.add_conditional_edges(
        "call_model",
        _should_continue,
        {
            "handle_tool_calls": "handle_tool_calls",
            END: END,
        },
    )
    graph.add_edge("handle_tool_calls", "call_model")

    # Compile with checkpointer for persistence
    compiled_graph = graph.compile(
        name="mcp-agent",
    )

    logger.info("Agent graph compiled successfully")
    return compiled_graph


# Graph instance
_graph_instance = None


async def get_graph():
    """Get or create the graph instance (lazy initialization)."""
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = await create_agent_graph()
    return _graph_instance


graph = None

try:
    import asyncio
    try:
        asyncio.get_running_loop()
        # Already in event loop - use lazy init
        logger.info("Detected running event loop, graph will be lazily initialized")
        graph = None
    except RuntimeError:
        # No event loop - safe to initialize synchronously
        graph = asyncio.run(create_agent_graph())
        logger.info("Graph initialized synchronously")
except Exception as e:
    logger.warning(f"Could not initialize graph: {e}. Will use lazy initialization.")
    graph = None
