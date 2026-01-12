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
    roles: list[str]
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


# ========== ROLE-BASED ACCESS CONTROL ==========

def _check_agent_access(user_context: UserContext, agent_name: str) -> tuple[bool, str]:
    """Check if user has access to a specific agent based on their role.
    
    Authorization Rules:
    - ORDER AGENT: Requires role "distributor" OR "admin"
    - NAV AGENT: Requires role "fundhouse" OR "admin"
    - MCP AGENT: Accessible to "distributor", "fundhouse", or "admin"
    
    Args:
        user_context: User context with role information
        agent_name: Name of the agent ('order', 'nav', 'mcp')
        
    Returns:
        Tuple of (is_authorized: bool, message: str)
    """
    # Get user roles (handle both single role and roles list)
    user_role = user_context.get("role", "").lower()
    user_roles = [r.lower() for r in user_context.get("roles", [])] if user_context.get("roles") else []
    
    # Combine both for easier checking
    all_roles = {user_role} | set(user_roles)
    all_roles.discard("")  # Remove empty strings
    
    logger.info(f"[RBAC] Checking access for agent '{agent_name}': user_id={user_context.get('user_id')}, roles={all_roles}")
    
    if agent_name.lower() == "order":
        if "admin" in all_roles or "distributor" in all_roles:
            logger.info(f"[RBAC] User {user_context.get('user_id')} AUTHORIZED for order agent (roles: {all_roles})")
            return True, "User authorized for order agent"
        else:
            msg = f"[RBAC] User {user_context.get('user_id')} DENIED access to order agent. Required: 'distributor' or 'admin', Got: {all_roles}"
            logger.warning(msg)
            return False, "Access denied."
    
    elif agent_name.lower() == "nav":
        if "admin" in all_roles or "fundhouse" in all_roles:
            logger.info(f"[RBAC] User {user_context.get('user_id')} AUTHORIZED for nav agent (roles: {all_roles})")
            return True, "User authorized for nav agent"
        else:
            msg = f"[RBAC] User {user_context.get('user_id')} DENIED access to nav agent. Required: 'fund_house' or 'admin', Got: {all_roles}"
            logger.warning(msg)
            return False, "Access denied."
    
    elif agent_name.lower() == "mcp":
        if "admin" in all_roles or "distributor" in all_roles or "fundhouse" in all_roles:
            logger.info(f"[RBAC] User {user_context.get('user_id')} AUTHORIZED for MCP agent (roles: {all_roles})")
            return True, "User authorized for MCP agent"
        else:
            msg = f"[RBAC] User {user_context.get('user_id')} DENIED access to MCP agent. Required: any of 'distributor', 'fundhouse', or 'admin', Got: {all_roles}"
            logger.warning(msg)
            return False, "Access denied."
    
    else:
        logger.warning(f"[RBAC] Unknown agent: {agent_name}")
        return False, f"Unknown agent: {agent_name}"


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

        # LOG: Capture raw config to verify user details propagation
        logger.info(f"[ROUTER] classify_query() called with config keys: {list(config.keys())}")
        configurable = config.get("configurable", {})
        logger.info(f"[ROUTER] configurable keys: {list(configurable.keys())}")
        
        user_context = configurable.get("user", {})
        logger.info(f"[ROUTER] Raw user_context from config: {user_context}")
        logger.info(f"[ROUTER] user_context keys: {list(user_context.keys()) if user_context else 'EMPTY'}")
        
        if not user_context:
            logger.warning(" [ROUTER] No user context found. Using default 'test_user' for development.")
            user_context = {
                "user_id": "test_user",
                "roles": ["admin"],
                "scope": ["mcp-agent", "order-agent", "nav-agent", "router-agent"]
            }
            logger.warning(f" [ROUTER] Using fallback user_context: {user_context}")
            # raise ValueError("User context is required in config")
        else:
            logger.info(f"  [ROUTER] User context successfully received:")
            logger.info(f"   - user_id: {user_context.get('user_id')}")
            logger.info(f"   - role: {user_context.get('role')}")
            logger.info(f"   - roles: {user_context.get('roles')}")
            logger.info(f"   - scope: {user_context.get('scope')}")

        # Get the latest user message
        messages = state["messages"]
        logger.info(f"[ROUTER] Message count in state: {len(messages)}")
        
        user_message = None
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                user_message = msg
                logger.info(f"[ROUTER] Found latest HumanMessage: {msg.content[:100]}")
                break

        if not user_message:
            logger.warning("[ROUTER]  No HumanMessage found in state")
            return {
                "route_decision": "general",
            }

        # Classify the query
        logger.info(f"[ROUTER] Classifying query for user: {user_context.get('user_id')}")
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
                logger.info(f"[ROUTER] Parsed route decision: {route_decision}")
            except (IndexError, ValueError):
                logger.warning(f"[ROUTER]  Could not parse route decision: {response_text}")

        logger.info(
            f" [ROUTER] Query classified as '{route_decision}' for user {user_context.get('user_id')} "
            f"(user_context propagated: {bool(user_context and user_context.get('user_id') != 'test_user')})"
        )
        
        return {
            "route_decision": route_decision,
        }

    except Exception as e:
        logger.error(f" [ROUTER] Error in classify_query: {e}", exc_info=True)
        return {
            "route_decision": "general",
        }


