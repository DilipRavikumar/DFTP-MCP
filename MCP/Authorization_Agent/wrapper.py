import sys
import os

_agent_dir = os.path.dirname(os.path.abspath(__file__))

if _agent_dir not in sys.path:
    sys.path.insert(0, _agent_dir)

from build import build_graph

def process_request(request: str) -> str:
    try:
        app = build_graph()
        final_state = app.invoke({"prompt": request})
        return str(final_state.get("result", "No result returned"))
    except Exception as e:
        return f"Error in Authorization Agent: {str(e)}"

def extract_scope_and_roles(request: str = "") -> dict:
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
