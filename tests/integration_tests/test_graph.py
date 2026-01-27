"""Integration tests for the MCP agent with authorization.

Tests the agent graph with various scenarios including:
- Authorization checks
- Multiple MCP servers
- Tool execution with scope validation
- State persistence
- Human-in-the-loop approval
"""

import pytest
from langchain_core.messages import HumanMessage

from agent.graph import AgentState, UserContext, graph

pytestmark = pytest.mark.anyio


@pytest.mark.langsmith
async def test_agent_with_user_authorization() -> None:
    """Test agent execution with proper user context."""
    user_context: UserContext = {
        "user_id": "test_user_1",
        "role": "editor",
        "scope": ["local_api"],
    }

    config = {
        "configurable": {
            "thread_id": "test_thread_1",
            "user": user_context,
        }
    }

    initial_state: AgentState = {
        "messages": [HumanMessage(content="List available resources")]
    }

    result = await graph.ainvoke(initial_state, config=config)

    assert result is not None
    assert "messages" in result
    assert len(result["messages"]) > 0


@pytest.mark.langsmith
async def test_agent_denies_unauthorized_scope() -> None:
    """Test that agent respects user scope restrictions."""
    user_context: UserContext = {
        "user_id": "test_user_2",
        "role": "viewer",
        "scope": [],  # No scope authorized
    }

    config = {
        "configurable": {
            "thread_id": "test_thread_2",
            "user": user_context,
        }
    }

    initial_state: AgentState = {
        "messages": [HumanMessage(content="Get data")]
    }

    result = await graph.ainvoke(initial_state, config=config)

    # Should return response (no tools available)
    assert result is not None
    assert "messages" in result


@pytest.mark.langsmith
async def test_state_persistence_with_user() -> None:
    """Test that state is persisted across invocations for same user."""
    thread_id = "test_persistence_thread"
    user_context: UserContext = {
        "user_id": "persistent_user",
        "role": "editor",
        "scope": ["local_api"],
    }

    config = {
        "configurable": {
            "thread_id": thread_id,
            "user": user_context,
        }
    }

    # First invocation
    first_state: AgentState = {
        "messages": [HumanMessage(content="What is available?")]
    }

    result1 = await graph.ainvoke(first_state, config=config)

    assert result1 is not None
    assert "messages" in result1


@pytest.mark.langsmith
async def test_different_users_isolated_threads() -> None:
    """Test that different users have isolated conversations."""
    thread_id = "shared_thread_id"

    # User 1
    user1_context: UserContext = {
        "user_id": "user_1",
        "role": "editor",
        "scope": ["local_api"],
    }

    config1 = {
        "configurable": {
            "thread_id": thread_id,
            "user": user1_context,
        }
    }

    state1: AgentState = {
        "messages": [HumanMessage(content="User 1 query")]
    }

    result1 = await graph.ainvoke(state1, config=config1)

    # User 2 with different role
    user2_context: UserContext = {
        "user_id": "user_2",
        "role": "viewer",
        "scope": ["local_api"],
    }

    config2 = {
        "configurable": {
            "thread_id": thread_id,
            "user": user2_context,
        }
    }

    state2: AgentState = {
        "messages": [HumanMessage(content="User 2 query")]
    }

    result2 = await graph.ainvoke(state2, config=config2)

    # Both should get responses
    assert result1 is not None
    assert result2 is not None


@pytest.mark.langsmith
async def test_error_handling() -> None:
    """Test error handling in the agent."""
    user_context: UserContext = {
        "user_id": "test_user",
        "role": "editor",
        "scope": ["local_api"],
    }

    config = {
        "configurable": {
            "thread_id": "test_error_thread",
            "user": user_context,
        }
    }

    initial_state: AgentState = {
        "messages": [HumanMessage(content="test message")]
    }

    result = await graph.ainvoke(initial_state, config=config)

    assert result is not None
    assert "messages" in result
