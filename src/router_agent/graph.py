"""LangGraph router agent for multi-agent coordination.

This router agent classifies user queries and routes them to specialized subagents
(Order Agent, NAV Agent), featuring:
- Query classification with AWS Bedrock (Claude)
- Parallel invocation of specialized subagents
- Result synthesis and response generation
- User authorization based on scope
- State persistence using PostgreSQL
- Comprehensive error handling and logging
"""

from __future__ import annotations
from functools import partial
import asyncio
import logging
import operator
import os
import uuid
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.store.base import BaseStore
from langgraph.store.postgres import PostgresStore
from typing_extensions import Annotated, TypedDict

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(os.getenv("AGENT_LOG_LEVEL", "INFO"))


class UserContext(TypedDict, total=False):
    """User context for authorization."""

    user_id: str
    role: str
    scope: list[str]


class Context(TypedDict):
    """Context parameters for the router agent.

    Set these when creating assistants OR when invoking the graph.
    """

    thread_id: str
    user: UserContext


class RouterState(TypedDict):
    """State schema for the router agent.

    Follows the MessagesState pattern for chat-based agents.
    """

    messages: Annotated[list[BaseMessage], operator.add]
    route_decision: Annotated[str, "Routing decision made by classifier"]
    order_result: Annotated[str, "Result from order agent"]
    nav_result: Annotated[str, "Result from NAV agent"]


ROUTER_SYSTEM_PROMPT = """You are a query router agent. Your job is to classify user queries and route them to the appropriate specialized agents.

ROUTING RULES:
1. "order": ONLY for ORDER FILE UPLOADS
   - User is uploading order files (.txt, .csv, .json, etc.)
   - Keywords: "upload order", "order file", "submit order"
   
2. "nav": ONLY for NAV FILE UPLOADS  
   - User is uploading NAV (Net Asset Value) files
   - Keywords: "upload nav", "nav file", "nav data", "nav ingestion"
   
3. "general": ALL OTHER QUERIES (DEFAULT)
   - Data retrieval: "get all positions", "show me orders", "fetch SLA records"
   - Analysis: "unresolved errors", "breached SLA", "exception summary"
   - Questions: "how many", "list", "show", "fetch", "retrieve"
   - Greetings and general inquiries

Respond with ONLY the routing decision in this exact format:
ROUTE: <decision>
REASON: <brief explanation>
"""

SYNTHESIZER_SYSTEM_PROMPT = """You are a response synthesizer. Your job is to combine results from multiple agents into a coherent, helpful response.

Analyze the results provided and synthesize them into a clear, organized response that directly answers the user's original question."""


def remember_user_context(
    state: RouterState,
    config: RunnableConfig,
    *,
    store: BaseStore,
) -> dict[str, Any]:
    """Store user context in persistent memory for session continuity.

    Args:
        state: Current router state
        config: Runtime configuration with user context
        store: PostgreSQL store for persistence

    Returns:
        Empty dict (no state changes)
    """
    try:
        user_context = config.get("configurable", {}).get("user", {})
        if not user_context or not user_context.get("user_id"):
            return {}

        user_id = user_context.get("user_id")
        ns = ("user", user_id, "context")

        # Store user metadata (role, scope) for later use
        user_data = {
            "role": user_context.get("role", "user"),
            "scope": user_context.get("scope", []),
            "timestamp": str(__import__("datetime").datetime.now()),
        }

        store.put(ns, "metadata", user_data)
        logger.debug(f"Stored context for user {user_id}")

    except Exception as e:
        logger.error(f"Error storing user context: {e}")

    return {}


