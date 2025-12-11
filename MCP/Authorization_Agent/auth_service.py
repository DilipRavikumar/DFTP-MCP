import json
from jose import jwt

def decode_keycloak_token(token: str) -> dict:
    try:
        # Disable signature check (local dev mode)
        return jwt.get_unverified_claims(token)
    except Exception:
        return {}

def get_scope_from_token(token: str) -> str:
    payload = decode_keycloak_token(token)
    
    # Keycloak stores client scopes in "scope" claim (string)
    scope_string = payload.get("scope", "")
    
    # Check for allowed scopes in priority order
    # Position Agent: MutualFunds, Assets, Wealth
    # Order Details Agent: MutualFunds, Assets, General
    # Order Ingestion Agent: MutualFunds, Assets, ACCOUNT_MANAGER
    if "MutualFunds" in scope_string:
        return "MutualFunds"
    if "Assets" in scope_string:
        return "Assets"
    if "Wealth" in scope_string:
        return "Wealth"
    if "General" in scope_string:
        return "General"
    if "ACCOUNT_MANAGER" in scope_string:
        return "ACCOUNT_MANAGER"
    
    return "unauthorized"

def get_roles_from_token(token: str):
    payload = decode_keycloak_token(token)

    # realm roles → payload["realm_access"]["roles"]
    realm_roles = payload.get("realm_access", {}).get("roles", [])

    # client roles
    client_roles = []
    if "resource_access" in payload:
        for client in payload["resource_access"].values():
            client_roles.extend(client.get("roles", []))

    all_roles = list(set(realm_roles + client_roles))

    return all_roles
