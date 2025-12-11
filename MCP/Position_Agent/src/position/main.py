#!/usr/bin/env python3
"""
langgraph_order_agent_fixed.py

Positions orchestration agent (full file) with fixes:
 - JSON-decode MCP tool responses when they're JSON strings
 - Defensive logging of payloads sent to calculate
 - Slightly more defensive amount parsing (reuse previous improved parser)
"""

from typing import Any, Dict, Optional, List
import re
import json
import os
import asyncio
import traceback
import ast
import sys

# Dynamic import helper for auth service (assuming Authorization_Agent is sibling)
def get_auth_service():
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Go up 3 levels to reach 'MCP' root (src/position -> src -> Position_Agent -> MCP)
        mcp_root = os.path.abspath(os.path.join(current_dir, "..", "..", ".."))
        if mcp_root not in sys.path:
            sys.path.append(mcp_root)
        from Authorization_Agent.auth_service import get_roles_from_token
        return get_roles_from_token
    except Exception as e:
        print(f"Warning: Could not import auth service: {e}")
        return None

def check_distributor_role() -> bool:
    try:
        # Enforce looking for session.json in the project root first
        # Locate root by finding where 'main.py' is relative to src/position
        current_file = os.path.abspath(__file__)
        src_dir = os.path.dirname(current_file)
        # Go up: src/position -> src -> Position_Agent -> MCP
        mcp_root = os.path.abspath(os.path.join(src_dir, "..", "..", ".."))
        
        session_path = os.path.join(mcp_root, "session.json")
        
        if not os.path.exists(session_path):
             # Fallback to current working directory
             session_path = os.path.join(os.getcwd(), "session.json")
        
        if not os.path.exists(session_path):
            print(f"Warning: session.json not found at {session_path}")
            return False

        with open(session_path, "r") as f:
            tokens = json.load(f)
            token = tokens.get("access_token")
        
        if not token:
            return False

        get_roles = get_auth_service()
        if not get_roles:
            return False # Fail safe
            
        roles = get_roles(token)
        # Check for 'distributor' (case-insensitive)
        return any(str(r).lower() == "distributor" for r in roles)
            
    except Exception as e:
        print(f"Role check failed: {e}")
        return False


__all__ = [
    "process_request",
    "submit_order",
    "get_nav",
    "calculate_position",
    "main"
]

from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict

from langchain_aws import ChatBedrock
from langchain_mcp_adapters.client import MultiServerMCPClient


# MCP client
def build_mcp_client() -> MultiServerMCPClient:
    mcp_url = os.getenv("MCP_URL", "http://127.0.0.1:8001/mcp")
    return MultiServerMCPClient(
        {
            "positions_gateway": {
                "transport": "streamable_http",
                "url": mcp_url,
            }
        }
    )


# LLM invocation
def llm_invoke_sync(model, prompt_text: str) -> str:
    if model is None:
        raise RuntimeError("No router model provided for LLM-assisted parse.")

    if hasattr(model, "ainvoke"):
        try:
            resp = asyncio.run(model.ainvoke({"messages":[{"role":"user","content":prompt_text}]}))
            if isinstance(resp, dict) and "content" in resp:
                return resp["content"]
            return getattr(resp, "content", None) or str(resp)
        except RuntimeError:
            pass
        except Exception:
            pass

    if hasattr(model, "invoke"):
        resp = model.invoke(prompt_text)
        return getattr(resp, "content", None) or str(resp)

    raise RuntimeError("Router model has neither invoke nor ainvoke.")

