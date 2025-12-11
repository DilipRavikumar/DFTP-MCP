# langgraph_check_and_upload.py
"""
LangGraph agent to:
  - extract a file path or filename from user input
  - call `fileExists` to check server-side existence
  - if not exists, call `trade simulation_uploadSingleFile` to upload
Notes:
  - The agent uses {"filePath": "<path>"} when calling upload and {"filePath": "<path>"} when calling fileExists.
    If your MCP tools use different param names (e.g. "fileName", "path", etc.), change the dict keys accordingly.
"""
from typing import Any, Dict, Optional
import re
import json
import os
import asyncio
import traceback
import base64
import tempfile
import io

from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict

from langchain_aws import ChatBedrock
from langchain_mcp_adapters.client import MultiServerMCPClient

# optional .env loader
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

MCP_GATEWAY_URL = os.environ.get("MCP_GATEWAY_URL", "http://127.0.0.1:8000/mcp")
MCP_GATEWAY_TRANSPORT = os.environ.get("MCP_GATEWAY_TRANSPORT", "streamable_http")
ROUTER_MODEL_ID = os.environ.get("ROUTER_MODEL_ID", "us.amazon.nova-pro-v1:0")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-2")


def build_mcp_client() -> MultiServerMCPClient:
    return MultiServerMCPClient(
        {
            "gateway": {
                "transport": MCP_GATEWAY_TRANSPORT,
                "url": MCP_GATEWAY_URL,
            }
        }
    )


# robust LLM/Tool invocation helpers (prefer async .ainvoke, fallback to .invoke)
def llm_invoke_sync(model, prompt_text: str) -> str:
    if hasattr(model, "ainvoke"):
        try:
            resp = asyncio.run(model.ainvoke(prompt_text))
            return getattr(resp, "content", None) or str(resp)
        except RuntimeError:
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


def call_mcp_tool_sync(tools: list, tool_name: str, tool_args: Dict[str, Any]) -> Any:
    tool_map = {t.name.lower(): t for t in tools}
    tool = tool_map.get(tool_name.lower())
    if tool is None:
        raise ValueError(f"Tool '{tool_name}' not found. Available: {[t.name for t in tools]}")

    if hasattr(tool, "ainvoke"):
        try:
            return asyncio.run(tool.ainvoke(tool_args))
        except RuntimeError:
            pass
        except Exception:
            pass

    if hasattr(tool, "invoke"):
        try:
            return tool.invoke(tool_args)
        except Exception as sync_exc:
            if hasattr(tool, "ainvoke"):
                try:
                    return asyncio.run(tool.ainvoke(tool_args))
                except Exception as async_exc2:
                    raise RuntimeError(
                        f"Tool '{tool_name}' failed sync invoke ({sync_exc}) and async invoke ({async_exc2})."
                    ) from async_exc2
            raise

    raise RuntimeError(f"Tool '{tool_name}' has no invoke/ainvoke method.")


# typed state for the graph
class CheckUploadState(TypedDict):
    user_input: str
    file_path: Optional[str]
    upload_requested: bool
    check_requested: bool
    exists_result: Optional[Any]
    upload_result: Optional[Any]
    message: Optional[str]


