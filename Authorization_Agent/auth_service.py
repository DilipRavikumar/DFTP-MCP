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

    if "MutualFunds" in scope_string:
        return "MutualFunds"
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
