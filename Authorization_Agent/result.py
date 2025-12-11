def get_service_result(scope: str, query: str) -> str:
    if scope == "ACCOUNT_MANAGER":
        return f"Manager allowed: processed query '{query}'"
    if scope == "VIEWER":
        return f"Viewer access: read-only response for '{query}'"
    if scope == "BASIC_USER":
        return f"Basic user response for '{query}'"
    return "Unauthorized: Invalid or missing permissions"