#tool_calling
def call_mcp_tool_sync(tools: list, tool_name: str, tool_args: Dict[str, Any]) -> Any:
    lookup = {}
    for t in tools:
        n = getattr(t, "name", None) or getattr(t, "tool_name", None) or t.__class__.__name__
        lookup[n.lower()] = t

    t = lookup.get(tool_name.lower())
    if t is None:
        for k, obj in lookup.items():
            if tool_name.lower() in k or k in tool_name.lower():
                t = obj
                break
    if t is None:
        raise ValueError(f"Tool '{tool_name}' not found. Available: {list(lookup.keys())}")

    # try async first
    if hasattr(t, "ainvoke"):
        try:
            return asyncio.run(t.ainvoke(tool_args))
        except RuntimeError:
            pass
        except Exception:
            pass

    if hasattr(t, "invoke"):
        try:
            return t.invoke(tool_args)
        except Exception as sync_exc:
            if hasattr(t, "ainvoke"):
                try:
                    return asyncio.run(t.ainvoke(tool_args))
                except Exception as async_exc2:
                    raise RuntimeError(
                        f"Tool '{tool_name}' failed sync invoke ({sync_exc}) and async invoke ({async_exc2})."
                    ) from async_exc2
            raise

    if callable(t):
        return t(tool_args)

    raise RuntimeError(f"Tool '{tool_name}' has no invokable method.")


def extract_text_from_result(result: Any) -> str:
    """Extract text content from LangChain message objects or return string representation."""
    if isinstance(result, list):
        # Handle list of message objects (e.g., [{"type": "text", "text": "...", "id": "..."}])
        texts = []
        for item in result:
            if isinstance(item, dict):
                if "text" in item:
                    texts.append(item["text"])
                elif "content" in item:
                    texts.append(item["content"])
            elif hasattr(item, "text"):
                texts.append(item.text)
            elif hasattr(item, "content"):
                texts.append(item.content)
        return " ".join(str(t) for t in texts) if texts else str(result)
    elif isinstance(result, dict):
        if "text" in result:
            return result["text"]
        elif "content" in result:
            return result["content"]
        else:
            return str(result)
    elif hasattr(result, "text"):
        return result.text
    elif hasattr(result, "content"):
        return result.content
    else:
        return str(result)

def parse_json(obj: Any) -> Any:
    """If obj is a string that looks like JSON, parse and return the object. 
    Also handles LangChain message objects by extracting text first."""
    # First, extract text if it's a LangChain message object
    if isinstance(obj, (list, dict)) and not isinstance(obj, str):
        # Check if it looks like a LangChain message object
        if isinstance(obj, list) and len(obj) > 0 and isinstance(obj[0], dict) and "type" in obj[0]:
            obj = extract_text_from_result(obj)
        elif isinstance(obj, dict) and ("type" in obj or "text" in obj or "content" in obj):
            obj = extract_text_from_result(obj)
    
    if isinstance(obj, str):
        s = obj.strip()
        if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
            try:
                return json.loads(s)
            except Exception:
                # may be double-encoded or escaped; try un-escaping common patterns
                try:
                    un = s.encode('utf-8').decode('unicode_escape')
                    return json.loads(un)
                except Exception:
                    return obj
    return obj

# LangGraph state
class OrderAgentState(TypedDict):
    user_input: str
    clientName: Optional[str]
    fundNumber: Optional[int]
    dollarAmount: Optional[float]
    asOfDate: Optional[str]
    parsed_ok: bool
    submit_result: Optional[Any]
    nav_result: Optional[Any]
    position_result: Optional[Any]
    message: Optional[str]