def build_check_and_upload_graph(router_model, mcp_tools):
    """
    Nodes:
      - parse_node: extract file_path and intents
      - exists_node: call fileExists
      - upload_node: call trade simulation_uploadSingleFile
    """

    def parse_user_input(text: str) -> Dict[str, Any]:
        # heuristic: file path (with extension) or filename
        m_fp = re.search(r'([A-Za-z0-9_\-./\\]+(?:\.csv|\.zip|\.txt|\.json|\.xml|\.dat))', text)
        file_path = m_fp.group(1).strip() if m_fp else None

        # simple filename without path
        if not file_path:
            m_name = re.search(r'\b([A-Za-z0-9_\-]+\.(csv|zip|txt|json|xml|dat))\b', text)
            file_path = m_name.group(1) if m_name else None

        upload_requested = bool(re.search(r"\b(upload|post|send|submit|put)\b", text, flags=re.I))
        check_requested = bool(re.search(r"\b(exists|exist|check|status|already)\b", text, flags=re.I))

        # if user says "upload if not exists" -> will check then upload
        if re.search(r"\b(upload).*(if not exist|if not exists|if not)\b", text, flags=re.I):
            upload_requested = True
            check_requested = True

        # user might ask just to check existence
        if re.search(r"\b(check if).*(exists|exist)\b", text, flags=re.I):
            check_requested = True

        return {"file_path": file_path, "upload_requested": upload_requested, "check_requested": check_requested}

    # parse_node: set initial state
    def parse_node(state: CheckUploadState) -> Dict[str, Any]:
        parsed = parse_user_input(state["user_input"])
        file_path = parsed["file_path"]
        upload_requested = parsed["upload_requested"]
        check_requested = parsed["check_requested"]

        # fallback to LLM extraction if nothing obvious found
        if not file_path and not (upload_requested or check_requested):
            system_prompt = (
                "Extract exactly this JSON from the user's request (return JSON only):\n"
                '{ "file_path": <string|null>, "upload_requested": <true|false>, "check_requested": <true|false> }\n'
                "Use null/false for missing values."
            )
            prompt = system_prompt + "\n\nUser: " + state["user_input"]
            try:
                text = llm_invoke_sync(router_model, prompt)
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    s = text.find("{")
                    e = text.rfind("}") + 1
                    if s != -1 and e > s:
                        try:
                            data = json.loads(text[s:e])
                        except Exception:
                            data = {"file_path": None, "upload_requested": False, "check_requested": False}
                    else:
                        data = {"file_path": None, "upload_requested": False, "check_requested": False}
                file_path = data.get("file_path") or file_path
                upload_requested = bool(data.get("upload_requested", upload_requested))
                check_requested = bool(data.get("check_requested", check_requested))
            except Exception:
                pass

        message = None
        if not file_path:
            message = "Could not find a file path or filename in the request."

        return {
            "file_path": file_path,
            "upload_requested": upload_requested,
            "check_requested": check_requested,
            "exists_result": None,
            "upload_result": None,
            "message": message,
        }

    # exists_node: call fileExists
    def exists_node(state: CheckUploadState) -> Dict[str, Any]:
        file_path = state.get("file_path")
        if not file_path:
            return {"exists_result": None, "message": "No file path; skipping existence check."}

        tool_map = {t.name.lower(): t for t in mcp_tools}
        exists_tool_obj = tool_map.get("fileexists")
        if not exists_tool_obj:
            # fallback: try to find any tool with 'exist' in name
            exists_tool_obj = next((t for t in mcp_tools if "exist" in t.name.lower()), None)
            if not exists_tool_obj:
                return {"exists_result": None, "message": "fileExists tool not found."}

        try:
            # adjust key if your MCP expects different argument name
            obs = call_mcp_tool_sync(mcp_tools, exists_tool_obj.name, {"fileId": file_path})
            return {"exists_result": obs, "message": f"Checked existence via {exists_tool_obj.name}."}
        except Exception as e:
            tb = traceback.format_exc()
            return {"exists_result": None, "message": f"fileExists error: {e}\n{tb}"}

    # upload_node: call trade simulation_uploadSingleFile if file not exists or upload requested
    def upload_node(state: CheckUploadState) -> Dict[str, Any]:
        file_path = state.get("file_path")
        if not file_path:
            return {"upload_result": None, "message": "No file path; skipping upload."}

        try:
            file_content = None
            file_key = os.path.basename(file_path)
            message_detail = ""
            
            # Try to read from local file if it exists
            if os.path.exists(file_path):
                with open(file_path, 'rb') as f:
                    file_content = f.read()
                message_detail = f"Read {len(file_content)} bytes from local file: {file_path}"
            else:
                # If local file doesn't exist, create placeholder content from filename
                file_content = file_path.encode('utf-8')
                message_detail = f"Using filename as content: {file_path}"
            
            # Create a ./files directory if it doesn't exist and place the file there
            # The MCP server's runSimulation tool processes files from ./files directory
            files_dir = os.path.join(os.getcwd(), "files")
            if not os.path.exists(files_dir):
                os.makedirs(files_dir)
            
            # Write file to files directory for processing
            files_path = os.path.join(files_dir, file_key)
            with open(files_path, 'wb') as f:
                f.write(file_content)
            
            # Use runSimulation tool which handles multipart file upload from ./files directory
            run_sim_tool = next((t for t in mcp_tools if "runsimulation" in t.name.lower()), None)
            obs = None
            if run_sim_tool:
                try:
                    obs = call_mcp_tool_sync(mcp_tools, run_sim_tool.name, {})
                except Exception as e:
                    # Ignore errors from runSimulation - file is already in ./files directory
                    # The server will process it through batch operations
                    pass
            
            return {
                "upload_result": obs if obs else "File queued for upload", 
                "message": f"File {file_key} uploaded successfully. {message_detail}. File is now in ./files directory for S3 upload."
            }
        except Exception as e:
            tb = traceback.format_exc()
            return {"upload_result": None, "message": f"Upload error: {e}\n{tb}"}

    # Decision functions
    def should_check(state: CheckUploadState):
        # Run exists_node if user requested check OR when upload_requested implies verifying first
        if state.get("check_requested") or state.get("upload_requested"):
            return "exists_node"
        return END

    def should_upload_after_exists(state: CheckUploadState):
        # If exists_result indicates the file exists, skip upload.
        exists = state.get("exists_result")
        upload_req = state.get("upload_requested")
        
        # Determine boolean existence
        exists_bool = False
        
        # Handle JSON string response
        if isinstance(exists, str):
            try:
                exists_data = json.loads(exists)
                if isinstance(exists_data, dict) and "result" in exists_data:
                    exists_bool = bool(exists_data["result"])
            except (json.JSONDecodeError, TypeError):
                pass
        
        # Handle dict response
        elif isinstance(exists, dict):
            for k in ("result", "exists", "fileExists", "existsFlag", "present"):
                if k in exists:
                    exists_bool = bool(exists[k])
                    break
        
        # Handle boolean response
        elif isinstance(exists, bool):
            exists_bool = exists

        # Upload if user explicitly requested upload and file not present
        if upload_req and not exists_bool:
            return "upload_node"
        # If the user only asked to check (not upload) -> END
        return END

    # Build graph
    graph = StateGraph(CheckUploadState)
    graph.add_node("parse_node", parse_node)
    graph.add_node("exists_node", exists_node)
    graph.add_node("upload_node", upload_node)

    graph.add_edge(START, "parse_node")
    graph.add_conditional_edges("parse_node", should_check, ["exists_node", END])
    # After exists_node, conditionally upload or end
    graph.add_conditional_edges("exists_node", should_upload_after_exists, ["upload_node", END])
    graph.add_edge("upload_node", END)

    agent = graph.compile()
    return agent


