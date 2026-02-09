"""LangGraph reconciliation agent for ad-hoc file uploads.

Features:
- Tool-calling agent using AWS Bedrock (Claude)
- Multipart file upload for reconciliation
- Human-in-the-loop approval for write operations
- Authorization via user scope/role
- Robust error handling and logging
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

import httpx
from langchain.tools import tool
from langchain_aws.chat_models import ChatBedrock
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph, add_messages
from langgraph.types import Command, interrupt
from typing_extensions import Annotated, TypedDict
from src.recon_agent.tool_authz import TOOL_ROLE_MAP
from langchain_mcp_adapters.client import MultiServerMCPClient
logger = logging.getLogger(__name__)
logger.setLevel(os.getenv("AGENT_LOG_LEVEL", "INFO"))

class UserContext(TypedDict, total=False):
    user_id: str
    role: str
    roles: list[str]
    scope: list[str]

class Context(TypedDict):
    thread_id: str
    user: UserContext

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

AGENT_SYSTEM_PROMPT = """
You are a reconciliation agent responsible for ad-hoc reconciliation file uploads.

Rules:
- Be explicit about reconciliation actions
- Validate and confirm file details before upload
- All uploads are WRITE operations and require approval
- Never assume missing inputs
- Clearly summarize reconciliation submission status
"""

def _get_api_base_url() -> str:
    return os.getenv(
        "RECONCILIATION_API_BASE_URL",
        "http://localhost:8087",
    )

def _parse_mcp_servers() -> dict[str, dict[str, str]]:
    """Parse MCP servers configuration from environment.

    Returns:
        Dictionary mapping server names to their configuration
    """
    mcp_config_str = os.getenv("RECON_MCP_SERVERS", "{}")
    logger.debug(f"Line 74 Raw MCP config string: {mcp_config_str}")

    try:
        config = json.loads(mcp_config_str)
        servers = {}
        for server in config.get("servers", []):
            servers[server["name"]] = {
                "transport": server.get("type", "http"), # Default to http if not specified (or use type as fallback)
                "url": server["url"],
            }
        return servers
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Failed to parse GENERAL_MCP_SERVERS: {e}")
        return {}

async def _get_mcp_tools(user_context: UserContext) -> list[Any]:
    """Initialize and retrieve tools from configured MCP servers.

    Only returns tools that user has access to based on scope.

    Args:
        user_context: User authorization context with scope

    Returns:
        List of authorized LangChain Tool objects from MCP servers
    """

    servers = _parse_mcp_servers()
    if not servers:
        logger.warning("No MCP servers configured in GENERAL_MCP_SERVERS environment variable")
        return []

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
            tools.append(upload_reconciliation_files)
            logger.info(
                f"Line 123 Loaded {len(tools)} tools from {server_name} ")
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


    authorized_tools = [
        tool for tool in all_tools
        if _is_tool_authorized(tool.name, user_context)
    ]


    logger.info(
        f"Authorized tools for user {user_context.get('user_id')}: "
        f"{len(authorized_tools)}/{len(all_tools)}"
    )

    return authorized_tools

def _is_tool_authorized(tool_name: str, user_context: dict) -> bool:


    user_roles = {
        r for r in user_context.get("roles", []) if isinstance(r, str)
    }

    if not user_roles:
        return False

    allowed_roles = TOOL_ROLE_MAP.get(tool_name)
    if not allowed_roles:
        return False

    return bool(user_roles & allowed_roles)


@tool
def upload_reconciliation_files(
    trade_date: str,
    currency: str,
    netting_file_path: str,
    settlement_file_path: str | None = None,
    description: str | None = None,
) -> str:
    """Upload netting/settlement files to trigger ad-hoc reconciliation.

    Args:
        trade_date: Trade date (YYYY-MM-DD)
        currency: Currency code (e.g. CAD, USD)
        netting_file_path: Local path to netting .txt file
        settlement_file_path: Optional local path to settlement .txt file
        description: Optional description
    """
    try:
        if not os.path.exists(netting_file_path):
            return f"Error: Netting file not found at {netting_file_path}"

        files = {}

        with open(netting_file_path, "rb") as nf:
            files["nettingFile"] = (
                os.path.basename(netting_file_path),
                nf.read(),
                "text/plain",
            )

        if settlement_file_path:
            if not os.path.exists(settlement_file_path):
                return f"Error: Settlement file not found at {settlement_file_path}"
            with open(settlement_file_path, "rb") as sf:
                files["settlementFile"] = (
                    os.path.basename(settlement_file_path),
                    sf.read(),
                    "text/plain",
                )

        params = {
            "tradeDate": trade_date,
            "currency": currency,
        }

        if description:
            params["description"] = description

        logger.info(f"Attempting upload to API base URL: {_get_api_base_url()}" )
        response = httpx.post(
            f"{_get_api_base_url()}/api/v1/reconciliation/adhoc/upload",
            params=params,
            files=files,
            timeout=60.0,
        )
        logger.info(f"Upload response status: {response.status_code}" )

        if response.status_code in (200, 202):
            logger.info(
                f"Reconciliation upload accepted "
                f"(tradeDate={trade_date}, currency={currency})"
            )
            return response.text

        logger.error(
            f"Upload failed ({response.status_code}): {response.text}"
        )
        return f"Error: Upload failed ({response.status_code}) - {response.text}"

    except Exception as e:
        logger.exception("Reconciliation upload failed")
        return f"Error uploading reconciliation files: {str(e)}"

async def _get_tools(user_context: UserContext) -> list[Any]:
    """Initialize and retrieve tools for order agent.

    Includes custom tools and those from configured MCP servers.
    Only returns tools that user has access to based on scope.

    Args:
        user_context: User authorization context with scope

    Returns:
        List of authorized LangChain Tool objects
    """
    tools_list = [upload_reconciliation_files]

    mcp_config_str = os.getenv("RECON_MCP_SERVERS", "{}")
    try:
        config = json.loads(mcp_config_str)
        servers = {}
        for server in config.get("servers", []):
            servers[server["name"]] = {
                "transport": server.get("transport", "http"),
                "url": server["url"],
            }
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Failed to parse RECON_MCP_SERVERS: {e}")
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
    for server_name, server_config in servers.items():
        try:
            mcp_config = {
                server_name: {
                    "transport": server_config["transport"],
                    "url": server_config["url"],
                }
            }
            
            client = MultiServerMCPClient(mcp_config)
            mcp_tools = await client.get_tools()
            logger.info(
                    f"Loaded {len(mcp_tools)} tools from {server_name} "
                    f"(authorized for user {user_context.get('user_id')})"
                )
            tools_list.extend(mcp_tools)
        except Exception as e:
            logger.error(f"Failed to load tools from {server_name}: {e}")
            continue

    # 2. ROLE CHECK: Must be "ROLE_DISTRIBUTOR" or "ROLE_ADMIN"
    allowed_roles = {"ROLE_DISTRIBUTOR", "ROLE_ADMIN"}
    user_role_set = set(user_roles)
    if not user_role_set.intersection(allowed_roles):
        logger.warning(f"User {user_context.get('user_id')} missing required role (ROLE_DISTRIBUTOR/ROLE_ADMIN)")
        return []

   
    return tools_list

def _is_write_operation(tool_name: str) -> bool:
    write_keywords = ["create", "update", "delete", "add", "remove"]
    return any(k in tool_name.lower() for k in write_keywords)

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
        tools = await _get_mcp_tools(user_context)

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
        model = model.bind_tools(tools)

        messages = state["messages"]
        if not any(isinstance(m, SystemMessage) for m in messages):
            messages = [SystemMessage(content=AGENT_SYSTEM_PROMPT)] + messages

        response = model.invoke(messages)
        return {"messages": [response]}

    except Exception as e:
        logger.exception("LLM failure")
        return {
            "messages": [
                AIMessage(content=f"Agent error: {str(e)}")
            ]
        }
def _should_continue(state: AgentState) -> str:
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "handle_tool_calls"
    return END

async def handle_tool_calls(
    state: AgentState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Process tool calls with authorization + human approval for write operations.
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
                f"Processing tool call: {tool_name} "
                f"user={user_context.get('user_id')} "
                f"roles={user_context.get('roles')}"
            )

            tool = tools_by_name.get(tool_name)

           
            if not tool or not _is_tool_authorized(tool_name, user_context):
                logger.warning(
                    f"[AUTHZ] DENIED tool={tool_name} "
                    f"user={user_context.get('user_id')} "
                    f"roles={user_context.get('roles')}"
                )
                results.append(
                    ToolMessage(
                        content="You are not authorized to perform this operation.",
                        tool_call_id=tool_call["id"],
                    )
                )
                continue

           
            if _is_write_operation(tool_name):
                approval_response = interrupt(
                    {
                        "action": tool_name,
                        "args": tool_args,
                        "description": (
                            "Write Operation Approval Required\n\n"
                            f"Tool: {tool_name}\n"
                            f"Arguments: {tool_args}\n\n"
                            "Please review and approve this operation before proceeding."
                        ),
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
                            f"user={user_context.get('user_id')}"
                        )
                    else:
                        logger.info(
                            f"Write operation rejected: {tool_name} "
                            f"user={user_context.get('user_id')}"
                        )
                        results.append(
                            ToolMessage(
                                content=f"Operation '{tool_name}' was rejected by the user.",
                                tool_call_id=tool_call["id"],
                            )
                        )
                        continue

           
            try:
                observation = await tool.ainvoke(tool_args)
                logger.info(f"Tool execution successful: {tool_name}")
            except Exception as e:
                observation = f"Error executing tool: {str(e)}"
                logger.error(
                    f"Tool execution failed: {tool_name} - {str(e)}"
                )

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

async def create_agent_graph() -> StateGraph:
    graph = StateGraph(AgentState, config_schema=Context)

    graph.add_node("call_model", call_model)
    graph.add_node("handle_tool_calls", handle_tool_calls)

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

    compiled = graph.compile(name="reconciliation-upload-agent")
    logger.info("Reconciliation upload agent compiled")
    return compiled

_graph = None

class _GraphProxy:
    async def ainvoke(self, *args, **kwargs):
        global _graph
        if _graph is None:
            _graph = await create_agent_graph()
        return await _graph.ainvoke(*args, **kwargs)

    def invoke(self, *args, **kwargs):
        global _graph
        if _graph is None:
            _graph = asyncio.run(create_agent_graph())
        return _graph.invoke(*args, **kwargs)

graph = _GraphProxy()
