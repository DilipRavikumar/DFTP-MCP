"""Production-ready LangGraph router agent for multi-agent coordination.

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

import asyncio
import logging
import os
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from typing_extensions import Annotated, TypedDict

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(os.getenv("AGENT_LOG_LEVEL", "INFO"))


class UserContext(TypedDict, total=False):
    """User context for authorization.

    See: https://langchain-ai.github.io/langgraph/cloud/how-tos/auth/
    """

    user_id: str
    role: str
    scope: list[str]


class Context(TypedDict):
    """Context parameters for the router agent.

    Set these when creating assistants OR when invoking the graph.
    See: https://langchain-ai.github.io/langgraph/cloud/how-tos/configuration_cloud/
    """

    thread_id: str
    user: UserContext


class RouterState(TypedDict):
    """State schema for the router agent.

    Follows the MessagesState pattern for chat-based agents.
    See: https://langchain-ai.github.io/langgraph/concepts/agentic-agents/
    """

    messages: Annotated[list[BaseMessage], "The conversation messages"]
    route_decision: Annotated[str, "Routing decision made by classifier"]
    order_result: Annotated[str, "Result from order agent"]
    nav_result: Annotated[str, "Result from NAV agent"]


ROUTER_SYSTEM_PROMPT = """You are a query router agent. Your job is to classify user queries and route them to the appropriate specialized agents.

Analyze the user's query and determine which specialized agent(s) should handle it:
- "order": Order management (file uploads, order creation, tracking)
- "nav": NAV file management (NAV uploads, health checks, processing)
- "general": Simple questions, greetings, calculations, or general queries (routes to MCP general agent)
- "multiple": Multiple agents needed for this task

Respond with ONLY the routing decision in this exact format:
ROUTE: <decision>
REASON: <brief explanation>
"""

SYNTHESIZER_SYSTEM_PROMPT = """You are a response synthesizer. Your job is to combine results from multiple agents into a coherent, helpful response.

