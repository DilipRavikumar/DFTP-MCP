import os
import json
import logging
import jwt
import requests
import uvicorn
import httpx

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

from fastapi import (
    FastAPI,
    Response,
    Request,
    HTTPException,
    Depends,
    File,
    UploadFile,
    Form,
)
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager

from langgraph.store.postgres import PostgresStore

import sys
from pathlib import Path

# Add project root to path so 'src' can be imported
sys.path.append(str(Path(__file__).parent.parent))

from src.router_agent.graph import create_router_graph


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db_uri = os.getenv(
        "POSTGRES_URI",
        "postgresql://postgres:root@localhost:5433/mcp_agent",
    )

    store_cm = None
    store = None

    try:
        logger.warning("[LIFESPAN] Initializing PostgresStore")

        store_cm = PostgresStore.from_conn_string(db_uri)
        store = store_cm.__enter__()

        logger.warning("[LIFESPAN] Creating router graph with store")
        graph = await create_router_graph(store=store)

        app.state.graph = graph
        app.state.store = store

        logger.warning("[LIFESPAN] Router graph initialized successfully")

        yield

    except Exception as e:
        logger.exception("[LIFESPAN] Failed during startup")
        raise e

    finally:
        if store_cm:
            store_cm.__exit__(None, None, None)
            logger.info("[LIFESPAN] PostgresStore connection closed")


app = FastAPI(
    title="LangGraph Unified Backend",
    lifespan=lifespan,
)


