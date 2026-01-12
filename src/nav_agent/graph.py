""" LangGraph NAV agent with file upload support.

This agent integrates with NAV (Net Asset Value) management APIs, featuring:
- Tool-calling agent with AWS Bedrock (Claude)
- File upload handling for NAV processing
- User authorization based on scope and role
- Human-in-the-loop approval for write operations
- Comprehensive error handling and logging
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

import httpx
from langchain.tools import tool
from langchain_core.messages import BaseMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
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
    scope: list[str]


class Context(TypedDict):
    """Context parameters for the agent.

    Set these when creating assistants OR when invoking the graph.
    
    """

    thread_id: str
    user: UserContext


class AgentState(TypedDict):
    """State schema for the NAV agent.

    Follows the MessagesState pattern for chat-based agents.
    
    """

    messages: Annotated[list[BaseMessage], "The conversation messages"]


AGENT_SYSTEM_PROMPT = """You are a helpful NAV (Net Asset Value) management agent with access to tools.

When handling file uploads:
- Extract the file path from the user message
- Call the upload_nav_file tool with the exact path
- When the tool returns a response, ALWAYS prefix it with a success indicator and return it directly to the user
- Do NOT add extra commentary or modify the tool response

Guidelines:
- Always be explicit about what operation you're performing
- When a user uploads a file, they will provide the local file path - use it exactly as provided
- For file uploads, return the tool response exactly as provided by the API
- Provide a clear status message to the user about what happened
- NAV files should be in JSON format
"""


def _get_api_base_url() -> str:
    """Get the NAV API base URL from environment."""
    return os.getenv("NAV_API_BASE_URL", "http://localhost:8080")


@tool
def upload_nav_file(file_path: str) -> str:
    """Upload a NAV (Net Asset Value) file for processing.

    This tool handles file uploads that cannot be passed through MCP.
    It reads the NAV file and sends it to the /api/nav/upload endpoint.
    The file will be stored locally, uploaded to S3, and queued for NAV parsing.

    Args:
        file_path: Local path to the NAV file to upload (JSON format)

    Returns:
        Upload result from the API
    """
    try:
        if not os.path.exists(file_path):
            return f"Error: File not found at {file_path}"

        # Validate file extension
        if not file_path.lower().endswith(".json"):
            logger.warning(f"File {file_path} is not a JSON file")

        with open(file_path, "rb") as f:
            file_content = f.read()

        if not file_content:
            return "Error: File is empty"

        file_name = os.path.basename(file_path)
        files = {"file": (file_name, file_content)}

        api_url = _get_api_base_url()
        logger.info(f"Uploading NAV file to {api_url}/api/nav/upload")
        
        response = httpx.post(
            f"{api_url}/api/nav/upload",
            files=files,
            timeout=30.0,
        )

        logger.info(f"Upload response status: {response.status_code}")
        logger.info(f"Upload response body: {response.text}")

        if response.status_code == 200:
            try:
                # Try to parse as JSON and return formatted response
                result_json = response.json()
                result_str = json.dumps(result_json, indent=2)
            except:
                # Fallback to raw text if JSON parsing fails
                result_str = response.text
            
            logger.info(
                f"NAV file uploaded successfully: {file_name} "
                f"(user: {os.getenv('CURRENT_USER_ID', 'unknown')})"
            )
            return result_str
        else:
            error_msg = f"Upload failed with status {response.status_code}"
            logger.error(f"{error_msg}: {response.text}")
            return f"Error: {error_msg}. Details: {response.text}"

    except Exception as e:
        logger.error(f"NAV file upload error: {str(e)}")
        return f"Error uploading NAV file: {str(e)}"


@tool
def check_nav_service_health() -> str:
    """Check if the NAV upload service is running and healthy.

    This tool performs a health check on the NAV service.

    Returns:
        Health status of the NAV service
    """
    try:
        api_url = _get_api_base_url()
        response = httpx.get(
            f"{api_url}/api/nav/health",
            timeout=10.0,
        )

        if response.status_code == 200:
            logger.info("NAV service health check passed")
            return response.text
        else:
            error_msg = f"Health check failed with status {response.status_code}"
            logger.warning(error_msg)
            return f"Error: {error_msg}"

    except Exception as e:
        logger.error(f"NAV service health check error: {str(e)}")
        return f"Error checking NAV service health: {str(e)}"


async def _get_tools(user_context: UserContext) -> list[Any]:
    """Initialize and retrieve tools for NAV agent.

    Includes custom tools and those from configured MCP servers.
    Only returns tools that user has access to based on scope.

    Args:
        user_context: User authorization context with scope

    Returns:
        List of authorized LangChain Tool objects
    """
    tools_list = [upload_nav_file, check_nav_service_health]

    try:
        from langchain_mcp_adapters import ClientMCPManager
    except ImportError as e:
        logger.warning(f"langchain-mcp-adapters not installed: {e}")
        return tools_list

    mcp_config_str = os.getenv("MCP_SERVERS", "{}")

    try:
        config = json.loads(mcp_config_str)
        servers = {}
        for server in config.get("servers", []):
            servers[server["name"]] = {
                "type": server["type"],
                "url": server["url"],
            }
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Failed to parse MCP_SERVERS: {e}")
        return tools_list

    if not servers:
        logger.debug("No MCP servers configured")
        return tools_list

    user_scope = user_context.get("scope", [])
    # Parse scope string if it's a string
    if isinstance(user_scope, str):
        user_scope = user_scope.split(" ")
        
    user_roles = user_context.get("roles", [])

    # 1. SCOPE CHECK: Must have "mutual funds"
    if "mutual funds" not in user_scope:
         logger.warning(f"User {user_context.get('user_id')} missing required scope 'mutual funds' for NAV Agent")
         return []

    # 2. ROLE CHECK: Must be "fundhouse" (or "admin" if we want to allow admins)
    allowed_roles = {"fundhouse"}
    user_role_set = set(user_roles)
    if not user_role_set.intersection(allowed_roles):
        logger.warning(f"User {user_context.get('user_id')} missing required role 'fundhouse' for NAV Agent")
        return []

    for server_name, server_config in servers.items():
        # Authorization: Only load tools from servers in user scope 
        # (This is legacy scope check for specific servers, we can keep or relax it)
        if server_name not in user_scope:
             # Relaxing this since "mutual funds" is the main gatekeeper now
             # logger.debug(f"User not authorized for server: {server_name}")
             # continue
             pass

        try:
            mcp_config = {
                server_name: {
                    "type": server_config["type"],
                    "url": server_config["url"],
                }
            }

            async with ClientMCPManager(mcp_config) as mcp:
                mcp_tools = await mcp.get_tools(server_name)
                logger.info(
                    f"Loaded {len(mcp_tools)} tools from {server_name} "
                    f"(authorized for user {user_context.get('user_id')})"
                )
                tools_list.extend(mcp_tools)
        except Exception as e:
            logger.error(f"Failed to load tools from {server_name}: {e}")
            continue

    return tools_list


def _is_write_operation(tool_name: str) -> bool:
    """Determine if a tool call represents a write operation requiring approval.

    Args:
        tool_name: Name of the tool being called

    Returns:
        True if the operation is a write/mutating operation requiring approval
    """
    # Tools that are safe and don't require approval
    safe_tools = ["upload_nav_file", "check_nav_service_health"]
    if tool_name in safe_tools:
        return False
    
    # Other write operations that require approval
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
        if not user_context:
            logger.warning("No user context found. Using default 'test_user' for development.")
            user_context = {
                "user_id": "test_user",
                "role": "admin",
                "scope": ["mcp-agent", "order-agent", "nav-agent", "router-agent"]
            }
            # raise ValueError("User context is required in config")

        # Initialize tools based on user authorization
        tools_list = await _get_tools(user_context)

        # Initialize Bedrock model with tools
        model = ChatBedrock(
            model_id=os.getenv(
                "BEDROCK_MODEL_ID",
                "anthropic.claude-3-5-sonnet-20241022-v2:0",
            ),
            region_name=os.getenv("AWS_REGION", "us-east-1"),
            temperature=0,
            max_tokens=4096,
        )

        model_with_tools = model.bind_tools(tools_list)

        # Create system message
        system_msg = SystemMessage(content=AGENT_SYSTEM_PROMPT)

        # Invoke the model
        response = model_with_tools.invoke([system_msg] + state["messages"])

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

    # If the LLM made tool calls, route to tool handler
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "handle_tool_calls"

    # Otherwise, end the conversation
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
    from langgraph.types import Interrupt
    
    messages = state["messages"]
    last_message = messages[-1]
    user_context = config.get("configurable", {}).get("user", {})
    if not user_context:
         # Fallback for dev
         user_context = {
            "user_id": "test_user",
            "role": "admin",
            "scope": ["mcp-agent", "order-agent", "nav-agent", "router-agent"]
        }

    if not hasattr(last_message, "tool_calls"):
        return {"messages": []}

    tool_calls = last_message.tool_calls
    results = []

    # Initialize tools
    tools_list = await _get_tools(user_context)
    tools_by_name = {tool.name: tool for tool in tools_list}

    # Process each tool call
    for tool_call in tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call.get("args", {})

        logger.info(
            f"Processing tool call: {tool_name} for user {user_context.get('user_id')}"
        )

        # Check if this is a write operation requiring approval
        if _is_write_operation(tool_name):
            # Request human approval for write operations
            approval_response = interrupt(
                {
                    "action": tool_name,
                    "args": tool_args,
                    "description": f"🔒 Write Operation Approval Required\n\n"
                    f"Tool: {tool_name}\n"
                    f"Arguments: {tool_args}\n\n"
                    f"Please review and approve this operation before proceeding.",
                }
            )

            # If the response is a Command with resume, continue
            # Otherwise wait for human input
            if isinstance(approval_response, Command):
                if approval_response.resume and approval_response.resume.get(
                    "type"
                ) in ["approve", "edit"]:
                    # Use edited args if provided
                    if approval_response.resume.get("args"):
                        tool_args = approval_response.resume["args"]
                    logger.info(
                        f"Write operation approved: {tool_name} "
                        f"(user: {user_context.get('user_id')})"
                    )
                else:
                    # Operation rejected
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

        # Execute the tool
        if tool_name in tools_by_name:
            tool = tools_by_name[tool_name]
            try:
                observation = await tool.ainvoke(tool_args)
                logger.info(f"Tool execution successful: {tool_name}")
                
                # For upload_nav_file, ensure we return the response as-is
                if tool_name == "upload_nav_file" and isinstance(observation, str):
                    # If the response looks like JSON, keep it clean
                    if observation.strip().startswith("{") or observation.strip().startswith("["):
                        observation = f"✓ File uploaded successfully!\n\n{observation}"
                    elif not observation.startswith("Error"):
                        observation = f"✓ {observation}"
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


async def finalize_response(
    state: AgentState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Convert tool results to final response for the user.

    Takes ToolMessage results and converts them to readable AIMessages.

    Args:
        state: Current agent state with tool results
        config: Runtime configuration

    Returns:
        Updated state with final AIMessage for user
    """
    from langchain_core.messages import AIMessage
    
    messages = state["messages"]
    
    # Look for ToolMessages in the results
    tool_results = []
    for msg in messages:
        if isinstance(msg, ToolMessage):
            tool_results.append(msg.content)
    
    if tool_results:
        # Combine all tool results into a single response
        combined_response = "\n\n".join(tool_results)
        logger.info("Converting tool results to final response")
        return {"messages": [AIMessage(content=combined_response)]}
    
    # If no tool results, return empty
    return {"messages": []}

