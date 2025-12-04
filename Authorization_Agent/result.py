def get_service_result(role: str, query: str) -> str:
    if role == "LIC":
        return f"LIC service response for query: '{query}'"
    elif role == "MF":
        return f"Mutual Fund service response for query: '{query}'"
    else:
        return "Unauthorized: Invalid or missing token"
