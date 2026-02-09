"""Production-ready LangGraph router agent for multi-agent coordination.

This router agent classifies user queries and routes them to specialized subagents
(Order Agent, NAV Agent, MCP Agent), featuring:
- Query classification with AWS Bedrock (Claude)
- Parallel invocation of specialized subagents
- Result synthesis and response generation
- User authorization based on roles and scope
- State persistence using PostgreSQL (PostgresStore)
- Comprehensive error handling and logging
"""

from __future__ import annotations

import logging
import operator
import os
import uuid
from functools import partial
from typing import Any

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.store.base import BaseStore
from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from typing_extensions import Annotated, TypedDict

logger = logging.getLogger(__name__)
logger.setLevel(os.getenv("AGENT_LOG_LEVEL", "INFO"))


class UserContext(TypedDict, total=False):
    """User context propagated from auth layer (Keycloak/JWT)."""

    user_id: str
    role: str
    roles: list[str]
    scope: list[str]
    username: str


class Context(TypedDict):
    """LangGraph runtime context."""

    thread_id: str
    user: UserContext


class RouterState(TypedDict):
    """Router agent state schema."""

    messages: Annotated[list[BaseMessage], operator.add]
    route_decision: Annotated[str, "Routing decision"]
    order_result: Annotated[str, "Order agent result"]
    nav_result: Annotated[str, "NAV agent result"]
    recon_result: Annotated[str, "Reconciliation agent result"]


ROUTER_SYSTEM_PROMPT = """You are a query router agent. Your job is to classify user queries and route them to the appropriate specialized agents.

ROUTING RULES:
1. "order": ONLY for ORDER FILE UPLOADS
   -this agent is responsible for uploading an order file,when the user gives the file and ask for upload an order like that
   - User is uploading order files (.txt, .csv, .json, etc.)
   - Keywords: "upload order", "order file", "submit order"

2. "nav": ONLY for NAV FILE UPLOADS
   - User is uploading NAV (Net Asset Value) files
   - Keywords: "upload nav", "nav file", "nav data", "nav ingestion"

   3. "recon": ONLY for RECONCILIATION FILE UPLOADS
   - this agent is called when user is uploading reconciliation files, or doing any adhoc reconciliation, or netting file upload, or settlement file upload, or any reconciliation related upload.
   - if the user ask any reconciliation related question, this agent should be called.
   - upload reconciliation files
   - ad-hoc reconciliation
   - netting file upload
   - settlement file upload
   - reconciliation upload
4. "general": ALL OTHER QUERIES (DEFAULT)
   -status or state related queries like status of an order, status of order with respect to fund house id, or any general question related to the system
   - Data retrieval
   - Analysis
   - Questions
   - Greetings

Respond with ONLY the routing decision in this exact format:
ROUTE: <decision>
REASON: <brief explanation>
"""

SYNTHESIZER_SYSTEM_PROMPT = """You are a response synthesizer. Your job is to combine results from multiple agents into a coherent, helpful response."""


def _check_agent_access(user_context: UserContext, agent_name: str) -> tuple[bool, str]:
    """RBAC enforcement for subagents."""

    user_role = user_context.get("role", "")
    user_roles = (
        [r for r in user_context.get("roles", [])] if user_context.get("roles") else []
    )
    all_roles = {user_role} | set(user_roles)
    all_roles.discard("")

    logger.info(
        f"[RBAC] Checking access: agent={agent_name}, "
        f"user_id={user_context.get('user_id')}, roles={all_roles}"
    )

    if agent_name == "order":
        if "ROLE_ADMIN" in all_roles or "ROLE_DISTRIBUTOR" in all_roles:
            return True, "Authorized"
        return False, "Access denied."

    if agent_name == "nav":
        if "ROLE_ADMIN" in all_roles or "ROLE_FUND" in all_roles:
            return True, "Authorized"
        return False, "Access denied."

    if agent_name == "recon":
        if {"ROLE_ADMIN", "ROLE_DISTRIBUTOR", "ROLE_FUND"} & all_roles:
            return True, "Authorized"
        return False, "Access denied."

    if agent_name == "mcp":
        if all_roles & {"ROLE_ADMIN", "ROLE_DISTRIBUTOR", "ROLE_FUND"}:
            return True, "Authorized"
        return False, "Access denied."

    logger.warning(f"[RBAC] Unknown agent: {agent_name}")
    return False, "Unknown agent."