# Build graph for orders
def build_order_graph(router_model, mcp_tools):
    # Improved parser (same as before)
    def parse_user_input(user_text: str) -> Dict[str, Any]:
        client = None
        fund = None
        amount = None
        date = None

        # fund detection
        m = re.search(r"\bfund(?:\s*number|\s*no|)\s*[:#]?\s*(\d{1,6})\b", user_text, flags=re.I)
        if not m:
            m = re.search(r"\bfund\s+(\d{1,6})\b", user_text, flags=re.I)
        if m:
            try:
                fund = int(m.group(1))
            except Exception:
                fund = None

        amount_kw_pattern = re.compile(
            r"(?:amount|invest(?:ing)?|put|deposit|rupees|rs\.?|inr|₹|\$)\s*[:\-]?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.\d+)?|[0-9]+(?:\.\d+)?)",
            flags=re.I,
        )
        m_amt = amount_kw_pattern.search(user_text)
        if m_amt:
            s = m_amt.group(1).replace(",", "")
            try:
                amount = float(s)
            except Exception:
                amount = None

        if amount is None:
            candidates = []
            for mm in re.finditer(r"([0-9]{1,3}(?:,[0-9]{3})*(?:\.\d+)?|[0-9]+(?:\.\d+)?)", user_text):
                token = mm.group(1)
                start, end = mm.start(1), mm.end(1)
                ctx = user_text[max(0, start-12): min(len(user_text), end+12)].lower()
                score = 0
                if "." in token:
                    score += 3
                if any(k in ctx for k in ("rupee", "rs", "inr", "amount", "invest", "$", "₹")):
                    score += 4
                if re.match(r"20\d{2}", token):
                    score -= 5
                candidates.append((score, token, ctx))
            if candidates:
                candidates.sort(key=lambda x: x[0], reverse=True)
                best_score, best_token, best_ctx = candidates[0]
                if best_score > 0:
                    try:
                        amount = float(best_token.replace(",", ""))
                    except Exception:
                        amount = None
                else:
                    amount = None

        # date
        m3 = re.search(r"(\d{4}-\d{2}-\d{2})", user_text)
        if m3:
            date = m3.group(1)
        else:
            m4 = re.search(r"on\s+([A-Za-z]{3,9}\s+\d{1,2}(?:,\s*\d{4})?)", user_text)
            if m4:
                date = m4.group(1)

        # client
        m_client = re.search(r"(?:client|for)\s+([A-Z][a-zA-Z]{1,30})", user_text)
        if m_client:
            client = m_client.group(1)
        else:
            m_cap = re.search(r"\b([A-Z][a-z]{1,30})\b", user_text)
            if m_cap:
                client = m_cap.group(1)

        return {"clientName": client, "fundNumber": fund, "dollarAmount": amount, "asOfDate": date}

    # parse node
    def parse_node(state: OrderAgentState) -> Dict[str, Any]:
        user_input = state["user_input"]
        parsed = parse_user_input(user_input)

        # LLM fallback if fields missing
        if (parsed["fundNumber"] is None or parsed["dollarAmount"] is None or parsed["clientName"] is None) and router_model:
            system_prompt = (
                "Extract from the user's message exactly JSON with these keys (use null for missing):\n"
                '{ "clientName": <string|null>, "fundNumber": <number|null>, "dollarAmount": <number|null>, "asOfDate": <string|null> }\n'
                "Return JSON only, no other text."
            )
            prompt = system_prompt + "\n\nUser: " + user_input
            try:
                text = llm_invoke_sync(router_model, prompt)
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    start = text.find("{")
                    end = text.rfind("}") + 1
                    if start != -1 and end > start:
                        try:
                            data = json.loads(text[start:end])
                        except Exception:
                            data = {}
                    else:
                        data = {}
                clientName = data.get("clientName", parsed["clientName"])
                fundNumber = data.get("fundNumber", parsed["fundNumber"])
                dollarAmount = data.get("dollarAmount", parsed["dollarAmount"])
                asOfDate = data.get("asOfDate", parsed["asOfDate"])
                try:
                    if isinstance(fundNumber, str) and fundNumber.isdigit():
                        fundNumber = int(fundNumber)
                except Exception:
                    pass
                try:
                    if dollarAmount is not None:
                        dollarAmount = float(dollarAmount)
                except Exception:
                    pass
                parsed = {
                    "clientName": clientName,
                    "fundNumber": fundNumber,
                    "dollarAmount": dollarAmount,
                    "asOfDate": asOfDate
                }
            except Exception:
                pass

        ok = bool(parsed["clientName"] and parsed["fundNumber"] is not None and parsed["dollarAmount"] is not None)
        message = None
        if not ok:
            message = "Parsing incomplete — some fields missing. Provide JSON like {\"clientName\":\"Alice\",\"fundNumber\":101,\"dollarAmount\":15000.5,\"asOfDate\":\"2025-12-08\"}"

        # return state slice
        return {
            "clientName": parsed["clientName"],
            "fundNumber": parsed["fundNumber"],
            "dollarAmount": parsed["dollarAmount"],
            "asOfDate": parsed["asOfDate"],
            "parsed_ok": ok,
            "submit_result": None,
            "nav_result": None,
            "position_result": None,
            "message": message
        }

    # submit node
    def submit_node(state: OrderAgentState) -> Dict[str, Any]:
        clientName = state.get("clientName")
        fundNumber = state.get("fundNumber")
        dollarAmount = state.get("dollarAmount")
        asOfDate = state.get("asOfDate")
        if not (clientName and fundNumber is not None and dollarAmount is not None):
            return {"submit_result": None, "message": "Missing order fields; skipping submit."}

        # find a submit-like tool
        tool_obj = None
        for t in mcp_tools:
            n = getattr(t, "name", None) or getattr(t, "tool_name", None) or t.__class__.__name__
            if any(k in n.lower() for k in ("receive", "submit", "order")):
                tool_obj = t
                break
        if tool_obj is None:
            return {"submit_result": None, "message": "Submit tool (receiveOrder/submitOrder) not found on MCP."}

        payload = {
            "clientName": clientName,
            "fundNumber": fundNumber,
            "dollarAmount": dollarAmount
        }
        if asOfDate:
            payload["asOfDate"] = asOfDate

        try:
            tool_name = getattr(tool_obj, "name", None) or getattr(tool_obj, "tool_name", None) or tool_obj.__class__.__name__
            result = call_mcp_tool_sync(mcp_tools, tool_name, payload)
            # Extract text from LangChain message objects if needed
            text_result = extract_text_from_result(result)
            parsed_result = parse_json(text_result)
            return {"submit_result": parsed_result, "message": "Order submitted (mock)."}
        except Exception as e:
            tb = traceback.format_exc()
            return {"submit_result": None, "message": f"Submit failed: {e}\n{tb}"}

    # get_nav node
    def get_nav_node(state: OrderAgentState) -> Dict[str, Any]:
        src = state.get("submit_result") or {}
        fund = None
        if isinstance(src, dict):
            fund = src.get("fundNumber") or state.get("fundNumber")
        else:
            fund = state.get("fundNumber")

        payload = {"fundNumber": fund}
        if state.get("asOfDate"):
            payload["asOfDate"] = state.get("asOfDate")

        tool_obj = None
        for t in mcp_tools:
            n = getattr(t, "name", None) or getattr(t, "tool_name", None) or t.__class__.__name__
            if any(k in n.lower() for k in ("nav", "getnav", "navfile")):
                tool_obj = t
                break
        if tool_obj is None:
            return {"nav_result": None, "message": "getNav tool not found."}

        try:
            tool_name = getattr(tool_obj, "name", None) or getattr(tool_obj, "tool_name", None) or tool_obj.__class__.__name__
            result = call_mcp_tool_sync(mcp_tools, tool_name, payload)
            # Extract text from LangChain message objects if needed
            text_result = extract_text_from_result(result)
            parsed = parse_json(text_result)
            return {"nav_result": parsed, "message": "Nav fetched."}
        except Exception as e:
            tb = traceback.format_exc()
            return {"nav_result": None, "message": f"getNav failed: {e}\n{tb}"}

    # calculate node
    def calculate_node(state: OrderAgentState) -> Dict[str, Any]:
        submitted = state.get("submit_result")
        nav = state.get("nav_result")
        if not submitted:
            return {"position_result": None, "message": "No submitted order; skipping calculate."}
        if not nav:
            nav_res = get_nav_node(state)
            nav = nav_res.get("nav_result")

        # Helper to normalize to dict
        def normalize_to_dict(obj: Any) -> dict:
            """Convert various formats to a dict."""
            if obj is None:
                return {}
            if isinstance(obj, dict):
                # Check if it's a LangChain message object
                if "type" in obj or ("text" in obj and "content" not in obj):
                    obj = extract_text_from_result(obj)
                    if isinstance(obj, str):
                        obj = parse_json(obj)
                return obj if isinstance(obj, dict) else {}
            if isinstance(obj, list):
                # Check if it's a LangChain message object list
                if len(obj) > 0 and isinstance(obj[0], dict) and "type" in obj[0]:
                    obj = extract_text_from_result(obj)
                    if isinstance(obj, str):
                        obj = parse_json(obj)
                return obj if isinstance(obj, dict) else {}
            if isinstance(obj, str):
                # Try JSON first
                parsed = parse_json(obj)
                if isinstance(parsed, dict):
                    return parsed
                # If JSON parsing failed, try Python literal eval (for single-quote dict strings)
                try:
                    parsed = ast.literal_eval(obj)
                    if isinstance(parsed, dict):
                        return parsed
                except:
                    pass
                # Last resort: try to extract and convert Python dict string to JSON
                try:
                    # Find dict-like content
                    start = obj.find("{")
                    end = obj.rfind("}") + 1
                    if start != -1 and end > start:
                        dict_str = obj[start:end]
                        # Use ast.literal_eval which safely evaluates Python literals
                        parsed = ast.literal_eval(dict_str)
                        if isinstance(parsed, dict):
                            return parsed
                except:
                    pass
            return {}

        submitted = normalize_to_dict(submitted)
        nav = normalize_to_dict(nav)

        if not submitted:
            return {"position_result": None, "message": "Invalid submit_result: could not parse as dict."}
        if not nav:
            return {"position_result": None, "message": "Invalid nav_result: could not parse as dict."}

        payload = {"order": submitted, "nav": nav}
        print("DEBUG: calling calculate with payload:", json.dumps(payload, default=str)[:2000])

        tool_obj = None
        for t in mcp_tools:
            n = getattr(t, "name", None) or getattr(t, "tool_name", None) or t.__class__.__name__
            if any(k in n.lower() for k in ("calculate", "calc", "position")):
                tool_obj = t
                break
        if tool_obj is None:
            return {"position_result": None, "message": "calculate tool not found."}

        try:
            tool_name = getattr(tool_obj, "name", None) or getattr(tool_obj, "tool_name", None) or tool_obj.__class__.__name__
            result = call_mcp_tool_sync(mcp_tools, tool_name, payload)
            parsed = parse_json(result)
            return {"position_result": parsed, "message": "Position calculated."}
        except Exception as e:
            tb = traceback.format_exc()
            return {"position_result": None, "message": f"calculate failed: {e}\n{tb}"}

    # Build graph
    graph = StateGraph(OrderAgentState)
    graph.add_node("parse_node", parse_node)
    graph.add_node("submit_node", submit_node)
    graph.add_node("get_nav_node", get_nav_node)
    graph.add_node("calculate_node", calculate_node)

    graph.add_edge(START, "parse_node")
    graph.add_edge("parse_node", "submit_node")
    graph.add_edge("submit_node", "get_nav_node")
    graph.add_edge("get_nav_node", "calculate_node")
    graph.add_edge("calculate_node", END)

    agent = graph.compile()
    agent = graph.compile()
    return agent

