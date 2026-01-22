import os
import json
import logging
import jwt
import uvicorn
import httpx
from dotenv import load_dotenv

load_dotenv()

from fastapi import (
    FastAPI,
    Request,
    UploadFile,
    File,
    Form,
    HTTPException,
)
from fastapi.responses import RedirectResponse, StreamingResponse
from pydantic import BaseModel  # Required for ChatRequest
from typing import Dict, Any, Optional, List
from contextlib import asynccontextmanager
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent))

from langchain_core.messages import HumanMessage
from src.router_agent.graph import create_router_graph
from langgraph.store.postgres import PostgresStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("APP_SERVER")

class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default"

@asynccontextmanager
async def lifespan(app: FastAPI):
    db_uri = os.getenv(
        "POSTGRES_URI",
        "postgresql://postgres:root@localhost:5433/mcp_agent",
    )

    store_cm = None
    try:
        logger.info("[BOOT] Initializing PostgresStore")
        store_cm = PostgresStore.from_conn_string(db_uri)
        store = store_cm.__enter__()

        graph = await create_router_graph(store=store)
        app.state.graph = graph

        logger.info("[BOOT] App ready")
        yield
    finally:
        if store_cm:
            store_cm.__exit__(None, None, None)
            logger.info("[SHUTDOWN] Store closed")


app = FastAPI(title="Unified Backend", lifespan=lifespan)

def extract_user_context(req: Request) -> Optional[Dict[str, Any]]:
    user_id = req.headers.get("X-User-Id")
    if user_id:
        roles_raw = req.headers.get("X-User-Roles", "")
        scope_raw = req.headers.get("X-User-Scope", "")
        return {
            "user_id": user_id,
            "username": req.headers.get("X-Username"),
            "roles": roles_raw.split(",") if roles_raw else [],
            "scope": scope_raw.split(" ") if scope_raw else [],
        }

    token = req.cookies.get("access_token")
    if not token:
        return None

    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        roles = payload.get("resource_access", {}).get("public-client", {}).get("roles", [])
        return {
            "user_id": payload.get("sub"),
            "username": payload.get("preferred_username"),
            "roles": roles,
            "scope": payload.get("scope", "").split(" "),
        }
    except Exception as e:
        logger.error("[AUTH] Token decode failed: %s", e)
        return None


@app.get("/api/auth/me")
async def me(req: Request):
    user = extract_user_context(req)
    if not user:
        return {"authenticated": False}
    return {"authenticated": True, **user}

async def stream_generator(input_message, thread_id, user_context, req):
    graph = req.app.state.graph
    input_state = {"messages": [HumanMessage(content=input_message)]}
    config = {"configurable": {"thread_id": thread_id, "user": user_context}}

    final_text = ""

    async for event in graph.astream_events(
        input_state, config=config, version="v1"
    ):
        if event["event"] == "on_chain_end":
            output = event["data"].get("output")

            if isinstance(output, dict) and "messages" in output:
                for msg in reversed(output["messages"]):
                    if msg.type == "ai":
                        content = msg.content

                        if isinstance(content, list):
                            text = ""
                            for block in content:
                                if (
                                    isinstance(block, dict)
                                    and block.get("type") == "text"
                                ):
                                    text += block.get("text", "")
                            final_text = text
                        else:
                            final_text = content
                        break

    if final_text:
        yield json.dumps({
            "type": "message",
            "content": final_text
        }) + "\n"



@app.post("/api/upload")
async def upload_file(
    req: Request,
    file: UploadFile = File(...),
    thread_id: str = Form(...),
    description: str = Form(""),
):
    """Handle file uploads, save locally, and trigger agent processing."""

    user_context = extract_user_context(req)


    if not user_context:
        logger.warning(
            "[UPLOAD] No user context extracted! Using DEV fallback with admin role"
        )
        user_context = {
            "user_id": "test_user",
            "username": "DevUser",
            "roles": ["admin"],
            "scope": [
                "mutual funds",
                "mcp-agent",
                "order-agent",
                "nav-agent",
                "router-agent",
            ],
        }
    else:
        logger.info(
            f"[UPLOAD] User context extracted: "
            f"user_id={user_context.get('user_id')}, "
            f"roles={user_context.get('roles')}"
        )

    try:
        upload_dir = Path("uploads")
        upload_dir.mkdir(exist_ok=True)


        file_path = upload_dir / file.filename


        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)


        logger.info(f"[UPLOAD] File saved to: {file_path.absolute()}")


    except Exception as e:
        logger.error(f"[UPLOAD] File save error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save file: {e}",
        )


    from langchain_core.messages import HumanMessage


    abs_path = str(file_path.absolute())
    msg_content = (
        f"I have uploaded a file named '{file.filename}'.\n"
        f"Description: {description}\n"
        f"The file is saved locally at: {abs_path}\n"
        f"Please process this file."
    )


    input_state = {
        "messages": [HumanMessage(content=msg_content)]
    }


    config = {
        "configurable": {
            "thread_id": thread_id,
            "user": user_context,
        }
    }


    try:
        result = await req.app.state.graph.ainvoke(
            input_state,
            config=config,
        )

        agent_response = "File processed."

        if "messages" in result and result["messages"]:
            for msg in reversed(result["messages"]):
                if msg.type == "ai":
                    agent_response = msg.content


                    if isinstance(agent_response, list):
                        text_content = ""
                        for block in agent_response:
                            if (
                                isinstance(block, dict)
                                and block.get("type") == "text"
                            ):
                                text_content += block.get("text", "")
                            elif isinstance(block, str):
                                text_content += block
                        agent_response = text_content
                    break


        return {"agent_response": agent_response}


    except Exception as e:
        logger.error(f"[UPLOAD] Agent processing error: {e}")
        return {
            "agent_response": f"Error during processing: {str(e)}"
        }


@app.post("/api/chat")
async def chat(request: ChatRequest, req: Request):
    """Chat endpoint – invokes LangGraph agent with auth + memory."""

    user_context = extract_user_context(req)

    if not user_context:
        logger.warning(
            "[CHAT] No user context extracted! Using DEV fallback with admin role"
        )
        user_context = {
            "user_id": "test_user",
            "roles": ["admin"],
            "scope": [
                "mcp-agent",
                "order-agent",
                "nav-agent",
                "router-agent",
                "mutual funds",
            ],
        }
    else:
        logger.info(
            f"[CHAT] User context extracted: "
            f"user_id={user_context.get('user_id')}, "
            f"roles={user_context.get('roles')}"
        )


    return StreamingResponse(
        stream_generator(
            request.message,
            request.thread_id,
            user_context,
            req,
        ),
        media_type="application/x-ndjson",
    )


if __name__ == "__main__":
    uvicorn.run(
        "app_server:app", 
        host="0.0.0.0", 
        port=8060, 
        reload=True
    )