def save_short_term_memory(
    store: BaseStore,
    config: RunnableConfig,
    thread_id: str,
    content: str,
) -> None:
    """Save short-term memory using redis store."""
    if not thread_id or not content:
        return

    try:
        user_context = config.get("configurable", {}).get("user", {})
        if not user_context or not user_context.get("user_id"):
            return

        user_id = user_context["user_id"]

        # Use a simple string key format for Redis
        key = f"memory:{user_id}:{thread_id}"
        store.put(
            ("memory",),
            key,
            {
                "content": content,
                "timestamp": str(uuid.uuid4()),
                "user_id": user_id,
                "thread_id": thread_id,
            },
        )

        logger.debug(f"[STM] Stored memory for {user_id}")

    except Exception as e:
        logger.error(f"[STM] Failed to save memory: {e}")


def retrieve_short_term_memory(
    store: BaseStore,
    config: RunnableConfig,
    thread_id: str,
    limit: int = 5,
) -> list[str]:
    """Retrieve recent short-term memory using redis store."""
    if not thread_id:
        return []

    try:
        user_context = config.get("configurable", {}).get("user", {})
        if not user_context or not user_context.get("user_id"):
            return []

        user_id = user_context["user_id"]

        # Construct the key used during save
        key = f"memory:{user_id}:{thread_id}"

        # Get the value directly from Redis
        item = store.get(("memory",), key)

        if item and item.value and isinstance(item.value, dict):
            content = item.value.get("content")
            if content:
                logger.info(f"Retrieved memory: {content}")
                if isinstance(content, dict):
                    content = str(content)
                    logger.info(
                        f"Memory content is a dict, converted to string: {content}"
                    )
                return [content]

        logger.info("No memory found")
        return []

    except Exception as e:
        logger.error(f"[STM] Failed to retrieve memory: {e}")
        return []


def _save_agent_interaction(
    store: BaseStore,
    config: RunnableConfig,
    agent_name: str,
    result: dict,
) -> None:
    """Persist agent interaction result."""

    try:
        user_context = config.get("configurable", {}).get("user", {})
        if not user_context or not user_context.get("user_id"):
            return

        user_id = user_context["user_id"]
        namespace = ("user", user_id, "interactions")

        store.put(
            namespace,
            str(uuid.uuid4()),
            {
                "agent": agent_name,
                "result": result,
            },
        )

        logger.debug(f"[MEMORY] Stored {agent_name} interaction for {user_id}")

    except Exception as e:
        logger.error(f"[MEMORY] Failed to store interaction: {e}")


async def _load_subagent(agent_name: str) -> Any:
    """Dynamically load a subagent graph."""

    try:
        if agent_name == "order":
            from src.order_agent.graph import graph as order_graph

            return order_graph

        elif agent_name == "nav":
            import src.nav_agent.graph as nav_module

            return nav_module.get_graph()

        elif agent_name == "recon":
            from src.recon_agent.graph import graph as recon_graph

            return recon_graph

        elif agent_name == "mcp":
            import src.agent.graph as mcp_module

            return await mcp_module.get_graph()

        raise ValueError(f"Unknown agent: {agent_name}")

    except Exception as e:
        logger.error(f"Failed to load subagent {agent_name}: {e}")
        raise


