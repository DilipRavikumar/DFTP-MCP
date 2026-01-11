async def handle_general_query(
    state: RouterState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Handle general queries that don't require specialized agents.
    
    Args:
        state: Current router state
        config: Runtime configuration
        
    Returns:
        Updated state with general response
    """
    try:
        from langchain_aws.chat_models import ChatBedrock
        
        # Get the latest user message
        messages = state["messages"]
        user_message = None
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                user_message = msg
                break
        
        if not user_message:
            return {
                "messages": [AIMessage(content="Hello! How can I help you today?")],
            }
        
        # Use LLM to respond to general query
        model = ChatBedrock(
            model_id=os.getenv(
                "BEDROCK_MODEL_ID",
                "anthropic.claude-3-5-sonnet-20241022-v2:0",
            ),
            region_name=os.getenv("AWS_REGION", "us-east-1"),
            temperature=0.7,
            max_tokens=512,
        )
        
        system_msg = SystemMessage(content="You are a helpful assistant. Respond to the user's query in a friendly and concise manner.")
        response = model.invoke([system_msg, user_message])
        
        logger.info("Handled general query")
        
        return {
            "messages": [AIMessage(content=response.content)],
        }
        
    except Exception as e:
        logger.error(f"Error in handle_general_query: {e}")
        return {
            "messages": [AIMessage(content="Hello! I'm here to help. You can ask me about orders or NAV files.")],
        }
