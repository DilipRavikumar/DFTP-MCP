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
        
        result = mcp_graph.invoke(mcp_state, config=mcp_config)
        
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