async def classify_query(
    state: RouterState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Classify the user query and determine routing."""

    try:
        from langchain_aws.chat_models import ChatBedrock

        logger.info("[ROUTER] classify_query() called")
        logger.info(f"[ROUTER] Config keys: {list(config.keys())}")

        configurable = config.get("configurable", {})
        user_context = configurable.get("user", {})

        logger.info(f"[ROUTER] User context received: {user_context}")

        messages = state.get("messages", [])
        logger.info(f"[ROUTER] Total messages in state: {len(messages)}")

        user_message = None
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                user_message = msg
                logger.info(f"[ROUTER] Latest user message: {msg.content[:200]}")
                break

        if not user_message:
            logger.warning("[ROUTER] No HumanMessage found. Defaulting to general.")
            return {"route_decision": "general"}

        model = ChatBedrock(
            model_id=os.getenv(
                "BEDROCK_MODEL_ID",
                "anthropic.claude-3-5-sonnet-20241022-v2:0",
            ),
            region_name=os.getenv("AWS_REGION", "us-east-1"),
            temperature=0,
            max_tokens=256,
        )

        system_msg = SystemMessage(content=ROUTER_SYSTEM_PROMPT)
        response = model.invoke([system_msg, user_message])

        response_text = response.content
        logger.info(f"[ROUTER] Raw classifier response: {response_text}")

        route_decision = "general"
        if "ROUTE:" in response_text:
            try:
                route_line = [
                    line for line in response_text.split("\n") if "ROUTE:" in line
                ][0]
                route_decision = route_line.split("ROUTE:")[1].strip().lower()
            except Exception as parse_error:
                logger.warning(f"[ROUTER] Failed parsing route: {parse_error}")

        logger.info(
            f"[ROUTER] Final route decision='{route_decision}' "
            f"user={user_context.get('user_id')}"
        )

        return {"route_decision": route_decision}

    except Exception as e:
        logger.exception("[ROUTER] classify_query failed")
        return {"route_decision": "general"}


async def invoke_order_agent(
    state: RouterState,
    config: RunnableConfig,
    *,
    store: BaseStore,
    redis_store: BaseStore,
) -> dict[str, Any]:
    """Invoke Order Agent with RBAC + memory."""

    try:
        logger.info("[ROUTER→ORDER] Invoking order agent")

        user_context = config.get("configurable", {}).get("user", {})
        logger.info(f"[ROUTER→ORDER] User context: {user_context}")

        authorized, msg = _check_agent_access(user_context, "order")
        if not authorized:
            logger.warning("[ROUTER→ORDER] Access denied")
            return {
                "order_result": msg,
                "messages": [AIMessage(content=msg)],
            }

        order_graph = await _load_subagent("order")

        messages = [m for m in state.get("messages", []) if isinstance(m, HumanMessage)]
        order_state = {"messages": messages[-1]}

        order_config = {
            "configurable": {
                "thread_id": config.get("configurable", {}).get("thread_id", "default"),
                "user": user_context,
            }
        }

        memories = retrieve_short_term_memory(
            redis_store,
            order_config,
            thread_id=config["configurable"]["thread_id"],
        )

        # Prepend memory context to messages if available
        if memories:
            memory_context = "Recent conversation context:\n" + "\n".join(memories)
            order_state["messages"] = [
                SystemMessage(content=memory_context),
                order_state["messages"],
            ]

        result = await order_graph.ainvoke(order_state, config=order_config)

        final_message = {}
        if "messages" in result:
            for msg_obj in reversed(result["messages"]):
                if isinstance(msg_obj, AIMessage):
                    # Handle both string content and structured content (list of dicts)
                    if isinstance(msg_obj.content, str):
                        final_message["AIMessage"] = msg_obj.content
                    elif isinstance(msg_obj.content, list) and len(msg_obj.content) > 0:
                        if (
                            isinstance(msg_obj.content[0], dict)
                            and "type" in msg_obj.content[0]
                        ):
                            if msg_obj.content[0]["type"] == "text":
                                final_message["AIMessage"] = msg_obj.content[0].get(
                                    "text", ""
                                )
                    if final_message.get("AIMessage"):
                        break
                if isinstance(msg_obj, HumanMessage):
                    final_message["HumanMessage"] = msg_obj.content
                    break

        logger.info(
            f"[ROUTER→ORDER] Completed. Output: "
            f"{final_message if final_message else 'EMPTY'}"
        )

        save_short_term_memory(
            redis_store,
            config,
            thread_id=config["configurable"]["thread_id"],
            content=final_message,
        )

        _save_agent_interaction(store, config, "order", final_message)

        return {
            "order_result": final_message or "Order agent completed",
            "messages": result.get("messages", []),
        }

    except Exception as e:
        logger.exception("[ROUTER→ORDER] Error")
        return {
            "order_result": str(e),
            "messages": [AIMessage(content=f"Order agent error: {str(e)}")],
        }


async def invoke_nav_agent(
    state: RouterState,
    config: RunnableConfig,
    *,
    store: BaseStore,
    redis_store: BaseStore,
) -> dict[str, Any]:
    """Invoke NAV Agent with RBAC + memory."""

    try:
        logger.info("[ROUTER→NAV] Invoking NAV agent")

        user_context = config.get("configurable", {}).get("user", {})
        logger.info(f"[ROUTER→NAV] User context: {user_context}")

        authorized, msg = _check_agent_access(user_context, "nav")
        if not authorized:
            logger.warning("[ROUTER→NAV] Access denied")
            return {
                "nav_result": msg,
                "messages": [AIMessage(content=msg)],
            }

        nav_graph = await _load_subagent("nav")

        messages = [m for m in state.get("messages", []) if isinstance(m, HumanMessage)]
        nav_state = {"messages": messages[-1]}

        nav_config = {
            "configurable": {
                "thread_id": config.get("configurable", {}).get("thread_id", "default"),
                "user": user_context,
            }
        }

        memories = retrieve_short_term_memory(
            redis_store,
            nav_config,
            thread_id=config["configurable"]["thread_id"],
        )

        # Prepend memory context to messages if available
        if memories:
            memory_context = "Recent conversation context:\n" + "\n".join(memories)
            nav_state["messages"] = [
                SystemMessage(content=memory_context),
                nav_state["messages"],
            ]

        result = await nav_graph.ainvoke(nav_state, config=nav_config)

        final_message = {}
        if "messages" in result:
            for msg_obj in reversed(result["messages"]):
                if isinstance(msg_obj, AIMessage):
                    # Handle both string content and structured content (list of dicts)
                    if isinstance(msg_obj.content, str):
                        final_message["AIMessage"] = msg_obj.content
                    elif isinstance(msg_obj.content, list) and len(msg_obj.content) > 0:
                        if (
                            isinstance(msg_obj.content[0], dict)
                            and "type" in msg_obj.content[0]
                        ):
                            if msg_obj.content[0]["type"] == "text":
                                final_message["AIMessage"] = msg_obj.content[0].get(
                                    "text", ""
                                )
                    if final_message.get("AIMessage"):
                        break
                if isinstance(msg_obj, HumanMessage):
                    final_message["HumanMessage"] = msg_obj.content
                    break

        logger.info(
            f"[ROUTER→NAV] Completed. Output: "
            f"{final_message if final_message else 'EMPTY'}"
        )

        save_short_term_memory(
            redis_store,
            config,
            thread_id=config["configurable"]["thread_id"],
            content=final_message,
        )

        _save_agent_interaction(store, config, "nav", final_message)

        return {
            "nav_result": final_message or "NAV agent completed",
            "messages": result.get("messages", []),
        }

    except Exception as e:
        logger.exception("[ROUTER→NAV] Error")
        return {
            "nav_result": str(e),
            "messages": [AIMessage(content=f"NAV agent error: {str(e)}")],
        }


async def invoke_recon_agent(
    state: RouterState,
    config: RunnableConfig,
    *,
    store: BaseStore,
    redis_store: BaseStore,
) -> dict[str, Any]:
    try:
        logger.info("[ROUTER→RECON] Invoking reconciliation agent")

        user_context = config.get("configurable", {}).get("user", {})
        authorized, msg = _check_agent_access(user_context, "recon")

        if not authorized:
            return {
                "recon_result": msg,
                "messages": [AIMessage(content=msg)],
            }

        recon_graph = await _load_subagent("recon")

        messages = [m for m in state.get("messages", []) if isinstance(m, HumanMessage)]

        recon_state = {"messages": messages[-1]}

        recon_config = {
            "configurable": {
                "thread_id": config.get("configurable", {}).get("thread_id", "default"),
                "user": user_context,
            }
        }

        memories = retrieve_short_term_memory(
            redis_store,
            recon_config,
            thread_id=config["configurable"]["thread_id"],
        )

        # Prepend memory context to messages if available
        if memories:
            memory_context = "Recent conversation context:\n" + "\n".join(memories)
            recon_state["messages"] = [
                SystemMessage(content=memory_context),
                recon_state["messages"],
            ]

        result = await recon_graph.ainvoke(recon_state, config=recon_config)

        final_message = {}
        if "messages" in result:
            for msg_obj in reversed(result["messages"]):
                if isinstance(msg_obj, AIMessage):
                    # Handle both string content and structured content (list of dicts)
                    if isinstance(msg_obj.content, str):
                        final_message["AIMessage"] = msg_obj.content
                    elif isinstance(msg_obj.content, list) and len(msg_obj.content) > 0:
                        if (
                            isinstance(msg_obj.content[0], dict)
                            and "type" in msg_obj.content[0]
                        ):
                            if msg_obj.content[0]["type"] == "text":
                                final_message["AIMessage"] = msg_obj.content[0].get(
                                    "text", ""
                                )
                    if final_message.get("AIMessage"):
                        break
                if isinstance(msg_obj, HumanMessage):
                    final_message["HumanMessage"] = msg_obj.content
                    break

        logger.info(
            f"[ROUTER→ORDER] Completed. Output: "
            f"{final_message if final_message else 'EMPTY'}"
        )

        save_short_term_memory(
            redis_store,
            config,
            thread_id=config["configurable"]["thread_id"],
            content=final_message,
        )

        _save_agent_interaction(store, config, "recon", final_message)

        return {
            "recon_result": final_message or "Reconciliation agent completed",
            "messages": result.get("messages", []),
        }

    except Exception as e:
        logger.exception("[ROUTER→RECON] Error")
        return {
            "recon_result": str(e),
            "messages": [AIMessage(content=f"Reconciliation agent error: {str(e)}")],
        }


async def invoke_mcp_agent(
    state: RouterState,
    config: RunnableConfig,
    *,
    store: BaseStore,
    redis_store: BaseStore,
) -> dict[str, Any]:
    """Invoke MCP agent for general queries."""

    try:
        logger.info("[ROUTER→MCP] Invoking MCP agent")

        user_context = config.get("configurable", {}).get("user", {})
        logger.info(f"[ROUTER→MCP] User context: {user_context}")

        authorized, msg = _check_agent_access(user_context, "mcp")
        if not authorized:
            logger.warning("[ROUTER→MCP] Access denied")
            return {
                "messages": [AIMessage(content=msg)],
            }

        mcp_graph = await _load_subagent("mcp")

        messages = [m for m in state.get("messages", []) if isinstance(m, HumanMessage)]
        mcp_state = {"messages": messages[-1]}

        mcp_config = {
            "configurable": {
                "thread_id": config.get("configurable", {}).get("thread_id", "default"),
                "user": user_context,
            }
        }

        logger.info("memory retrieval called")
        memories = retrieve_short_term_memory(
            redis_store,
            mcp_config,
            thread_id=config["configurable"]["thread_id"],
        )

        # Prepend memory context to messages if available
        if memories:
            memory_context = "Recent conversation context:\n" + "\n".join(memories)
            mcp_state["messages"] = [
                SystemMessage(content=memory_context),
                mcp_state["messages"],
            ]

        result = await mcp_graph.ainvoke(mcp_state, config=mcp_config)

        final_message = {}
        if "messages" in result:
            for msg_obj in reversed(result["messages"]):
                if isinstance(msg_obj, AIMessage):
                    # Handle both string content and structured content (list of dicts)
                    if isinstance(msg_obj.content, str):
                        final_message["AIMessage"] = msg_obj.content
                    elif isinstance(msg_obj.content, list) and len(msg_obj.content) > 0:
                        if (
                            isinstance(msg_obj.content[0], dict)
                            and "type" in msg_obj.content[0]
                        ):
                            if msg_obj.content[0]["type"] == "text":
                                final_message["AIMessage"] = msg_obj.content[0].get(
                                    "text", ""
                                )
                    if final_message.get("AIMessage"):
                        break
                if isinstance(msg_obj, HumanMessage):
                    final_message["HumanMessage"] = msg_obj.content
                    break

        logger.info(
            f"[ROUTER→ORDER] Completed. Output: "
            f"{final_message if final_message else 'EMPTY'}"
        )

        save_short_term_memory(
            redis_store,
            config,
            thread_id=config["configurable"]["thread_id"],
            content=final_message,
        )

        _save_agent_interaction(store, config, "general", final_message)

        return {"mcp_result": final_message or "MCP agent completed"}

    except Exception as e:
        logger.exception("[ROUTER→MCP] Error")
        return {
            "messages": [AIMessage(content=f"MCP agent error: {str(e)}")],
        }


async def synthesize_results(
    state: RouterState,
    config: RunnableConfig,
    *,
    store: BaseStore,
) -> dict[str, Any]:
    """Synthesize results from Order/NAV agents into a final response."""

    try:
        from langchain_aws.chat_models import ChatBedrock

        logger.info("[ROUTER→SYNTHESIZE] Synthesizing results")
        user_context = config.get("configurable", {}).get("user", {})
        logger.info(f"[ROUTER→SYNTHESIZE] User: {user_context.get('user_id')}")

        results = []
        if state.get("order_result"):
            results.append(f"Order Agent: {state['order_result']}")
        if state.get("nav_result"):
            results.append(f"NAV Agent: {state['nav_result']}")

        if not results:
            logger.info("[ROUTER→SYNTHESIZE] No agent results to synthesize")
            return {}

        user_message = None
        for msg in state.get("messages", []):
            if isinstance(msg, HumanMessage):
                user_message = msg
                break

        if not user_message:
            combined = "\n\n".join(results)
            _save_agent_interaction(store, config, "synthesis", combined)
            return {"messages": [AIMessage(content=combined)]}

        model = ChatBedrock(
            model_id=os.getenv(
                "BEDROCK_MODEL_ID",
                "anthropic.claude-3-5-sonnet-20241022-v2:0",
            ),
            region_name=os.getenv("AWS_REGION", "us-east-1"),
            temperature=0,
            max_tokens=2048,
        )

        synthesis_prompt = f"""
Original user query:
{user_message.content}

Agent Results:
{chr(10).join(results)}

Please synthesize these results into a clear, helpful response.
"""

        system_msg = SystemMessage(content=SYNTHESIZER_SYSTEM_PROMPT)
        response = model.invoke([system_msg, HumanMessage(content=synthesis_prompt)])

        _save_agent_interaction(store, config, "synthesis", response.content)

        logger.info("[ROUTER→SYNTHESIZE] Synthesis completed")

        return {"messages": [AIMessage(content=response.content)]}

    except Exception as e:
        logger.exception("[ROUTER→SYNTHESIZE] Error")
        return {
            "messages": [AIMessage(content=f"Error synthesizing results: {str(e)}")]
        }


def _should_continue(state: RouterState) -> str:
    """Determine next node based on routing decision."""

    route_decision = state.get("route_decision", "general").lower().strip()

    logger.debug(f"[ROUTER] Routing decision: {route_decision}")

    if route_decision == "order":
        return "order_agent"
    elif route_decision == "nav":
        return "nav_agent"
    elif route_decision == "recon":
        return "recon_agent"
    else:
        return "mcp_agent"


def create_router_graph(
    store: BaseStore,
    redis_store: BaseStore,
) -> StateGraph:
    logger.info("[ROUTER] Initializing Router Graph")

    graph = StateGraph(RouterState, config_schema=Context)

    graph.add_node("classify_query", classify_query)

    graph.add_node(
        "order_agent",
        partial(invoke_order_agent, store=store, redis_store=redis_store),
    )
    graph.add_node(
        "nav_agent", partial(invoke_nav_agent, store=store, redis_store=redis_store)
    )
    graph.add_node(
        "recon_agent",
        partial(invoke_recon_agent, store=store, redis_store=redis_store),
    )
    graph.add_node(
        "mcp_agent", partial(invoke_mcp_agent, store=store, redis_store=redis_store)
    )
    graph.add_node("synthesize", partial(synthesize_results))
    graph.add_edge(START, "classify_query")

    graph.add_conditional_edges(
        "classify_query",
        _should_continue,
        {
            "order_agent": "order_agent",
            "nav_agent": "nav_agent",
            "recon_agent": "recon_agent",
            "mcp_agent": "mcp_agent",
        },
    )

    graph.add_edge("order_agent", END)
    graph.add_edge("nav_agent", END)
    graph.add_edge("recon_agent", END)
    graph.add_edge("mcp_agent", END)

    compiled = graph.compile(
        name="router-agent",
        store=store,
    )

    logger.info("[ROUTER] Router graph compiled successfully")
    return compiled
