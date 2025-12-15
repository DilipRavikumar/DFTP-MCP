from typing import Any, Dict, Optional
import json
import os
import asyncio
import traceback
import re

from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict

from langchain_aws import ChatBedrock
from langchain_mcp_adapters.client import MultiServerMCPClient

from langchain_core.tools.base import ToolException

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass




MCP_GATEWAY_URL = "http://127.0.0.1:8000/mcp"

MCP_GATEWAY_TRANSPORT = os.environ.get("MCP_GATEWAY_TRANSPORT", "streamable_http")
ROUTER_MODEL_ID = os.environ.get("ROUTER_MODEL_ID", "us.amazon.nova-pro-v1:0")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-2")

_mcp_client = None





def build_mcp_client() -> MultiServerMCPClient:
    return MultiServerMCPClient(
        {
            "gateway": {
                "transport": MCP_GATEWAY_TRANSPORT,
                "url": MCP_GATEWAY_URL,
            }
        }
    )


def _run_coroutine_in_new_loop(coro):
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        try:
            asyncio.set_event_loop(None)
        except Exception:
            pass
        try:
            loop.close()
        except Exception:
            pass


def llm_invoke_sync(model, prompt_text: str) -> str:
    if hasattr(model, "ainvoke"):
        try:
            resp = asyncio.run(model.ainvoke(prompt_text))
            return getattr(resp, "content", None) or str(resp)
        except RuntimeError:
            try:
                resp = _run_coroutine_in_new_loop(model.ainvoke(prompt_text))
                return getattr(resp, "content", None) or str(resp)
            except Exception:
                pass
        except Exception:
            try:
                if hasattr(model, "invoke"):
                    resp = model.invoke(prompt_text)
                    return getattr(resp, "content", None) or str(resp)
            except Exception:
                pass

    if hasattr(model, "invoke"):
        resp = model.invoke(prompt_text)
        return getattr(resp, "content", None) or str(resp)

    raise RuntimeError("Model has neither invoke nor ainvoke")


def call_mcp_tool_raw(tools: list, tool_name: str, tool_args: Dict[str, Any]) -> Any:
    tool_map = {t.name.lower(): t for t in tools}
    tool = tool_map.get(tool_name.lower())
    if tool is None:
        raise ValueError(f"Tool '{tool_name}' not found. Available: {[t.name for t in tools]}")

    try:
        try:
            result = asyncio.run(tool.ainvoke(tool_args))
            return _clean_and_parse_tool_result(result)
        except RuntimeError:
            result = _run_coroutine_in_new_loop(tool.ainvoke(tool_args))
            return _clean_and_parse_tool_result(result)
    except ToolException as te:
        error_msg = str(te)
        
        if "Got list:" in error_msg:
            try:
                start_idx = error_msg.find("Got list: ") + len("Got list: ")
                end_idx = error_msg.find(". Tools should wrap")
                if end_idx == -1:
                    end_idx = len(error_msg)
                list_str = error_msg[start_idx:end_idx]
                
                import ast
                data = ast.literal_eval(list_str)
                return _remove_none_values(data)
            except Exception as e:
                pass  
        
        return {
            "error": "Tool execution error",
            "details": error_msg,
            "tool": tool_name,
            "arguments": tool_args
        }
    except Exception as e:
        error_msg = str(e)
        
        return {
            "error": "Tool execution error",
            "details": error_msg,
            "tool": tool_name,
            "arguments": tool_args
        }


def _clean_and_parse_tool_result(result: Any) -> Any:
    if isinstance(result, dict):
        return _remove_none_values(result)
    
    if isinstance(result, str):
        try:
            parsed = json.loads(result)
            return _remove_none_values(parsed)
        except json.JSONDecodeError:
            return result
    
    return result


def _remove_none_values(data: Any) -> Any:
    if isinstance(data, dict):
        return {k: _remove_none_values(v) for k, v in data.items() if v is not None}
    elif isinstance(data, list):
        return [_remove_none_values(item) for item in data if item is not None]
    else:
        return data


class RouterState(TypedDict):
    user_input: str
    tool_name: Optional[str]
    arguments: Dict[str, Any]
    result: Optional[Any]
    message: Optional[str]