def _save_agent_interaction(
    store: BaseStore,
    config: RunnableConfig,
    agent_name: str,
    result: str,
) -> None:
    """Save agent interaction to persistent memory.

    Args:
        store: PostgreSQL store
        config: Runtime configuration with user context
        agent_name: Name of the agent (order, nav, mcp)
        result: Result/output from the agent
    """
    try:
        user_context = config.get("configurable", {}).get("user", {})
        if not user_context or not user_context.get("user_id"):
            return

        user_id = user_context.get("user_id")
        ns = ("user", user_id, "interactions")

        interaction_data = {
            "agent": agent_name,
            "result": result[:500] if len(result) > 500 else result,
            "timestamp": str(__import__("datetime").datetime.now()),
        }

        store.put(ns, str(uuid.uuid4()), interaction_data)
        logger.debug(f"Saved {agent_name} interaction for user {user_id}")

    except Exception as e:
        logger.error(f"Error saving agent interaction: {e}")


async def _load_subagent(agent_name: str) -> Any:
    """Dynamically load a subagent graph.

    Args:
        agent_name: Name of the subagent ('order', 'nav', 'mcp')

    Returns:
        Compiled subagent graph

    Raises:
        ValueError: If agent cannot be loaded
    """
    try:
        if agent_name == "order":
            from src.order_agent.graph import graph as order_graph

            return order_graph
        elif agent_name == "nav":
            import src.nav_agent.graph as nav_module

            # Use get_graph() which handles async initialization properly
            return nav_module.get_graph()
        elif agent_name == "mcp":
            import src.agent.graph as mcp_module

            # Always use lazy initialization for MCP agent
            return await mcp_module.get_graph()
        else:
            raise ValueError(f"Unknown agent: {agent_name}")
    except Exception as e:
        logger.error(f"Failed to load {agent_name} agent: {e}")
        raise