# Scope validation for Position Agent
ALLOWED_SCOPES = ["MutualFunds", "Assets", "Wealth"]

def extract_scope_from_request(request: str) -> tuple:
    """Extract scope and actual request from formatted payload.
    Format: "SCOPE:{scope}|ROLES:{roles}|REQUEST:{actual_request}"
    Returns: (scope, actual_request)
    """
    if request.startswith("SCOPE:"):
        try:
            parts = request.split("|REQUEST:", 1)
            if len(parts) == 2:
                scope_part = parts[0].replace("SCOPE:", "")
                # Extract just the scope (before |ROLES: if present)
                if "|ROLES:" in scope_part:
                    scope = scope_part.split("|ROLES:")[0]
                else:
                    scope = scope_part
                actual_request = parts[1]
                return scope, actual_request
        except:
            pass
    # If not formatted, return unauthorized and original request
    return "unauthorized", request

def validate_scope(scope: str) -> bool:
    """Check if scope is allowed for Position Agent."""
    return scope in ALLOWED_SCOPES

# Supervisor entry point
def process_request(request: str) -> str:
    """Entry point for Supervisor Agent."""
    # Extract scope from request
    scope, actual_request = extract_scope_from_request(request)
    
    # Validate scope
    if not validate_scope(scope):
        return f"Unauthorized: Scope '{scope}' is not allowed for Position Agent. Required scopes: {', '.join(ALLOWED_SCOPES)}"

    mcp_tools = []
    try:
        # Wrap MCP client creation with a timeout to prevent hang if backend is offline
        client = build_mcp_client()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Use wait_for to implement timeout
        async def get_tools_safe():
            return await client.get_tools()
            
        try:
            mcp_tools = loop.run_until_complete(asyncio.wait_for(get_tools_safe(), timeout=2.0))
        except asyncio.TimeoutError:
            print("Warning: MCP tool retrieval timed out (backend likely offline). Proceeding with no tools.")
        finally:
            loop.close()
    except Exception as e:
        print(f"Warning initializing MCP tools: {e}")
        # Proceed with empty toolkit rather than crashing/hanging


    bedrock_model_id = os.getenv("BEDROCK_MODEL_ID", "us.amazon.nova-pro-v1:0")
    try:
        router_model = ChatBedrock(
            model_id=bedrock_model_id,
            region_name=os.environ.get("AWS_REGION", "us-east-2"),
        )
    except Exception as e:
        return f"Error initializing Bedrock model: {e}"

    agent = build_order_graph(router_model, mcp_tools)
    
    init_state: OrderAgentState = {
        "user_input": actual_request,  # Use the actual request without scope prefix
        "clientName": None,
        "fundNumber": None,
        "dollarAmount": None,
        "asOfDate": None,
        "parsed_ok": False,
        "submit_result": None,
        "nav_result": None,
        "position_result": None,
        "message": None
    }
    
    # If the request is JSON, try to parse it
    if request.strip().startswith("{"):
        try:
            j = json.loads(request)
            init_state.update(j)
        except Exception:
            pass

    try:
        final_state = agent.invoke(init_state)
        
        parts = []
        if final_state.get("message"):
            parts.append(f"Status: {final_state['message']}")
            
        if final_state.get("submit_result"):
             parts.append(f"Submit Result: {json.dumps(final_state['submit_result'])}")
             
        if final_state.get("position_result"):
             parts.append(f"Position Result: {json.dumps(final_state['position_result'])}")

        return "\n".join(parts) if parts else "Processed request (no details returned)."
    except Exception as e:
        return f"Agent execution error: {traceback.format_exc()}"
    finally:
        try:
            loop.close()
        except:
            pass


