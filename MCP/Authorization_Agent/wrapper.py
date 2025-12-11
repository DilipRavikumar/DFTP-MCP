import sys
import os

# Get the directory where this file is located (Authorization_Agent directory)
_agent_dir = os.path.dirname(os.path.abspath(__file__))

# CRITICAL: Add Authorization_Agent directory to sys.path FIRST
# This must happen before any imports from this directory
if _agent_dir not in sys.path:
    sys.path.insert(0, _agent_dir)

# Now import build - it should be able to find agents, schema, etc.
# because they're all in the same directory (Authorization_Agent)
from build import build_graph

def process_request(request: str) -> str:
    """Entry point for the Authorization Agent."""
    try:
        app = build_graph()
        final_state = app.invoke({"prompt": request})
        return str(final_state.get("result", "No result returned"))
    except Exception as e:
        return f"Error in Authorization Agent: {str(e)}"

def extract_scope_and_roles(request: str = "") -> dict:
    """Extract scope and roles from real Keycloak token in session.json.
    Returns dict with scope and roles.
    """
    try:
        from agents import extract_token_and_scope
        token, scope, roles = extract_token_and_scope(request)
        
        return {
            "scope": scope if scope else "unauthorized",
            "roles": roles if roles else [],
            "token": token if token else ""
        }
    except Exception as e:
        return {
            "scope": "unauthorized",
            "roles": [],
            "token": "",
            "error": f"Failed to extract scope: {str(e)}"
        }