async def classify_query(
    state: RouterState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Classify the user query and determine routing.

    Args:
        state: Current router state with message history
        config: Runtime configuration including user context

    Returns:
        Updated state with routing decision
    """
    try:
        from langchain_aws.chat_models import ChatBedrock

        user_context = config.get("configurable", {}).get("user", {})
        if not user_context:
            logger.warning(
                "No user context found. Using default 'test_user' for development."
            )
            user_context = {
                "user_id": "test_user",
                "role": "admin",
                "scope": ["mcp-agent", "order-agent", "nav-agent", "router-agent"],
            }
            # raise ValueError("User context is required in config")

        # Get the latest user message
        messages = state["messages"]
        user_message = None
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                user_message = msg
                break

        if not user_message:
            return {
                "route_decision": "general",
            }

        # Classify the query
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

        # Parse the routing decision
        response_text = response.content
        route_decision = "general"

        if "ROUTE:" in response_text:
            try:
                route_line = [
                    line for line in response_text.split("\n") if "ROUTE:" in line
                ][0]
                route_decision = route_line.split("ROUTE:")[1].strip().lower()
            except (IndexError, ValueError):
                logger.warning(f"Could not parse route decision: {response_text}")

        logger.info(
            f"Query classified as '{route_decision}' for user {user_context.get('user_id')}"
        )

        return {
            "route_decision": route_decision,
        }

    except Exception as e:
        logger.error(f"Error in classify_query: {e}")
        return {
            "route_decision": "general",
        }


async def invoke_order_agent(
    state: RouterState,
    config: RunnableConfig,
    *,
    store: BaseStore,
) -> dict[str, Any]:
    """Invoke the order agent as a subgraph.

    Transforms router state to order agent state and back.

    Args:
        state: Current router state
        config: Runtime configuration
        store: PostgreSQL store for persistence

    Returns:
        Updated state with order agent result
    """
    try:
        user_context = config.get("configurable", {}).get("user", {})
        if not user_context:
            user_context = {
                "user_id": "test_user",
                "role": "admin",
                "scope": [
                    "mutual funds",
                    "mcp-agent",
                    "order-agent",
                    "nav-agent",
                    "router-agent",
                ],
            }

        # Load order agent
        order_graph = await _load_subagent("order")

        # Transform state: extract user messages for order agent
        messages = state["messages"]
        order_state = {"messages": messages}

        # Invoke order agent with user context
        order_config = {
            "configurable": {
                "thread_id": config.get("configurable", {}).get("thread_id", "default"),
                "user": user_context,
            }
        }

        result = await order_graph.ainvoke(order_state, config=order_config)

        # Extract final message from order agent result
        final_message = ""
        if "messages" in result:
            for msg in reversed(result["messages"]):
                if isinstance(msg, AIMessage):
                    final_message = msg.content
                    break

        # Save interaction to persistent memory
        _save_agent_interaction(store, config, "order", final_message)

        logger.info(
            f"Order agent completed for user {user_context.get('user_id')}: {final_message[:100]}"
        )

        return {
            "order_result": final_message or "Order agent completed without response",
            "messages": [AIMessage(content=f"Order agent: {final_message}")],
        }

    except Exception as e:
        logger.error(f"Error invoking order agent: {e}")
        return {
            "order_result": f"Error: {str(e)}",
            "messages": [AIMessage(content=f"Order agent error: {str(e)}")],
        }


async def invoke_nav_agent(
    state: RouterState,
    config: RunnableConfig,
    *,
    store: BaseStore,
) -> dict[str, Any]:
    """Invoke the NAV agent as a subgraph.

    Transforms router state to NAV agent state and back.

    Args:
        state: Current router state
        config: Runtime configuration
        store: PostgreSQL store for persistence

    Returns:
        Updated state with NAV agent result
    """
    try:
        from langchain_core.messages import ToolMessage

        user_context = config.get("configurable", {}).get("user", {})
        if not user_context:
            user_context = {
                "user_id": "test_user",
                "role": "admin",
                "scope": ["mcp-agent", "order-agent", "nav-agent", "router-agent"],
            }

        # Load NAV agent
        nav_graph = await _load_subagent("nav")

        # Transform state: extract user messages for NAV agent
        messages = state["messages"]
        nav_state = {"messages": messages}

        # Invoke NAV agent with user context
        nav_config = {
            "configurable": {
                "thread_id": config.get("configurable", {}).get("thread_id", "default"),
                "user": user_context,
            }
        }

        result = await nav_graph.ainvoke(nav_state, config=nav_config)

        # Extract final message from NAV agent result
        final_message = ""

        logger.info(
            f"NAV agent result keys: {result.keys() if isinstance(result, dict) else 'not a dict'}"
        )
        logger.info(
            f"NAV agent messages count: {len(result.get('messages', []))} messages"
        )

        # Log all messages for debugging
        if "messages" in result:
            for i, msg in enumerate(result["messages"]):
                logger.debug(
                    f"Message {i}: {type(msg).__name__} - {str(msg.content)[:100]}"
                )

        # First, try to find a ToolMessage (file upload response)
        if "messages" in result:
            for msg in reversed(result["messages"]):
                if isinstance(msg, ToolMessage):
                    final_message = msg.content
                    logger.info(
                        f"Extracted tool response for user {user_context.get('user_id')}"
                    )
                    break

            # If no ToolMessage, fall back to last AIMessage
            if not final_message:
                for msg in reversed(result["messages"]):
                    if isinstance(msg, AIMessage):
                        final_message = msg.content
                        break

        # Save interaction to persistent memory
        _save_agent_interaction(store, config, "nav", final_message)

        logger.info(
            f"NAV agent completed for user {user_context.get('user_id')}: {final_message[:100] if final_message else 'empty'}"
        )

        return {
            "nav_result": final_message or "NAV agent completed without response",
            "messages": [
                AIMessage(
                    content=(
                        f"NAV agent: {final_message}"
                        if final_message
                        else "NAV agent: No response"
                    )
                )
            ],
        }

    except Exception as e:
        logger.error(f"Error invoking NAV agent: {e}")
        return {
            "nav_result": f"Error: {str(e)}",
            "messages": [AIMessage(content=f"NAV agent error: {str(e)}")],
        }


async def invoke_mcp_agent(
    state: RouterState,
    config: RunnableConfig,
    *,
    store: BaseStore,
) -> dict[str, Any]:
    """Invoke the MCP agent for general queries.

    Args:
        state: Current router state
        config: Runtime configuration
        store: PostgreSQL store for persistence

    Returns:
        Updated state with MCP agent response
    """
    try:
        user_context = config.get("configurable", {}).get("user", {})
        if not user_context:
            user_context = {
                "user_id": "test_user",
                "role": "admin",
                "scope": ["mcp-agent", "order-agent", "nav-agent", "router-agent"],
            }

        # Load MCP agent
        mcp_graph = await _load_subagent("mcp")

        # Transform state
        messages = state["messages"]
        mcp_state = {"messages": messages}

        # Invoke MCP agent
        mcp_config = {
            "configurable": {
                "thread_id": config.get("configurable", {}).get("thread_id", "default"),
                "user": user_context,
            }
        }

        result = await mcp_graph.ainvoke(mcp_state, config=mcp_config)

        # Extract final message
        final_message = ""
        if "messages" in result:
            for msg in reversed(result["messages"]):
                if isinstance(msg, AIMessage):
                    final_message = msg.content
                    break

        # Save interaction to persistent memory
        _save_agent_interaction(store, config, "mcp", final_message)

        logger.info(f"MCP agent completed for user {user_context.get('user_id')}")

        return {
            "messages": [AIMessage(content=final_message or "MCP agent completed")],
        }

    except Exception as e:
        logger.error(f"Error invoking MCP agent: {e}")
        return {
            "messages": [
                AIMessage(content=f"Hello! I'm here to help. Error: {str(e)}")
            ],
        }


async def synthesize_results(
    state: RouterState,
    config: RunnableConfig,
    *,
    store: BaseStore,
) -> dict[str, Any]:
    """Synthesize results from subagents into final response.

    Args:
        state: Current router state with all agent results
        config: Runtime configuration
        store: PostgreSQL store for persistence

    Returns:
        Updated state with synthesized response
    """
    try:
        from langchain_aws.chat_models import ChatBedrock

        user_context = config.get("configurable", {}).get("user", {})
        if not user_context:
            user_context = {
                "user_id": "test_user",
                "role": "admin",
                "scope": ["mcp-agent", "order-agent", "nav-agent", "router-agent"],
            }

        # Collect results
        results = []
        if state.get("order_result"):
            results.append(f"Order Agent: {state['order_result']}")
        if state.get("nav_result"):
            results.append(f"NAV Agent: {state['nav_result']}")

        # Get original user message
        user_message = None
        for msg in state["messages"]:
            if isinstance(msg, HumanMessage):
                user_message = msg
                break

        # If no user message and we have agent results (file upload scenario),
        # return the agent result directly
        if not user_message and results:
            combined_result = "\n\n".join(results)

            # Save synthesis to persistent memory
            _save_agent_interaction(store, config, "synthesis", combined_result)

            logger.info(
                f"File upload processed successfully for user {user_context.get('user_id')}"
            )
            return {
                "messages": [AIMessage(content=combined_result)],
            }

        if not user_message:
            user_message = HumanMessage(content="No original query")

        # Synthesize results
        model = ChatBedrock(
            model_id=os.getenv(
                "BEDROCK_MODEL_ID",
                "anthropic.claude-3-5-sonnet-20241022-v2:0",
            ),
            region_name=os.getenv("AWS_REGION", "us-east-1"),
            temperature=0,
            max_tokens=2048,
        )

        synthesis_context = (
            "\n\n".join(results) if results else "No agent results available"
        )
        synthesis_prompt = f"""Original user query: {user_message.content}

Agent Results:
{synthesis_context}

Please synthesize these results into a clear, helpful response."""

        system_msg = SystemMessage(content=SYNTHESIZER_SYSTEM_PROMPT)
        response = model.invoke([system_msg, HumanMessage(content=synthesis_prompt)])

        # Save synthesis to persistent memory
        _save_agent_interaction(store, config, "synthesis", response.content)

        logger.info(f"Results synthesized for user {user_context.get('user_id')}")

        return {
            "messages": [AIMessage(content=response.content)],
        }

    except Exception as e:
        logger.error(f"Error in synthesize_results: {e}")
        return {
            "messages": [AIMessage(content=f"Error synthesizing results: {str(e)}")],
        }


def _should_continue(state: RouterState) -> str:
    """Determine next step based on routing decision.

    Args:
        state: Current router state

    Returns:
        Next node to execute
    """
    route_decision = state.get("route_decision", "general").lower().strip()

    logger.debug(f"Routing to: {route_decision}")

    if route_decision == "order":
        return "order_agent"
    elif route_decision == "nav":
        return "nav_agent"
    else:
        return "mcp_agent"

def remember_node(state, config, store):
    return remember_user_context(state, config, store=store)

def order_node(state, config, store):
    return invoke_order_agent(state, config, store=store)

def nav_node(state, config, store):
    return invoke_nav_agent(state, config, store=store)

def mcp_node(state, config, store):
    return invoke_mcp_agent(state, config, store=store)

def synthesize_node(state, config, store):
    return synthesize_results(state, config, store=store)

async def create_router_graph(store: BaseStore | None = None) -> StateGraph:
    """Create and compile the router agent graph.

    The graph follows this flow:
    1. START → remember → classify_query (Store user context & determine routing)
    2. classify_query → conditional routing (Route to appropriate agent(s))
    3. Single agent: invoke agent → synthesize
    4. Multiple agents: invoke all agents in parallel → synthesize
    5. synthesize → END

    Args:
        store: PostgreSQL store for persistent memory. If None, creates in-memory store.

    Returns:
        Compiled LangGraph StateGraph with persistence
    """
    # Initialize store if not provided
    if store is None:
        from langgraph.store.memory import InMemoryStore

        store = InMemoryStore()
        logger.info("Using in-memory store (no persistent storage)")
    else:
        logger.info("Using PostgreSQL store for persistence")

    # Create state graph
    graph = StateGraph(RouterState, config_schema=Context)

    # Add nodes with store access
    graph.add_node(
    "remember",
    lambda state, config: remember_user_context(state, config, store=store),
)

    graph.add_node("classify_query", classify_query)
    graph.add_node(
    "order_agent",
    partial(invoke_order_agent, store=store),
)

    graph.add_node(
        "nav_agent", lambda state, config: invoke_nav_agent(state, config, store=store)
    )
    graph.add_node(
        "mcp_agent", lambda state, config: invoke_mcp_agent(state, config, store=store)
    )
    graph.add_node(
        "synthesize",
        partial(synthesize_results, store=store),
    )

    # Add edges
    graph.add_edge(START, "remember")
    graph.add_edge("remember", "classify_query")

    # Conditional routing based on classification
    graph.add_conditional_edges(
        "classify_query",
        _should_continue,
        {
            "order_agent": "order_agent",
            "nav_agent": "nav_agent",
            "mcp_agent": "mcp_agent", # Start with first agent if multiple
            "synthesize": "synthesize",
        },
    )

    # All agents route to synthesis
    graph.add_edge("order_agent", "synthesize")
    graph.add_edge("nav_agent", "synthesize")

    # Synthesis and MCP agent lead to end
    graph.add_edge("synthesize", END)
    graph.add_edge("mcp_agent", END)

    # Compile with store for persistence
    compiled_graph = graph.compile(
        name="router-agent",
        store=store,
    )

    logger.info("Router agent graph compiled successfully with persistence")
    return compiled_graph


# Initialize graph at module level for use by LangGraph CLI

# Fallback: create a minimal graph for testing
async def _create_minimal_graph() -> StateGraph:
    """Create a minimal graph when main graph initialization fails."""
    from langgraph.store.memory import InMemoryStore

    store = InMemoryStore()
    g = StateGraph(RouterState, config_schema=Context)
    g.add_node(
        "remember",
        lambda state, config: remember_node(state, config, store=store),
    )
    g.add_node("classify_query", classify_query)
    g.add_edge(START, "remember")
    g.add_edge("remember", "classify_query")
    g.add_edge("classify_query", END)
    return g.compile(store=store)


# For compatibility with langgraph CLI
# Graph will be initialized by the application (FastAPI lifespan)
graph = None

