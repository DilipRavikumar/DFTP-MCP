#!/usr/bin/env python3
"""
langgraph_order_agent_fixed.py

Positions orchestration agent (full file) with fixes:
 - JSON-decode MCP tool responses when they're JSON strings
 - Defensive logging of payloads sent to calculate
 - Slightly more defensive amount parsing (reuse previous improved parser)
"""

from typing import Any, Dict, Optional
import re
import json
import os
import asyncio
import traceback

from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict

from langchain_aws import ChatBedrock
from langchain_mcp_adapters.client import MultiServerMCPClient


# MCP client
def build_mcp_client() -> MultiServerMCPClient:
    mcp_url = os.getenv("MCP_URL", "http://127.0.0.1:8000/mcp")
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


def parse_json(obj: Any) -> Any:
    """If obj is a string that looks like JSON, parse and return the object. Otherwise return obj."""
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
            parsed_result = parse_json(result)
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
            parsed = parse_json(result)
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

        if isinstance(submitted, str):
            submitted = parse_json(submitted)
        if isinstance(nav, str):
            nav = parse_json(nav)

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
    return agent

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