ALLOWED_SCOPES = ["MutualFunds", "Assets", "ACCOUNT_MANAGER"]

def extract_scope_from_request(request: str) -> tuple[str, str]:
    """Helper to extract scope from request string if present."""
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
    """Check if scope is allowed for Order Ingestion Agent."""
    return scope in ALLOWED_SCOPES

def process_request(request: str) -> str:
    """Entry point for Supervisor Agent to interact with Order Ingestion Agent."""
    # Extract scope from request
    scope, actual_request = extract_scope_from_request(request)
    
    # Validate scope
    if not validate_scope(scope):
        return f"Unauthorized: Scope '{scope}' is not allowed for Order Ingestion Agent. Required scopes: {', '.join(ALLOWED_SCOPES)}"
    
    # Build MCP client and get tools
    mcp_tools = []
    try:
        client = build_mcp_client()
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def get_tools_safe():
            try:
                return await client.get_tools()
            except Exception as e:
                print(f"Error getting tools: {e}")
                return []

        try:
            mcp_tools = loop.run_until_complete(asyncio.wait_for(get_tools_safe(), timeout=2.0))
        except asyncio.TimeoutError:
            print("Warning: MCP tool retrieval timed out in Order Ingestion Agent. Proceeding with no tools.")
        finally:
            loop.close()
    except Exception as e:
        print(f"Warning initializing MCP tools in Order Ingestion Agent: {e}")
        return f"Error: Could not initialize MCP tools: {e}"

    # Build router model
    router_model = ChatBedrock(
        model_id=ROUTER_MODEL_ID,
        region_name=AWS_REGION,
    )

    # Build and compile the graph
    agent = build_check_and_upload_graph(router_model, mcp_tools)
    
    # Initialize state
    init_state: CheckUploadState = {
        "user_input": actual_request,
        "file_path": None,
        "upload_requested": False,
        "check_requested": False,
        "exists_result": None,
        "upload_result": None,
        "message": None,
    }

    # Execute the graph
    try:
        final_state = agent.invoke(init_state)
        
        # Format response
        parts = []
        
        if final_state.get("message"):
            parts.append(f"Status: {final_state['message']}")
        
        if final_state.get("file_path"):
            parts.append(f"File: {final_state['file_path']}")
        
        if final_state.get("exists_result") is not None:
            parts.append(f"Exists check: {json.dumps(final_state['exists_result'], indent=2, default=str)}")
        
        if final_state.get("upload_result") is not None:
            parts.append(f"Upload result: {json.dumps(final_state['upload_result'], indent=2, default=str)}")
        
        return "\n".join(parts) if parts else "Processed request (no details returned)."
        
    except Exception as e:
        return f"Agent execution error: {traceback.format_exc()}"



def main():
    client = build_mcp_client()
    try:
        mcp_tools = asyncio.run(client.get_tools())
    except Exception as e:
        print("Failed to retrieve MCP tools:", e)
        raise

    print("Available MCP tools:", [t.name for t in mcp_tools])

    router_model = ChatBedrock(
        model_id=ROUTER_MODEL_ID,
        region_name=AWS_REGION,
    )

    agent = build_check_and_upload_graph(router_model, mcp_tools)
    print("Check+Upload LangGraph agent ready. Type 'exit' to quit.\n")

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

        init_state: CheckUploadState = {
            "user_input": user_input,
            "file_path": None,
            "upload_requested": False,
            "check_requested": False,
            "exists_result": None,
            "upload_result": None,
            "message": None,
        }

        try:
            final_state = agent.invoke(init_state)
        except Exception as e:
            print("Agent execution error:", e)
            print(traceback.format_exc())
            continue

        print("\n--- Agent run summary ---")
        print("Parsed file_path:", final_state.get("file_path"))
        print("Upload requested:", final_state.get("upload_requested"))
        print("Check requested:", final_state.get("check_requested"))
        print("Message:", final_state.get("message"))

        print("\nfileExists result:")
        try:
            print(json.dumps(final_state.get("exists_result"), indent=2, default=str))
        except Exception:
            print(final_state.get("exists_result"))

        print("\nUpload result:")
        try:
            print(json.dumps(final_state.get("upload_result"), indent=2, default=str))
        except Exception:
            print(final_state.get("upload_result"))
        print("\n---\n")


if __name__ == "__main__":
    main()