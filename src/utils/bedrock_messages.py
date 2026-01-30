from langchain_core.messages import HumanMessage, AIMessage

def sanitize_for_bedrock(messages):
    sanitized = []
    last_type = None

    for msg in messages:
        if isinstance(msg, AIMessage) and last_type is AIMessage:
            continue
        sanitized.append(msg)
        last_type = type(msg)

    # Bedrock REQUIRES last message to be Human
    if not isinstance(sanitized[-1], HumanMessage):
        sanitized.append(
            HumanMessage(content="Please continue.")
        )

    return sanitized
