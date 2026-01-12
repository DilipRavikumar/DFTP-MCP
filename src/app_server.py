
import os
import json
import logging
import jwt
import requests
import uvicorn
import httpx
from router_agent.graph import create_router_graph
# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, Response, Request, HTTPException, Depends, File, UploadFile, Form
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from langgraph.store.postgres import PostgresStore
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

import sys
from pathlib import Path

# Add project root to path so 'src' can be imported
sys.path.append(str(Path(__file__).parent.parent))


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    db_uri = os.getenv(
        "POSTGRES_URI",
        "postgresql://postgres:root@localhost:5433/mcp_agent",
    )

    store = None
    try:
        # ✅ PostgresStore is a *SYNC* context manager
        store_cm = PostgresStore.from_conn_string(db_uri)
        store = store_cm.__enter__()

        # ✅ Graph MUST be created while store is alive
        graph = await create_router_graph(store=store)

        app.state.graph = graph
        app.state.store = store

        logger.warning("Router graph initialized successfully. Store=PostgresStore")

        yield

    except Exception as e:
        logger.exception("Failed during application lifespan startup")
        raise e

    finally:
        if store_cm:
            store_cm.__exit__(None, None, None)
            logger.info("PostgresStore connection closed")


app = FastAPI(
    title="LangGraph Unified Backend",
    lifespan=lifespan
)


# CORS Configuration
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

# --- Configuration ---
KEYCLOAK_URL = "http://localhost:8180"
REALM = "authentication"
CLIENT_ID = "public-client"
# Adjust these URLs based on your environment
BACKEND_URL = "http://localhost:8081"
FRONTEND_URL = "http://localhost:4200"
CALLBACK_URI = f"{BACKEND_URL}/api/auth/callback"

# --- Models ---
class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default"

# --- Authentication Routes ---

@app.get("/api/auth/login")
def login():
    """Redirects user to Keycloak login page"""
    keycloak_login_url = (
        f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/auth"
        f"?client_id={CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={CALLBACK_URI}"
    )
    return RedirectResponse(keycloak_login_url)

@app.get("/api/auth/logout")
def logout():
    """Logs user out of Keycloak and clears cookies"""
    post_logout_redirect = f"{FRONTEND_URL}"
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
    """Handles Keycloak callback, exchanges code for token, sets cookie"""
    if not code:
        return RedirectResponse(FRONTEND_URL)

    try:
        # Exchange code for token
        data = {
            "client_id": CLIENT_ID,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": CALLBACK_URI
        }
        token_response = requests.post(
            f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/token",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        token_response.raise_for_status()
        token_data = token_response.json()
        access_token = token_data.get("access_token")

        if not access_token:
            raise HTTPException(status_code=401, detail="Access token missing")

        # Redirect to frontend with cookie
        response = RedirectResponse(url=f"{FRONTEND_URL}/login-callback", status_code=302)
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=False, # Allow frontend JS to read if needed (or keep True for security)
            secure=False,   # Set to True in production (HTTPS)
            samesite="Lax",
            path="/"
        )
        return response

    except Exception as e:
        logger.error(f"Auth callback error: {e}")
        error_msg = str(e)
        return RedirectResponse(f"{FRONTEND_URL}?error=auth_failed&details={error_msg}")

@app.get("/api/auth/me")
def me(request: Request):
    """Returns current user info based on token"""
    token = request.cookies.get("access_token")
    if not token:
        # Check Authorization header as fallback
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    if not token:
        return {"authenticated": False, "scope": "General", "user_id": "anonymous"}

    try:
        # Decode without verification for internal use (Gateway verified it, or we verify here)
        # In prod, verify signature with Keycloak public key
        payload = jwt.decode(token, options={"verify_signature": False})
        user_scope = payload.get("scope", "General")
        
        return {
            "authenticated": True,
            "user_id": payload.get("sub"),
            "username": payload.get("preferred_username"),
            "scope": user_scope,
            # Extract Client Roles: resource_access.{CLIENT_ID}.roles
            "roles": payload.get("resource_access", {}).get(CLIENT_ID, {}).get("roles", [])
        }
    except Exception as e:
        logger.error(f"Token decode error: {e}")
        return {"authenticated": False, "error": str(e)}

# --- Chat / Agent Routes ---