def build_langgraph_router_graph(router_model, mcp_tools):
    def llm_node(state: RouterState) -> Dict[str, Any]:
        user_input = state["user_input"]

        tools_desc = "\n".join(f"- {t.name}: {getattr(t, 'description', '') or ''}" for t in mcp_tools)
        system_prompt = (
            "You are a strict router assistant. The user gives a natural-language request "
            "that must map to exactly one MCP tool. Available tools:\n\n"
            f"{tools_desc}\n\n"
            "RETURN JSON ONLY with exactly these keys:\n"
            '  { "tool_name": <string|null>, "arguments": { ... } }\n\n'
            "If you cannot map the request to a single tool, respond with:\n"
            '  { "tool_name": null, "arguments": {} }\n'
            "Do NOT output text outside the JSON."
        )

        prompt_text = system_prompt + "\n\nUser request: " + user_input

        try:
            text = llm_invoke_sync(router_model, prompt_text)
        except Exception as e:
            return {
                "tool_name": None,
                "arguments": {},
                "result": None,
                "message": f"Router LLM error: {e}",
            }

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start != -1 and end > start:
                try:
                    data = json.loads(text[start:end])
                except Exception:
                    data = {"tool_name": None, "arguments": {}}
            else:
                data = {"tool_name": None, "arguments": {}}

        tool_name = data.get("tool_name")
        arguments = data.get("arguments", {}) or {}
        if not isinstance(arguments, dict):
            arguments = {}

        return {
            "tool_name": tool_name,
            "arguments": arguments,
            "result": None,
            "message": None,
        }

    def tool_node(state: RouterState) -> Dict[str, Any]:
        tool_name = state.get("tool_name")
        args = state.get("arguments") or {}

        if not tool_name:
            return {"result": None, "message": "No tool to call."}

        try:
            observation = call_mcp_tool_raw(mcp_tools, tool_name, args)
            if isinstance(observation, dict) and "validation_error_but_tool_executed" in str(observation.get("status", "")):
                return {"result": observation, "message": f"Tool '{tool_name}' executed (with validation warning)."}
            return {"result": observation, "message": f"Tool '{tool_name}' executed successfully."}
        except Exception as e:
            tb = traceback.format_exc()
            print(f"DEBUG: Tool execution error for {tool_name}: {e}")
            print(tb)
            return {"result": None, "message": f"Tool execution error: {e}"}

    def should_call_tool(state: RouterState):
        if state.get("tool_name"):
            return "tool_node"
        return END

    graph_builder = StateGraph(RouterState)
    graph_builder.add_node("llm_node", llm_node)
    graph_builder.add_node("tool_node", tool_node)

    graph_builder.add_edge(START, "llm_node")
    graph_builder.add_conditional_edges("llm_node", should_call_tool, ["tool_node", END])
    graph_builder.add_edge("tool_node", END)

    agent = graph_builder.compile()
    return agent


ALLOWED_SCOPES = ["MutualFunds", "Assets", "Wealth", "General", "ACCOUNT_MANAGER"]

def extract_scope_from_request(request: str) -> tuple[str, str]:
    scope = "unknown"
    actual_request = request
    
    if "SCOPE:" in request and "|REQUEST:" in request:
        try:
            parts = request.split("|")
            for part in parts:
                if part.startswith("SCOPE:"):
                    scope = part.replace("SCOPE:", "").strip()
                elif part.startswith("REQUEST:"):
                    actual_request = part.replace("REQUEST:", "").strip()
        except:
            pass
            
    return scope, actual_request

def validate_scope(scope: str) -> bool:
    return scope in ALLOWED_SCOPES