# Top-Level Tool Wrappers for specific capabilities

def _get_mcp_tool_by_keyword(client, keywords):
    """Helper to find a tool by keyword safely."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def get_tools_safe():
            return await client.get_tools()

        mcp_tools = []
        try:
            mcp_tools = loop.run_until_complete(asyncio.wait_for(get_tools_safe(), timeout=2.0))
        except asyncio.TimeoutError:
            pass # Return empty list
            
        loop.close()
        
        for t in mcp_tools:
            n = getattr(t, "name", None) or getattr(t, "tool_name", None) or t.__class__.__name__
            if any(k in n.lower() for k in keywords):
                return t, mcp_tools
        return None, mcp_tools
    except Exception:
        return None, []

def submit_order(clientName: str, fundNumber: int, dollarAmount: float, asOfDate: str = None) -> str:
    """Submits an order directly."""
    try:
        client = build_mcp_client()
        payload = {
            "clientName": clientName,
            "fundNumber": fundNumber,
            "dollarAmount": dollarAmount
        }
        if asOfDate:
            payload["asOfDate"] = asOfDate
            
        tool_obj, mcp_tools = _get_mcp_tool_by_keyword(client, ("receive", "submit", "order"))
        if not tool_obj:
            return "Error: Submit tool not found or backend offline."
            
        tool_name = getattr(tool_obj, "name", None) or getattr(tool_obj, "tool_name", None) or tool_obj.__class__.__name__
        result = call_mcp_tool_sync(mcp_tools, tool_name, payload)
        return extract_text_from_result(result)
    except Exception as e:
        return f"Error submitting order: {e}"

def get_nav(fundNumber: int, asOfDate: str = None) -> str:
    """Gets NAV directly."""
    try:
        client = build_mcp_client()
        payload = {"fundNumber": fundNumber}
        if asOfDate:
            payload["asOfDate"] = asOfDate
            
        tool_obj, mcp_tools = _get_mcp_tool_by_keyword(client, ("nav", "getnav"))
        if not tool_obj:
            return "Error: NAV tool not found or backend offline."
            
        tool_name = getattr(tool_obj, "name", None) or getattr(tool_obj, "tool_name", None) or tool_obj.__class__.__name__
        result = call_mcp_tool_sync(mcp_tools, tool_name, payload)
        return extract_text_from_result(result)
    except Exception as e:
        return f"Error getting NAV: {e}"

def calculate_position(order_json: str, nav_json: str) -> str:
    """Calculates position directly."""
    try:
        client = build_mcp_client()
        try:
            order = parse_json(order_json)
            nav = parse_json(nav_json)
        except:
             return "Error: Invalid JSON input for order or nav"

        payload = {"order": order, "nav": nav}
        
        tool_obj, mcp_tools = _get_mcp_tool_by_keyword(client, ("calculate", "calc", "position"))
        if not tool_obj:
            return "Error: Calculate tool not found or backend offline."
            
        tool_name = getattr(tool_obj, "name", None) or getattr(tool_obj, "tool_name", None) or tool_obj.__class__.__name__
        result = call_mcp_tool_sync(mcp_tools, tool_name, payload)
        return extract_text_from_result(result)
    except Exception as e:
        return f"Error calculating position: {e}"


# CLI runner
def main():
    client = build_mcp_client()
    try:
        mcp_tools = asyncio.run(client.get_tools())
    except Exception as e:
        print("Failed to retrieve MCP tools:", e)
        print(traceback.format_exc())
        return

    print("Available MCP tools:", [getattr(t, "name", None) or getattr(t, "tool_name", None) or t.__class__.__name__ for t in mcp_tools])

    bedrock_model_id = os.getenv("BEDROCK_MODEL_ID")
    router_model = None
    if bedrock_model_id:
        try:
            router_model = ChatBedrock(
                model_id=bedrock_model_id,
                region_name=os.environ.get("AWS_REGION", "us-east-2"),
            )
        except Exception as e:
            print("Failed to instantiate ChatBedrock router model:", e)
            router_model = None

    agent = build_order_graph(router_model, mcp_tools)
    print("Order LangGraph agent ready. Type 'exit' to quit.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            print("Bye!")
            break

        init_state: OrderAgentState = {
            "user_input": user_input,
            "clientName": None,
            "fundNumber": None,
            "dollarAmount": None,
            "asOfDate": None,
            "parsed_ok": False,
            "submit_result": None,
            "nav_result": None,
            "position_result": None,
            "message": None
        }

        if user_input.strip().startswith("{"):
            try:
                j = json.loads(user_input)
                init_state.update(j)
            except Exception:
                pass

        try:
            final_state = agent.invoke(init_state)
        except Exception as e:
            print("Agent execution error:", e)
            print(traceback.format_exc())
            continue

        print("\nAgent run summary")
        print("Parsed clientName:", final_state.get("clientName"))
        print("Parsed fundNumber:", final_state.get("fundNumber"))
        print("Parsed dollarAmount:", final_state.get("dollarAmount"))
        print("Parsed asOfDate:", final_state.get("asOfDate"))
        print("Parsed OK:", final_state.get("parsed_ok"))
        print("Message:", final_state.get("message"))

        print("\nsubmit_result:")
        try:
            print(json.dumps(final_state.get("submit_result"), indent=2, default=str))
        except Exception:
            print(final_state.get("submit_result"))

        print("\nnav_result:")
        try:
            print(json.dumps(final_state.get("nav_result"), indent=2, default=str))
        except Exception:
            print(final_state.get("nav_result"))

        print("\nposition_result:")
        try:
            print(json.dumps(final_state.get("position_result"), indent=2, default=str))
        except Exception:
            print(final_state.get("position_result"))
        print("\n---\n")

if __name__ == "__main__":
    main()
