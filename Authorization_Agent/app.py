import streamlit as st
import requests
import json
import os
import boto3
from typing import TypedDict
from langgraph.graph import StateGraph, END
from dotenv import load_dotenv
import subprocess

# ---------------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------------
st.set_page_config(page_title="DTCC MCP Chatbot", page_icon="💬")

# ---------------------------------------------------------
# KEYCLOAK DETAILS
# ---------------------------------------------------------
KEYCLOAK_DOMAIN = "http://localhost:8180"
REALM = "authorization"
CLIENT_ID = "public-client"
TOKEN_URL = f"{KEYCLOAK_DOMAIN}/realms/{REALM}/protocol/openid-connect/token"

# ---------------------------------------------------------
# SESSION STORAGE
# ---------------------------------------------------------
if "tokens" not in st.session_state:
    st.session_state.tokens = None

# ---------------------------------------------------------
# LOGIN FUNCTION
# ---------------------------------------------------------
def login(username, password):
    data = {
        "grant_type": "password",
        "client_id": CLIENT_ID,
        "username": username,
        "password": password
    }
    response = requests.post(TOKEN_URL, data=data)
    if response.status_code != 200:
        return None, response.text
    return response.json(), None

# ---------------------------------------------------------
# HELPER FUNCTION TO RUN main.py
# ---------------------------------------------------------
def run_main_py(user_prompt: str) -> str:
    try:
        result = subprocess.run(
            ["python", "main.py", user_prompt],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return f"Error running main.py: {e.stderr}"

# ---------------------------------------------------------
# CHAT PAGE FUNCTION
# ---------------------------------------------------------
def render_chat_page():
    load_dotenv()

    # Load CSS if exists
    if os.path.exists("style.css"):
        with open("style.css") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

    # Mock tokens
    MOCK_TOKENS = {
        "t-111": {"scope": "Assets"},
        "t-222": {"scope": "Wealth"},
        "t-333": {"scope": "General"},
    }

    def mock_token_service(token: str):
        return MOCK_TOKENS.get(token)

    # Agent state
    class AgentState(TypedDict):
        token: str
        user_message: str
        scope: str
        error: str

    # Bedrock client
    bedrock = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-2"))

    def validate_token(state: AgentState) -> AgentState:
        token_input = state["token"]
        token_info = mock_token_service(token_input)
        if not token_info:
            state["error"] = "❌ Invalid token. Please check your token in the sidebar."
            return state
        state["scope"] = token_info["scope"]
        return state

    # Graph Setup
    graph = StateGraph(AgentState)
    graph.add_node("validate_token", validate_token)
    graph.set_entry_point("validate_token")
    graph.add_edge("validate_token", END)
    compiled_graph = graph.compile()

    # Stream Bedrock AI response
    def stream_nova_pro(scope: str, messages: list):
        system_prompt = f"You are the {scope} agent for DTCC. Answer helpfully and professionally."
        bedrock_messages = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "assistant"
            bedrock_messages.append({
                "role": role,
                "content": [{"text": msg["content"]}]
            })

        model_id = os.getenv(
            "BEDROCK_MODEL_ID",
            "arn:aws:bedrock:us-east-2:254800774891:inference-profile/us.amazon.nova-pro-v1:0"
        )

        try:
            response = bedrock.converse_stream(
                modelId=model_id,
                messages=bedrock_messages,
                system=[{"text": system_prompt}],
                inferenceConfig={"maxTokens": 1000, "temperature": 0.7}
            )
            stream = response.get('stream')
            if stream:
                for event in stream:
                    if 'contentBlockDelta' in event:
                        yield event['contentBlockDelta']['delta']['text']
        except Exception as e:
            yield f"Error: {str(e)}"

    # ----------------- UI START -----------------
    st.title("DTCC Context-Aware Chat")

    # Sidebar
    with st.sidebar:
        st.header("Configuration")
        token = st.text_input("Enter your token", value="t-111", help="Try: t-111, t-222, t-333")

        if st.button("Set Token"):
            info = mock_token_service(token)
            if info:
                st.sidebar.success(f"Active Scope: {info['scope']}")
            else:
                st.sidebar.error("Invalid Token")

        st.divider()

        if st.button("Clear History"):
            st.session_state.messages = []
            st.rerun()

    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat input
    if prompt := st.chat_input("How can I help you today?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            initial_state = {
                "token": token,
                "user_message": prompt,
                "scope": "",
                "error": ""
            }

            graph_result = compiled_graph.invoke(initial_state)

            if graph_result.get("error"):
                error_msg = graph_result["error"]
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
            else:
                scope = graph_result["scope"]

                status_placeholder = st.empty()
                status_placeholder.caption(f"Agent Scope: **{scope}**")

                # Run main.py first
                main_output = run_main_py(prompt)
                st.session_state.messages.append({"role": "assistant", "content": main_output})
                st.markdown(main_output)

                # Stream AI response
                response_placeholder = st.empty()
                full_response = ""
                for chunk in stream_nova_pro(scope, st.session_state.messages):
                    full_response += chunk
                    response_placeholder.markdown(full_response + "▌")

                response_placeholder.markdown(full_response)
                status_placeholder.empty()
                st.session_state.messages.append({"role": "assistant", "content": full_response})

# ---------------------------------------------------------
# RENDER LOGIN OR CHAT
# ---------------------------------------------------------
if st.session_state.tokens is None:
    st.title("🔐 Keycloak Login")
    username = st.text_input("Enter username")
    password = st.text_input("Enter password", type="password")

    if st.button("Login"):
        tokens, error = login(username, password)
        if tokens:
            st.session_state.tokens = tokens
            with open("session.json", "w") as f:
                json.dump(tokens, f, indent=4)
            st.success("Login successful!")
            st.rerun()
        else:
            st.error(f"Login failed: {error}")
else:
    render_chat_page()