origins = [
    "http://localhost:4200",
    "http://localhost:8000",
    "http://localhost:8081",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


KEYCLOAK_URL = "http://localhost:8180"
REALM = "authentication"
CLIENT_ID = "public-client"

BACKEND_URL = "http://localhost:8081"
FRONTEND_URL = "http://localhost:4200"
CALLBACK_URI = f"{BACKEND_URL}/api/auth/callback"


class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default"

# Authentication Routes

@app.get("/api/auth/login")
def login():
    keycloak_login_url = (
        f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/auth"
        f"?client_id={CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={CALLBACK_URI}"
    )
    return RedirectResponse(keycloak_login_url)

from urllib.parse import quote

@app.get("/api/auth/logout")
def logout():
    post_logout_redirect = quote(FRONTEND_URL)

    logout_url = (
        f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/logout"
        f"?client_id={CLIENT_ID}"
        f"&post_logout_redirect_uri={post_logout_redirect}"
    )
    response = RedirectResponse(logout_url)
    response.delete_cookie("access_token", path="/")
    return response

@app.get("/api/auth/callback")
def callback(code: str = None):
    if not code:
        return RedirectResponse(FRONTEND_URL)

    try:
        data = {
            "client_id": CLIENT_ID,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": CALLBACK_URI,
        }

        token_response = requests.post(
            f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/token",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        token_response.raise_for_status()
        token_data = token_response.json()
        access_token = token_data.get("access_token")

        if not access_token:
            raise HTTPException(status_code=401, detail="Access token missing")

        response = RedirectResponse(
            url=f"{FRONTEND_URL}/login-callback",
            status_code=302,
        )

        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=False,
            secure=False,
            samesite="Lax",
            path="/",
        )

        return response

    except Exception as e:
        logger.error(f"Auth callback error: {e}")
        return RedirectResponse(
            f"{FRONTEND_URL}?error=auth_failed&details={str(e)}"
        )

def normalize_user_context(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Normalizes role and scope from JWT payload into lists."""

    # Normalize scope
    scope = payload.get("scope", [])
    if isinstance(scope, str):
        scope = scope.split(" ")

    # Normalize roles
    roles = payload.get("roles", [])

    # Handle Keycloak client roles
    client_roles = (
        payload.get("resource_access", {})
        .get(CLIENT_ID, {})
        .get("roles", [])
    )
    if client_roles:
        roles.extend(client_roles)

    # Handle single role field
    single_role = payload.get("role")
    if single_role:
        roles.append(single_role)

    roles = list(set(roles))

    return {
        "user_id": payload.get("sub", "anonymous"),
        "roles": roles,
        "scope": scope,
        "username": payload.get("preferred_username"),
    }


def extract_user_context_from_request(
    req: Request,
) -> Optional[Dict[str, Any]]:
    """Extract and normalize user context from cookies or Authorization header."""

    token = req.cookies.get("access_token")
    logger.debug(
        f"[AUTH] Token from cookies: {'FOUND' if token else 'NOT FOUND'}"
    )

    if not token:
        auth_header = req.headers.get("Authorization")
        logger.debug(
            f"[AUTH] Authorization header: {'FOUND' if auth_header else 'NOT FOUND'}"
        )
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            logger.debug("[AUTH] Token extracted from Bearer header")

    if not token:
        logger.warning("[AUTH] No token found in cookies or headers")
        return None

    try:
        payload = jwt.decode(token, options={"verify_signature": False})

        logger.debug(f"[AUTH] JWT payload keys: {list(payload.keys())}")
        logger.debug(f"[AUTH] JWT roles: {payload.get('roles')}")
        logger.debug(
            f"[AUTH] JWT resource_access: {payload.get('resource_access')}"
        )

        context = normalize_user_context(payload)

        logger.info(
            f"[AUTH] Extracted user context: "
            f"user_id={context.get('user_id')}, roles={context.get('roles')}"
        )

        return context

    except Exception as e:
        logger.error(f"[AUTH] Failed to decode token: {e}")
        return None


@app.get("/api/auth/me")
def me(request: Request):
    """Return current authenticated user information."""

    user_context = extract_user_context_from_request(request)

    if not user_context:
        return {
            "authenticated": False,
            "scope": "General",
            "user_id": "anonymous",
            "roles": [],
        }

    return {
        "authenticated": True,
        "user_id": user_context.get("user_id"),
        "username": user_context.get("username"),
        "scope": user_context.get("scope"),
        "roles": user_context.get("roles", []),
    }


async def stream_generator(
    input_message: str,
    thread_id: str,
    user_context: Dict[str, Any],
    req: Request,
):
    """Run the LangGraph router and stream events to the client."""

    from langchain_core.messages import HumanMessage

    input_state = {
        "messages": [HumanMessage(content=input_message)]
    }

    config = {
        "configurable": {
            "thread_id": thread_id,
            "user": user_context,
        }
    }

    announced_agents = set()

    try:
        async for event in req.app.state.graph.astream_events(
            input_state,
            config=config,
            version="v1",
        ):
            kind = event["event"]
            metadata = event.get("metadata", {})
            node_name = metadata.get("langgraph_node", "")

            # Ignore router classification output
            if node_name == "classify_query":
                continue

            # Stream model tokens
            if kind == "on_chat_model_stream":
                content = event["data"]["chunk"].content

                if isinstance(content, list):
                    text_content = ""
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text_content += block.get("text", "")
                        elif isinstance(block, str):
                            text_content += block
                    content = text_content

                if content:
                    yield json.dumps(
                        {"type": "message", "content": content}
                    ) + "\n"

            # Announce agent entry
            elif (
                kind == "on_chain_start"
                and node_name in ["mcp_agent", "order_agent", "nav_agent"]
            ):
                agent_map = {
                    "mcp_agent": "General Agent",
                    "order_agent": "Order Agent",
                    "nav_agent": "NAV Agent",
                }

                if node_name not in announced_agents:
                    announced_agents.add(node_name)
                    friendly = agent_map.get(node_name, node_name)
                    yield json.dumps(
                        {
                            "type": "message",
                            "content": f"\n\n**Using {friendly}**...\n\n",
                        }
                    ) + "\n"

    except Exception as e:
        logger.error(f"[STREAM] Streaming error: {e}")
        yield json.dumps(
            {"type": "error", "content": str(e)}
        ) + "\n"

@app.post("/api/chat")
async def chat(request: ChatRequest, req: Request):
    """Chat endpoint – invokes LangGraph agent with auth + memory."""

    user_context = extract_user_context_from_request(req)

    # DEV fallback (AUTH BRANCH – UNCHANGED)
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



@app.post("/api/upload")
async def upload_file(
    req: Request,
    file: UploadFile = File(...),
    thread_id: str = Form(...),
    description: str = Form(""),
):
    """Handle file uploads, save locally, and trigger agent processing."""


    user_context = extract_user_context_from_request(req)

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



if __name__ == "__main__":
    uvicorn.run(
        "src.app_server:app",
        host="0.0.0.0",
        port=8081,
        reload=True,
    )
