def get_service_result(scope: str, query: str) -> str:
    if scope == "LIC":
        return f"LIC service response for query: '{query}'"
    elif scope == "MF":
        return f"Mutual Fund service response for query: '{query}'"
    else:
        return "Unauthorized: Invalid or missing token"