def process_request_v2(request: str) -> str:
    import logging
    import datetime
    
    log_file = os.path.join(os.path.dirname(__file__), "debug_process_request.log")
    logging.basicConfig(
        filename=log_file,
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    logging.info(f"=" * 80)
    logging.info(f"process_request_v2 called at {datetime.datetime.now()}")
    logging.info(f"Raw request: {request}")
    
    scope, actual_request = extract_scope_from_request(request)
    logging.info(f"Extracted scope: {scope}")
    logging.info(f"Actual request: {actual_request}")
    
    if not validate_scope(scope):
        msg = f"Unauthorized: Scope '{scope}' is not allowed for Order Details Agent. Required scopes: {', '.join(ALLOWED_SCOPES)}"
        logging.warning(msg)
        return msg
    
    global _mcp_client
    
    mcp_tools = []
    try:
        client = build_mcp_client()
        logging.info("MCP client created")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def get_tools_safe():
            try:
                return await client.get_tools()
            except Exception as e:
                logging.error(f"Error getting tools: {e}")
                print(f"Error getting tools: {e}")
                return []

        try:
            mcp_tools = loop.run_until_complete(asyncio.wait_for(get_tools_safe(), timeout=2.0))
            logging.info(f"Loaded {len(mcp_tools)} MCP tools: {[t.name for t in mcp_tools]}")
        except asyncio.TimeoutError:
            logging.warning("MCP tool retrieval timed out. Proceeding with no tools.")
            print("Warning: MCP tool retrieval timed out in Order Details Agent. Proceeding with no tools.")
        finally:
            loop.close()
    except Exception as e:
        logging.error(f"Exception initializing MCP tools: {e}")
        print(f"Warning initializing MCP tools in Order Details Agent: {e}")

    router_model = ChatBedrock(
        model_id=ROUTER_MODEL_ID,
        region_name=AWS_REGION,
    )
    logging.info("Router model created")

    agent = build_langgraph_router_graph(router_model, mcp_tools)
    logging.info("LangGraph agent compiled")
    
    init_state: RouterState = {
        "user_input": actual_request,
        "tool_name": None,
        "arguments": {},
        "result": None,
        "message": None,
    }
    logging.info(f"Initial state: {init_state}")

    try:
        final_state = agent.invoke(init_state)
        logging.info(f"Final state: {final_state}")
        
        parts = []
        
        if final_state.get("result"):
            result = final_state.get("result")
            logging.info(f"Got result: {result}")
            if isinstance(result, dict) and "error" in result:
                parts.append(f"Error: {result['error']}")
                if "details" in result:
                     parts.append(f"Details: {result['details']}")
            else:
                parts.append(f"Result: {json.dumps(result, indent=2)}")
        elif final_state.get("message"):
             logging.info(f"Got message instead of result: {final_state['message']}")
             parts.append(f"Status: {final_state['message']}")
        
        response = "\n".join(parts) if parts else "Processed request (no details returned)."
        logging.info(f"Returning response: {response}")
        return response
        
    except Exception as e:
        error_msg = f"Agent execution error: {traceback.format_exc()}"
        logging.error(error_msg)
        return error_msg


def process_request(request: str) -> str:
    print(f"[ORDER_DETAILS_AGENT] process_request called from {__file__}")
    return process_request_v2(request)


def main():
    global _mcp_client
    
    _mcp_client = build_mcp_client()
    client = _mcp_client
    try:
        mcp_tools = asyncio.run(client.get_tools())
    except Exception as e:
        print("Failed to get MCP tools:", e)
        raise

    
    print("=" * 70)
    print("Loaded MCP tools:", [t.name for t in mcp_tools])
    print("=" * 70)
    for t in mcp_tools:
        print("=== TOOL ===", t.name)
        print("  description:", getattr(t, "description", None))
        
        try:
            print("  input_schema:", getattr(t, "input_schema", None))
            print("  output_schema:", getattr(t, "output_schema", None))
        except Exception:
            pass
        print()

    router_model = ChatBedrock(
        model_id=ROUTER_MODEL_ID,
        region_name=AWS_REGION,
    )

    agent = build_langgraph_router_graph(router_model, mcp_tools)

    print("=" * 70)
    print("LangGraph router compiled. Type 'exit' to quit.")
    print("=" * 70)
    print()

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

        # Initialize state
        init_state: RouterState = {
            "user_input": user_input,
            "tool_name": None,
            "arguments": {},
            "result": None,
            "message": None,
        }

        try:
            final_state = agent.invoke(init_state)
        except Exception as e:
            print("Agent execution error:", e)
            print(traceback.format_exc())
            continue

        msg = final_state.get("message")
        res = final_state.get("result")

        print(f"\nRouter message: {msg}")
        print("Tool result:")
        try:
            print(json.dumps(res, indent=2, default=str))
        except Exception:
            print(res)
        print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    main()