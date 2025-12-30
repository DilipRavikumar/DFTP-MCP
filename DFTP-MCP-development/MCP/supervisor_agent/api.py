import os
import sys
import json
import uuid
import shutil
import asyncio
import requests
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

auth_agent_dir = os.path.join(parent_dir, "Authorization_Agent")
if auth_agent_dir not in sys.path:
    sys.path.insert(0, auth_agent_dir)

try:
    from .main import load_orchestrator_agent
    # Authorization_Agent is a sibling package. 
    # Since we added parent_dir to sys.path, absolute import should work if Authorization_Agent has __init__.py
    # But better to check.
    from Authorization_Agent.wrapper import extract_scope_and_roles
except ImportError:
    # Fallback for when running as a script (not recommended but possible)
    from main import load_orchestrator_agent
    from Authorization_Agent.wrapper import extract_scope_and_roles


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ORDER_INGESTION_AGENT_DIR = os.path.join(parent_dir, "Order_Ingestion_Agent")
FILES_DIR = os.path.join(ORDER_INGESTION_AGENT_DIR, "files")
os.makedirs(FILES_DIR, exist_ok=True)

KEYCLOAK_DOMAIN = os.getenv("KEYCLOAK_DOMAIN", "http://localhost:8180")
REALM = os.getenv("KEYCLOAK_REALM", "authentication")
CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "public-client")
TOKEN_URL = f"{KEYCLOAK_DOMAIN}/realms/{REALM}/protocol/openid-connect/token"

orchestrator = load_orchestrator_agent(os.path.join(current_dir, "supervisor_config.yaml"))

class LoginRequest(BaseModel):
    username: str
    password: str

class ChatRequest(BaseModel):
    message: str
    thread_id: str
    scope: str
    roles: List[str] = []
    token: str

@app.post("/api/login")
async def login(request: LoginRequest):
    try:
        data = {
            "grant_type": "password",
            "client_id": CLIENT_ID,
            "username": request.username,
            "password": request.password,
        }
        response = requests.post(TOKEN_URL, data=data, timeout=5)
        if response.status_code == 200:
            tokens = response.json()
            
            # Here we are mocking the scope extraction since we don't have the actual token validation logic 
            # fully exposed without the middleware or the actual auth agent logic that parses the token.
            # However, we can try to use the auth agent wrapper if it supports passing the token.
            # The existing wrapper.py uses `extract_token_and_scope(request)`, expecting a string request.
            # We will return the tokens and let the client pass them back.
            
            # For the purpose of this migration, we will do a best effort extraction 
            # purely to return the scope to the frontend for display if needed.
            return {"tokens": tokens}
        else:
            raise HTTPException(status_code=401, detail=response.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    config = {"configurable": {"thread_id": request.thread_id}}
    
    # We construct the message internally.
    # Note: The original streamlit app didn't explicitly pass scope in the prompt 
    # but the agents might expect it "injected".
    # In main.py: direct_agent_tool logic -> `get_user_scope()` which calls `Authorization_Agent.wrapper`.
    # That wrapper seems to look at some global context or expects the request to have it?
    # Wait, `get_user_scope` in `main.py` calls `auth_module.extract_scope_and_roles()`.
    # `Authorization_Agent/agents.py`'s `extract_token_and_scope` usually parses a "request" string
    # BUT `wrapper.py` calls it with `request` default "".
    # If the system relies on a global or strict injection, we might need to mock or set it.
    
    # However, `main.py` lines 223: `scope_payload = f"SCOPE:{current_scope}|..."`
    # It gets `current_scope` from `get_user_scope()`.
    # `get_user_scope` imports `Authorization_Agent.wrapper`.
    # `Authorization_Agent.wrapper.extract_scope_and_roles` calls `agents.extract_token_and_scope(request)`.
    # This seems to rely on the `request` being passed in... but `get_user_scope` takes NO arguments.
    # This implies there might be a disconnect in the current python code or it relies on a file/env var.
    # CHECK: `start_session_state.scope` in Streamlit was manually set.
    
    # IMPORTANT: The python code in `main.py` uses `functions = AgentToolFactory.get_functions_from_module...`
    # and the closure captures `get_user_scope`.
    # If `get_user_scope` is stateless (which it appears to be), it allows "unauthorized".
    # To properly support granular auth, we might need to modify `main.py` to accept scope in `invoke`, 
    # OR we rely on the prompt Engineering trick: "SCOPE:MutualFunds|REQUEST:..."
    # The `Order_Details_Agent` specifically parses `SCOPE:` from the request string.
    
    # SO, we will prepend the scope to the prompt if provided.
    
    actual_prompt = request.message
    if request.scope:
        actual_prompt = f"SCOPE:{request.scope}|ROLES:{','.join(request.roles)}|REQUEST:{request.message}"

    async def event_generator():
        try:
            # We stream the response.
            for step in orchestrator.stream(
                {"messages": [{"role": "user", "content": actual_prompt}]},
                config,
            ):
                for update in step.values():
                    if isinstance(update, dict):
                        for message in update.get("messages", []):
                            content = ""
                            if hasattr(message, "content"):
                                content = message.content
                            elif hasattr(message, "text"):
                                content = message.text
                            
                            if content:
                                yield json.dumps({"type": "message", "content": content}) + "\n"
        except Exception as e:
            yield json.dumps({"type": "error", "content": str(e)}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...), thread_id: str = Form(...)):
    try:
        file_path = os.path.join(FILES_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Notify agent about upload
        upload_request = f"upload {file.filename}"
        config = {"configurable": {"thread_id": thread_id}}
        
        response_text = ""
        for step in orchestrator.stream(
             {"messages": [{"role": "user", "content": upload_request}]},
             config,
        ):
            for update in step.values():
                 if isinstance(update, dict):
                     for message in update.get("messages", []):
                         if hasattr(message, "content"):
                             response_text = message.content
        
        return {"filename": file.filename, "agent_response": response_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health():
    return {"status": "ok"}