async def stream_generator(input_message: str, thread_id: str, user_context: Dict,req: Request):
    """Runs the graph and streams events to the client"""
    
    from langchain_core.messages import HumanMessage
    
    # LangGraph input structure - use proper message objects
    input_state = {
        "messages": [HumanMessage(content=input_message)]
    }
    
    # Configuration
    config = {
        "configurable": {
            "thread_id": thread_id,
            "user": user_context
        }
    }

    announced_agents = set()

    try:
        async for event in req.app.state.graph.astream_events(input_state, config=config, version="v1"):
            kind = event["event"]
            
            # Inspect metadata to filter noise and identify active agent
            metadata = event.get("metadata", {})
            node_name = metadata.get("langgraph_node", "")
            
            # 1. Ignore output from the Router's classification step
            if node_name == "classify_query":
                continue

            # 'on_chat_model_stream' gives tokens. 'on_chain_end' gives full outputs.
            # You might need to adjust this depending on exactly what your frontend expects
            if kind == "on_chat_model_stream":
                content = event["data"]["chunk"].content
                
                # Handle structured content (list of blocks) from Claude 3
                if isinstance(content, list):
                    text_content = ""
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text_content += block.get("text", "")
                        elif isinstance(block, str):
                            text_content += block
                    content = text_content

                if content:
                    yield json.dumps({"type": "message", "content": content}) + "\n"
            
            # 3. Detect Node Entry to signal user
            elif kind == "on_chain_start" and node_name in ["mcp_agent", "order_agent", "nav_agent"]:
                # Map technical node names to friendly names
                agent_map = {
                    "mcp_agent": "General Agent",
                    "order_agent": "Order Agent",
                    "nav_agent": "NAV Agent"
                }
                
                if node_name not in announced_agents:
                    announced_agents.add(node_name)
                    friendly_name = agent_map.get(node_name, node_name)
                    # Send a system message or special marker
                    # We'll stick it in a 'meta' event for now, frontend might need update to render it nicely
                    # For now, let's prepend it as a bold indicator if it's the first time
                    yield json.dumps({"type": "message", "content": f"\n\n**Using {friendly_name}**...\n\n"}) + "\n"
            
    except Exception as e:
        logger.error(f"Streaming error: {e}")
        yield json.dumps({"type": "error", "content": str(e)}) + "\n"


@app.post("/api/chat")
async def chat(request: ChatRequest, req: Request):
    """Chat endpoint - invokes LangGraph agent"""
    
    # Extract user context from token
    token = req.cookies.get("access_token")
    if not token:
         auth_header = req.headers.get("Authorization")
         if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    user_context = {}
    if token:
         try:
            payload = jwt.decode(token, options={"verify_signature": False})
            user_context = {
                "user_id": payload.get("sub", "anonymous"),
                "role": "user", # Extract role properly if needed
                "scope": payload.get("scope", "").split(" ")
            }
         except:
             pass
    
    # Default for dev if auth fails or not enabled
    if not user_context:
        user_context = {
             "user_id": "test_user",
             "role": "admin",
             "scope": ["mcp-agent", "order-agent", "nav-agent", "router-agent"]
        }

    return StreamingResponse(
        stream_generator(request.message, request.thread_id, user_context,req),
        media_type="application/x-ndjson"
    )

@app.post("/api/upload")
async def upload_file(
    req: Request,
    file: UploadFile = File(...),
    thread_id: str = Form(...),
    description: str = Form("")
):
    """Handle file uploads, save locally, and trigger agent processing."""
    
    # 1. Auth / User Context (Same as chat endpoint)
    token = req.cookies.get("access_token")
    if not token:
         auth_header = req.headers.get("Authorization")
         if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    user_context = {}
    if token:
         try:
            payload = jwt.decode(token, options={"verify_signature": False})
            user_context = {
                "user_id": payload.get("sub", "anonymous"),
                "username": payload.get("preferred_username"),
                "scope": payload.get("scope", "").split(" "),
                # Extract Client Roles: resource_access.{CLIENT_ID}.roles
                "roles": payload.get("resource_access", {}).get(CLIENT_ID, {}).get("roles", [])
            }
         except:
             pass
    
    if not user_context:
        # Default for dev
        user_context = {
             "user_id": "test_user",
             "username": "DevUser",
             "roles": ["admin"],
             "scope": ["mutual funds", "mcp-agent", "order-agent", "nav-agent", "router-agent"]
        }

    # 2. Save File Locally
    try:
        upload_dir = Path("uploads")
        upload_dir.mkdir(exist_ok=True)
        
        file_path = upload_dir / file.filename
        # TODO: Handle unique filenames if needed
        
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
            
        logger.info(f"File saved to: {file_path.absolute()}")
        
    except Exception as e:
        logger.error(f"File save error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")

    # 3. Invoke Agent with File Info
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
            "user": user_context
        }
    }
    
    try:
        # We use ainvoke to run the graph
        result = await req.app.state.graph.ainvoke(input_state, config=config)

        
        agent_response = "File processed."
        if "messages" in result and result["messages"]:
            # Get the last message (AIMessage)
            for msg in reversed(result["messages"]):
                if msg.type == "ai":
                    agent_response = msg.content
                    # Parse block format if needed (similar to stream logic)
                    if isinstance(agent_response, list):
                        text_content = ""
                        for block in agent_response:
                             if isinstance(block, dict) and block.get("type") == "text":
                                 text_content += block.get("text", "")
                             elif isinstance(block, str):
                                 text_content += block
                        agent_response = text_content
                    break
        
        return {"agent_response": agent_response}
        
    except Exception as e:
        logger.error(f"Agent processing error: {e}")
        return {"agent_response": f"Error during processing: {str(e)}"}

# --- Entry Point ---
if __name__ == "__main__":
    # Run uvicorn server
    uvicorn.run("src.app_server:app", host="0.0.0.0", port=8081, reload=True)
