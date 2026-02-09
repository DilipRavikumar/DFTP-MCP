"""LangGraph order agent with file upload support.


This agent integrates with order management APIs, featuring:
- Tool-calling agent with AWS Bedrock (Claude)
- File upload handling for order processing
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


import httpx
from langchain.tools import tool
from langchain_aws import ChatBedrock
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
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
    """State schema for the order agent.


    Follows the MessagesState pattern for chat-based agents.
    """


    messages: Annotated[list[BaseMessage], add_messages]




AGENT_SYSTEM_PROMPT = """You are a helpful order management agent with access to tools.


Guidelines:
- Always be explicit about what operation you're performing
- Summarize results clearly for the user
- For write operations, wait for user confirmation before proceeding
- Never assume user intent for destructive operations
- Provide helpful context when operations might have side effects
- For file uploads, confirm the file details before processing
"""




def _get_api_base_url() -> str:
    """Get the order API base URL from environment."""
    return os.getenv("ORDER_API_BASE_URL", "http://localhost:8082")




@tool
def upload_order_file(file_path: str, key: str | None = None) -> str:
    """Upload a file to S3 via the order API.


    This tool handles file uploads that cannot be passed through MCP.
    It reads the file and sends it to the /order/upload endpoint.


    Args:
        file_path: Local path to the file to upload
        key: Optional S3 key/path for the uploaded file


    Returns:
        Upload result from the API
    """
    try:
        if not os.path.exists(file_path):
            return f"Error: File not found at {file_path}"


        with open(file_path, "rb") as f:
            file_content = f.read()


        file_name = os.path.basename(file_path)
        files = {"file": (file_name, file_content)}
        params = {}
        if key:
            params["key"] = key


        api_url = _get_api_base_url()
        response = httpx.post(
            f"{api_url}/order/upload",
            files=files,
            params=params,
            timeout=30.0,
        )


        if response.status_code == 200:
            result = response.json()
            logger.info(
                f"File uploaded successfully: {file_name} "
                f"(user: {os.getenv('CURRENT_USER_ID', 'unknown')})"
            )
            return json.dumps(result)
        else:
            error_msg = f"Upload failed with status {response.status_code}"
            logger.error(f"{error_msg}: {response.text}")
            return f"Error: {error_msg}. Details: {response.text}"


    except Exception as e:
        logger.error(f"File upload error: {str(e)}")
        return f"Error uploading file: {str(e)}"




async def _get_tools(user_context: UserContext) -> list[Any]:
    """Initialize and retrieve tools for order agent.


    Includes custom tools and those from configured MCP servers.
    Only returns tools that user has access to based on scope.


    Args:
        user_context: User authorization context with scope


    Returns:
        List of authorized LangChain Tool objects
    """
    tools_list = [upload_order_file]


    try:
        from langchain_mcp_adapters import ClientMCPManager
    except ImportError as e:
        logger.warning(f"langchain-mcp-adapters not installed: {e}")
        return tools_list


    mcp_config_str = os.getenv("ORDER_MCP_SERVERS", "{}")


    try:
        config = json.loads(mcp_config_str)
        servers = {}
        for server in config.get("servers", []):
            servers[server["name"]] = {
                "type": server["type"],
                "url": server["url"],
            }
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Failed to parse ORDER_MCP_SERVERS: {e}")
        return tools_list


    if not servers:
        logger.debug("No MCP servers configured")
        return tools_list


    user_scope = user_context.get("scope", [])
    # Parse scope string if it's a string (e.g. from Keycloak)
    if isinstance(user_scope, str):
        user_scope = user_scope.split(" ")
       
    user_roles = user_context.get("roles", [])
   
    # 1. SCOPE CHECK: Must have "mutual funds" or be ROLE_ADMIN
    if "mutual funds" not in user_scope and "ROLE_ADMIN" not in user_roles:
         logger.warning(f"User {user_context.get('user_id')} missing required scope 'mutual funds'")
         return []


    # 2. ROLE CHECK: Must be "ROLE_DISTRIBUTOR" or "ROLE_ADMIN"
    allowed_roles = {"ROLE_DISTRIBUTOR", "ROLE_ADMIN"}
    user_role_set = set(user_roles)
    if not user_role_set.intersection(allowed_roles):
        logger.warning(f"User {user_context.get('user_id')} missing required role (ROLE_DISTRIBUTOR/ROLE_ADMIN)")
        return []


    for server_name, server_config in servers.items():
        if server_name not in user_scope and "ROLE_ADMIN" not in user_roles:
             
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


        user_context = config.get("configurable", {}).get("user", {})
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


        system_msg = SystemMessage(content=AGENT_SYSTEM_PROMPT)


        messages = state["messages"]
        has_system_msg = any(isinstance(msg, SystemMessage) for msg in messages)
       
        if has_system_msg:
            message_history = messages
        else:
            message_history = [system_msg] + messages
       
        # Invoke the model
        response = model_with_tools.invoke(message_history)


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
    messages = state["messages"]
    last_message = messages[-1]
    user_context = config.get("configurable", {}).get("user", {})


    if not hasattr(last_message, "tool_calls"):
        return {"messages": []}


    tool_calls = last_message.tool_calls
    results = []


    try:
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


            # Execute the tool
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
        "postgresql://postgres:postgres@localhost:5433/order_agent",
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
        name="order-agent",
    )


    logger.info("Order agent graph compiled successfully")
    return compiled_graph




# Lazy initialization for module-level graph
_graph = None




async def _get_or_create_graph():
    """Get or create the graph asynchronously, handling event loop context."""
    global _graph
    if _graph is not None:
        return _graph
   
    try:
        _graph = await create_agent_graph()
        logger.info("Order agent graph initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize order agent graph: {e}")
        # Fallback: create a minimal graph for testing
        g = StateGraph(AgentState, config_schema=Context)
        g.add_node("call_model", call_model)
        g.add_edge(START, "call_model")
        _graph = g.compile(checkpointer=MemorySaver())
   
    return _graph




# Property-like accessor for lazy initialization
class _GraphProxy:
    """Lazy-loading proxy for the graph with async support."""
   
    async def ainvoke(self, *args, **kwargs):
        global _graph
        if _graph is None:
            _graph = await _get_or_create_graph()
        return await _graph.ainvoke(*args, **kwargs)
   
    def invoke(self, *args, **kwargs):
        """Synchronous invoke - delegates to ainvoke in async context."""
        global _graph
        if _graph is None:
            # Try to initialize synchronously (no running loop)
            try:
                asyncio.get_running_loop()
                raise RuntimeError(
                    "Cannot call invoke() from async context. Use ainvoke() instead."
                )
            except RuntimeError:
                _graph = asyncio.run(_get_or_create_graph())
        return _graph.invoke(*args, **kwargs)
   
    def __getattr__(self, name):
        global _graph
        if _graph is None:
            # For attribute access, try to initialize
            try:
                asyncio.get_running_loop()
                logger.warning(
                    f"Graph not yet initialized, accessing {name} in async context. "
                    "Use ainvoke() for async operations."
                )
            except RuntimeError:
                _graph = asyncio.run(_get_or_create_graph())
        return getattr(_graph, name) if _graph else None
   
    def __call__(self, *args, **kwargs):
        global _graph
        if _graph is None:
            try:
                asyncio.get_running_loop()
                raise RuntimeError(
                    "Cannot call graph from async context. Use ainvoke() instead."
                )
            except RuntimeError:
                _graph = asyncio.run(_get_or_create_graph())
        return _graph(*args, **kwargs)




graph = _GraphProxy()