async def create_agent_graph() -> StateGraph:
    """Create and compile the agent graph.

    The graph follows this flow:
    1. START → call_model (LLM decides what to do)
    2. call_model → should_continue (Check if tools were called)
    3. handle_tool_calls → call_model (Execute tools and loop back)
    4. → END (Model responds directly to user)

    Returns:
        Compiled LangGraph StateGraph
    """
    # Initialize checkpointer
    # checkpointer = await initialize_checkpointer()

    # Create state graph
    graph = StateGraph(AgentState, config_schema=Context)

    # Add nodes
    graph.add_node("call_model", call_model)
    graph.add_node("handle_tool_calls", handle_tool_calls)
    graph.add_node("finalize_response", finalize_response)

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
    # After tool execution, finalize the response
    graph.add_edge("handle_tool_calls", "finalize_response")
    
    # Final response goes to end
    graph.add_edge("finalize_response", END)

    # Compile with checkpointer for persistence
    compiled_graph = graph.compile(
        name="nav-agent"
    )

    logger.info("NAV agent graph compiled successfully")
    return compiled_graph


# Initialize graph at module level for use by LangGraph CLI

# Lazy initialization to avoid asyncio.run() conflicts
_graph_instance = None

def get_graph():
    global _graph_instance
    if _graph_instance:
        return _graph_instance
        
    try:
        current_loop = asyncio.get_running_loop()
        logger.info("Detected running event loop, graph will be lazily initialized")
        
        # Re-using create_agent_graph logic synchronously where possible 
        graph = StateGraph(AgentState, config_schema=Context)
        graph.add_node("call_model", call_model)
        graph.add_node("handle_tool_calls", handle_tool_calls)
        graph.add_node("finalize_response", finalize_response)
        graph.add_edge(START, "call_model")
        graph.add_conditional_edges(
            "call_model",
            _should_continue,
            {
                "handle_tool_calls": "handle_tool_calls",
                END: END,
            },
        )
        graph.add_edge("handle_tool_calls", "finalize_response")
        graph.add_edge("finalize_response", END)
        
        _graph_instance = graph.compile(name="nav-agent")
        logger.info("NAV Agent graph compiled successfully")
        return _graph_instance
        
    except RuntimeError:
        # No running event loop (e.g. CLI usage), safe to run async setup
        return asyncio.run(create_agent_graph())

# For backward compatibility with LangGraph CLI
if __name__ == "__main__":
    graph = asyncio.run(create_agent_graph())
else:
    # When imported, try to get graph if safe, otherwise rely on get_graph()
    try:
        asyncio.get_running_loop()
        # Don't init yet, let router call get_graph()
        graph = None 
    except RuntimeError:
        graph = asyncio.run(create_agent_graph())
