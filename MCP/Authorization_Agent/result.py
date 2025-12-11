def get_service_result(scope, query):
    # Add business scopes
    if scope in ["MutualFunds", "Assets", "Wealth", "General"]:
        return f"Business user allowed ({scope}): processed query '{query}'"
    if scope == "ACCOUNT_MANAGER":
        return f"Manager allowed: processed query '{query}'"
    if scope == "VIEWER":
        return f"Viewer access: read-only response for '{query}'"
    if scope == "BASIC_USER":
        return f"Basic user response for '{query}'"
    return f"Unauthorized: Scope '{scope}' is not in allowed list"