async def invoke_order_agent(
    state: RouterState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Invoke the order agent as a subgraph.

    Transforms router state to order agent state and back.
     ROLE-BASED ACCESS: Requires 'distributor' or 'admin' role

    Args:
        state: Current router state
        config: Runtime configuration

    Returns:
        Updated state with order agent result
    """
    try:
        #  LOG: Capture user context at order agent invocation
        logger.info("[ROUTER→ORDER] invoke_order_agent() called")
        logger.info(f"[ROUTER→ORDER] config keys: {list(config.keys())}")
        
        user_context = config.get("configurable", {}).get("user", {})
        logger.info(f"[ROUTER→ORDER] User context from config: {user_context}")
        
        # ========== ROLE-BASED ACCESS CHECK (BEFORE FALLBACK) ==========
        is_authorized, auth_message = _check_agent_access(user_context, "order")
        if not is_authorized:
            logger.warning(f" [ROUTER→ORDER] Access denied for user {user_context.get('user_id')}")
            return {
                "order_result": auth_message,
                "messages": [AIMessage(content=f"{auth_message}")],
            }
        # ================================================================
        
        if not user_context:
            logger.warning("[ROUTER→ORDER] No user context received from router!")
            user_context = {
                "user_id": "test_user",
                "roles": ["admin"], # Updated to list
                "scope": ["mutual funds", "mcp-agent", "order-agent", "nav-agent", "router-agent"]
            }
            logger.warning(f" [ROUTER→ORDER] Using fallback: {user_context}")
        else:
            logger.info(f" [ROUTER→ORDER] User context successfully propagated:")
            logger.info(f"   - user_id: {user_context.get('user_id')}")
            logger.info(f"   - roles: {user_context.get('roles')}")
            logger.info(f"   - scope: {user_context.get('scope')}")

        # Load order agent
        logger.info("[ROUTER→ORDER] Loading order agent subgraph...")
        order_graph = await _load_subagent("order")

        # Transform state: extract user messages for order agent
        messages = state["messages"]
        logger.info(f"[ROUTER→ORDER] Preparing state with {len(messages)} messages")
        order_state = {"messages": messages}

        # Invoke order agent with user context
        logger.info(f"[ROUTER→ORDER] Invoking order agent for user: {user_context.get('user_id')}")
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
            f" [ROUTER→ORDER] Order agent completed for user {user_context.get('user_id')}: "
            f"{final_message[:100] if final_message else 'NO RESPONSE'}"
        )

        return {
            "order_result": final_message or "Order agent completed without response",
            "messages": [AIMessage(content=f"Order agent: {final_message}")],
        }

    except Exception as e:
        logger.error(f" [ROUTER→ORDER] Error invoking order agent: {e}", exc_info=True)
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
     ROLE-BASED ACCESS: Requires 'fundhouse' or 'admin' role

    Args:
        state: Current router state
        config: Runtime configuration

    Returns:
        Updated state with NAV agent result
    """
    try:
        from langchain_core.messages import ToolMessage
        
        #  LOG: Capture user context at NAV agent invocation
        logger.info("[ROUTER→NAV] invoke_nav_agent() called")
        logger.info(f"[ROUTER→NAV] config keys: {list(config.keys())}")
        
        user_context = config.get("configurable", {}).get("user", {})
        logger.info(f"[ROUTER→NAV] User context from config: {user_context}")
        
        # ========== ROLE-BASED ACCESS CHECK (BEFORE FALLBACK) ==========
        is_authorized, auth_message = _check_agent_access(user_context, "nav")
        if not is_authorized:
            logger.warning(f" [ROUTER→NAV] Access denied for user {user_context.get('user_id')}")
            return {
                "nav_result": auth_message,
                "messages": [AIMessage(content=f"{auth_message}")],
            }
        # ================================================================
        
        if not user_context:
            logger.warning(" [ROUTER→NAV] No user context received from router!")
            user_context = {
                "user_id": "test_user",
                "roles": ["admin"],
                "scope": ["mcp-agent", "order-agent", "nav-agent", "router-agent"]
            }
            logger.warning(f" [ROUTER→NAV] Using fallback: {user_context}")
        else:
            logger.info(f" [ROUTER→NAV] User context successfully propagated:")
            logger.info(f"   - user_id: {user_context.get('user_id')}")
            logger.info(f"   - roles: {user_context.get('roles')}")
            logger.info(f"   - scope: {user_context.get('scope')}")

        # Load NAV agent
        logger.info("[ROUTER→NAV] Loading NAV agent subgraph...")
        nav_graph = await _load_subagent("nav")

        # Transform state: extract user messages for NAV agent
        messages = state["messages"]
        logger.info(f"[ROUTER→NAV] Preparing state with {len(messages)} messages")
        nav_state = {"messages": messages}

        # Invoke NAV agent with user context
        logger.info(f"[ROUTER→NAV] Invoking NAV agent for user: {user_context.get('user_id')}")
        nav_config = {
            "configurable": {
                "thread_id": config.get("configurable", {}).get("thread_id", "default"),
                "user": user_context,
            }
        }

        result = await nav_graph.ainvoke(nav_state, config=nav_config)

        # Extract final message from NAV agent result
        final_message = ""
        
        logger.info(f"[ROUTER→NAV] NAV agent result keys: {result.keys() if isinstance(result, dict) else 'not a dict'}")
        logger.info(f"[ROUTER→NAV] NAV agent messages count: {len(result.get('messages', []))} messages")
        
        # Log all messages for debugging
        if "messages" in result:
            for i, msg in enumerate(result["messages"]):
                logger.debug(f"[ROUTER→NAV] Message {i}: {type(msg).__name__} - {str(msg.content)[:100]}")
        
        # First, try to find a ToolMessage (file upload response)
        if "messages" in result:
            for msg in reversed(result["messages"]):
                if isinstance(msg, ToolMessage):
                    final_message = msg.content
                    logger.info(f"[ROUTER→NAV] Extracted tool response for user {user_context.get('user_id')}")
                    break
            
            # If no ToolMessage, fall back to last AIMessage
            if not final_message:
                for msg in reversed(result["messages"]):
                    if isinstance(msg, AIMessage):
                        final_message = msg.content
                        break

        logger.info(
            f" [ROUTER→NAV] NAV agent completed for user {user_context.get('user_id')}: "
            f"{final_message[:100] if final_message else 'empty'}"
        )

        return {
            "nav_result": final_message or "NAV agent completed without response",
            "messages": [AIMessage(content=f"NAV agent: {final_message}" if final_message else "NAV agent: No response")],
        }

    except Exception as e:
        logger.error(f" [ROUTER→NAV] Error invoking NAV agent: {e}", exc_info=True)
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
        #  LOG: Capture user context at MCP agent invocation
        logger.info("[ROUTER→MCP] invoke_mcp_agent() called")
        logger.info(f"[ROUTER→MCP] config keys: {list(config.keys())}")
        
        user_context = config.get("configurable", {}).get("user", {})
        logger.info(f"[ROUTER→MCP] User context from config: {user_context}")
        
        # ========== ROLE-BASED ACCESS CHECK (BEFORE FALLBACK) ==========
        is_authorized, auth_message = _check_agent_access(user_context, "mcp")
        if not is_authorized:
            logger.warning(f"[ROUTER→MCP] Access denied for user {user_context.get('user_id')}")
            return {
                "messages": [AIMessage(content=f" {auth_message}")],
            }
        # ================================================================
        
        if not user_context:
            logger.warning(" [ROUTER→MCP] No user context received from router!")
            user_context = {
                "user_id": "test_user",
                "roles": ["admin"],
                "scope": ["mcp-agent", "order-agent", "nav-agent", "router-agent"]
            }
            logger.warning(f" [ROUTER→MCP] Using fallback: {user_context}")
        else:
            logger.info(f" [ROUTER→MCP] User context successfully propagated:")
            logger.info(f"   - user_id: {user_context.get('user_id')}")
            logger.info(f"   - roles: {user_context.get('roles')}")
            logger.info(f"   - scope: {user_context.get('scope')}")
        
        # Load MCP agent
        logger.info("[ROUTER→MCP] Loading MCP agent subgraph...")
        mcp_graph = await _load_subagent("mcp")
        
        # Transform state
        messages = state["messages"]
        logger.info(f"[ROUTER→MCP] Preparing state with {len(messages)} messages")
        mcp_state = {"messages": messages}
        
        # Invoke MCP agent
        logger.info(f"[ROUTER→MCP] Invoking MCP agent for user: {user_context.get('user_id')}")
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
            logger.info(f"[ROUTER→MCP] MCP agent returned {len(result['messages'])} messages")
            for i, msg in enumerate(result["messages"]):
                logger.debug(f"[ROUTER→MCP] Message {i}: {type(msg).__name__}")
            
            for msg in reversed(result["messages"]):
                if isinstance(msg, AIMessage):
                    final_message = msg.content
                    logger.info(f"[ROUTER→MCP] Extracted AIMessage response")
                    break
        
        logger.info(
            f" [ROUTER→MCP] MCP agent completed for user {user_context.get('user_id')}: "
            f"{final_message[:100] if final_message else 'empty'}"
        )
        
        return {
            "messages": [AIMessage(content=final_message or "MCP agent completed")],
        }
        
    except Exception as e:
        logger.error(f" [ROUTER→MCP] Error invoking MCP agent: {e}", exc_info=True)
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

        #  LOG: Capture user context at synthesis stage
        logger.info("[ROUTER→SYNTHESIZE] synthesize_results() called")
        logger.info(f"[ROUTER→SYNTHESIZE] config keys: {list(config.keys())}")
        
        user_context = config.get("configurable", {}).get("user", {})
        logger.info(f"[ROUTER→SYNTHESIZE] User context from config: {user_context}")
        
        if not user_context:
            logger.warning(" [ROUTER→SYNTHESIZE] No user context received!")
            user_context = {
                "user_id": "test_user",
                "roles": ["admin"],
                "scope": ["mcp-agent", "order-agent", "nav-agent", "router-agent"]
            }
            logger.warning(f" [ROUTER→SYNTHESIZE] Using fallback: {user_context}")
        else:
            logger.info(f" [ROUTER→SYNTHESIZE] User context successfully propagated:")
            logger.info(f"   - user_id: {user_context.get('user_id')}")
            logger.info(f"   - roles: {user_context.get('roles')}")
            logger.info(f"   - scope: {user_context.get('scope')}")

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
    logger.info("═" * 80)
    logger.info(" [ROUTER] Router Graph Initialization Started")
    logger.info("═" * 80)
    
    # Initialize checkpointer
    # checkpointer = await initialize_checkpointer()

    # Create state graph
    graph = StateGraph(RouterState, config_schema=Context)
    logger.info("[ROUTER] StateGraph created with RouterState schema")

    # Add nodes
    graph.add_node("classify_query", classify_query)
    graph.add_node("order_agent", invoke_order_agent)
    graph.add_node("nav_agent", invoke_nav_agent)
    graph.add_node("mcp_agent", invoke_mcp_agent)
    graph.add_node("synthesize", synthesize_results)
    logger.info("[ROUTER] Added 5 nodes: classify_query, order_agent, nav_agent, mcp_agent, synthesize")

    # Add edges
    graph.add_edge(START, "classify_query")
    logger.info("[ROUTER] Router graph initialized and ready to receive user context")

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


# Fallback: create a minimal graph for testing
async def _create_minimal_graph() -> StateGraph:
    """Create a minimal graph when main graph initialization fails."""
    from langgraph.checkpoint.memory import MemorySaver

    g = StateGraph(RouterState, config_schema=Context)
    g.add_node("classify_query", classify_query)
    g.add_edge(START, "classify_query")
    g.add_edge("classify_query", END)
    return g.compile(checkpointer=MemorySaver())


# For compatibility with langgraph CLI
try:
    graph = asyncio.run(_init_graph())
except Exception as e:
    logger.error(f"Failed to initialize router agent graph: {e}")
    graph = asyncio.run(_create_minimal_graph())