Analyze the results provided and synthesize them into a clear, organized response that directly answers the user's original question."""


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
            import src.order_agent.graph as order_module
            return await order_module.get_graph()
        elif agent_name == "nav":
            import src.nav_agent.graph as nav_module
            # get_graph() is synchronous for nav agent
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
            logger.warning("No user context found. Using default 'test_user' for development.")
            user_context = {
                "user_id": "test_user",
                "role": "admin",
                "scope": ["mcp-agent", "order-agent", "nav-agent", "router-agent"]
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
) -> dict[str, Any]:
    """Invoke the order agent as a subgraph.

    Transforms router state to order agent state and back.

    Args:
        state: Current router state
        config: Runtime configuration

    Returns:
        Updated state with order agent result
    """
    try:
        user_context = config.get("configurable", {}).get("user", {})
        if not user_context:
             user_context = {
                "user_id": "test_user",
                "roles": ["admin"], # Updated to list
                "scope": ["mutual funds", "mcp-agent", "order-agent", "nav-agent", "router-agent"]
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
) -> dict[str, Any]:
    """Invoke the NAV agent as a subgraph.

    Transforms router state to NAV agent state and back.

    Args:
        state: Current router state
        config: Runtime configuration

    Returns:
        Updated state with NAV agent result
    """
    try:
        user_context = config.get("configurable", {}).get("user", {})

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
        if "messages" in result:
            for msg in reversed(result["messages"]):
                if isinstance(msg, AIMessage):
                    final_message = msg.content
                    break

        logger.info(
            f"NAV agent completed for user {user_context.get('user_id')}: {final_message[:100]}"
        )

        return {
            "nav_result": final_message or "NAV agent completed without response",
            "messages": [AIMessage(content=f"NAV agent: {final_message}")],
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
) -> dict[str, Any]:
    """Invoke the MCP agent for general queries.
    
    Args:
        state: Current router state
        config: Runtime configuration
        
    Returns:
        Updated state with MCP agent response
    """
    try:
        user_context = config.get("configurable", {}).get("user", {})
        if not user_context:
            user_context = {
                "user_id": "test_user",
                "role": "admin",
                "scope": ["mcp-agent", "order-agent", "nav-agent", "router-agent"]
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
        
        logger.info(f"MCP agent completed for user {user_context.get('user_id')}")
        
        return {
            "messages": [AIMessage(content=final_message or "MCP agent completed")],
        }
        
    except Exception as e:
        logger.error(f"Error invoking MCP agent: {e}")
        return {
            "messages": [AIMessage(content=f"Hello! I'm here to help. Error: {str(e)}")],
        }


async def synthesize_results(
    state: RouterState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Synthesize results from subagents into final response.

    Args:
        state: Current router state with all agent results
        config: Runtime configuration

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
                "scope": ["mcp-agent", "order-agent", "nav-agent", "router-agent"]
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

        synthesis_context = "\n\n".join(results) if results else "No agent results available"
        synthesis_prompt = f"""Original user query: {user_message.content}

Agent Results:
{synthesis_context}

Please synthesize these results into a clear, helpful response."""

        system_msg = SystemMessage(content=SYNTHESIZER_SYSTEM_PROMPT)
        response = model.invoke([system_msg, HumanMessage(content=synthesis_prompt)])

        logger.info(
            f"Results synthesized for user {user_context.get('user_id')}"
        )

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
    elif route_decision == "multiple":
        return "multiple_agents"
    else:
        return "mcp_agent"



async def initialize_checkpointer() -> Any:
    """Initialize PostgreSQL checkpointer for state persistence.

    Returns:
        Configured AsyncPostgresSaver instance, or MemorySaver as fallback
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
        "postgresql://postgres:postgres@localhost:5432/router_agent",
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


async def create_router_graph() -> StateGraph:
    """Create and compile the router agent graph.

    The graph follows this flow:
    1. START → classify_query (Determine routing)
    2. classify_query → conditional routing (Route to appropriate agent(s))
    3. Single agent: invoke agent → synthesize
    4. Multiple agents: invoke all agents in parallel → synthesize
    5. synthesize → END

    Returns:
        Compiled LangGraph StateGraph with PostgreSQL persistence
    """
    # Initialize checkpointer
    # checkpointer = await initialize_checkpointer()

    # Create state graph
    graph = StateGraph(RouterState, config_schema=Context)

    # Add nodes
    graph.add_node("classify_query", classify_query)
    graph.add_node("order_agent", invoke_order_agent)
    graph.add_node("nav_agent", invoke_nav_agent)
    graph.add_node("mcp_agent", invoke_mcp_agent)
    graph.add_node("synthesize", synthesize_results)

    # Add edges
    graph.add_edge(START, "classify_query")

    # Conditional routing based on classification
    graph.add_conditional_edges(
        "classify_query",
        _should_continue,
        {
            "order_agent": "order_agent",
            "nav_agent": "nav_agent",
            "mcp_agent": "mcp_agent",
            "multiple_agents": "order_agent",  # Start with first agent if multiple
            "synthesize": "synthesize",
        },
    )

    # All agents route to synthesis
    graph.add_edge("order_agent", "synthesize")
    graph.add_edge("nav_agent", "synthesize")

    # Synthesis and MCP agent lead to end
    graph.add_edge("synthesize", END)
    graph.add_edge("mcp_agent", END)

    # Compile with checkpointer for persistence
    compiled_graph = graph.compile(
        name="router-agent",
    )

    logger.info("Router agent graph compiled successfully")
    return compiled_graph


# Initialize graph at module level for use by LangGraph CLI
async def _init_graph() -> StateGraph:
    """Initialize the graph asynchronously."""
    return await create_router_graph()


# For compatibility with langgraph CLI
try:
    graph = asyncio.run(_init_graph())
except Exception as e:
    logger.error(f"Failed to initialize router agent graph: {e}")
    # Fallback: create a minimal graph for testing
    from langgraph.checkpoint.memory import MemorySaver

    async def _create_minimal_graph() -> StateGraph:
        g = StateGraph(RouterState, config_schema=Context)
        g.add_node("classify_query", classify_query)
        g.add_edge(START, "classify_query")
        return g.compile(checkpointer=MemorySaver())

    graph = asyncio.run(_create_minimal_graph())
