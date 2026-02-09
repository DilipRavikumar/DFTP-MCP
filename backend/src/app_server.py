import json
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel  # Required for ChatRequest

sys.path.append(str(Path(__file__).parent.parent))
from langchain_core.messages import HumanMessage
from langgraph.store.postgres import PostgresStore
from langgraph.store.redis import RedisStore

from src.router_agent.graph import create_router_graph

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("APP_SERVER")

class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default"

@asynccontextmanager
async def lifespan(app: FastAPI):
    db_uri = "postgresql://postgres:root@localhost:5433/mcp_agent"
    redis_uri = "redis://localhost:6379"
    store_cm = None
    saver_cm = None
    checkpointer = None

    try:
        logger.info("[BOOT] Initializing PostgresStore")
        store_cm = PostgresStore.from_conn_string(db_uri)
        store = store_cm.__enter__()

        logger.info("[BOOT] Initializing RedisSaver")

        # ENTER CONTEXT → REAL SAVER
        saver_cm = RedisStore.from_conn_string(redis_uri)
        redis_store = saver_cm.__enter__()

        logger.info("[BOOT] Building Router Graph")
        graph = create_router_graph(
            store=store,
            redis_store=redis_store,
        )

        app.state.graph = graph
        yield

    finally:
        logger.info("[SHUTDOWN] Closing resources")

        if saver_cm:
            saver_cm.__exit__(None, None, None)

        if store_cm:
            store_cm.__exit__(None, None, None)


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
        "__clear__": True, 
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
            tool_error = None
            ai_message = None

            for msg in reversed(result["messages"]):
                if msg.type == "tool" and str(msg.content).startswith("Error"):
                    tool_error = msg.content
                    break

                if msg.type == "ai" and ai_message is None:
                    ai_message = msg.content

            agent_response = tool_error or ai_message or "File processed."


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