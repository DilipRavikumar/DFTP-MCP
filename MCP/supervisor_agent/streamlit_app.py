import os
import sys
import uuid
import json
import requests
import streamlit as st
from dotenv import load_dotenv
import importlib.util

# =====================================================
# ENV + PAGE CONFIG
# =====================================================
load_dotenv()

st.set_page_config(
    page_title="DTCC Multi-Agent Orchestrator",
    page_icon="🤖",
    layout="wide",
)

# =====================================================
# IMPORT ORCHESTRATOR
# =====================================================
current_dir = os.path.dirname(os.path.abspath(__file__))
main_path = os.path.join(current_dir, "main.py")

spec = importlib.util.spec_from_file_location("orchestrator_main", main_path)
orchestrator_main = importlib.util.module_from_spec(spec)
spec.loader.exec_module(orchestrator_main)

load_orchestrator_agent = orchestrator_main.load_orchestrator_agent

# =====================================================
# FILE STORAGE (MUST MATCH AGENT)
# =====================================================
PROJECT_ROOT = os.path.abspath(os.path.join(current_dir, ".."))
ORDER_INGESTION_AGENT_DIR = os.path.join(PROJECT_ROOT, "Order_Ingestion_Agent")
FILES_DIR = os.path.join(ORDER_INGESTION_AGENT_DIR, "files")
os.makedirs(FILES_DIR, exist_ok=True)

# =====================================================
# KEYCLOAK CONFIG
# =====================================================
KEYCLOAK_DOMAIN = os.getenv("KEYCLOAK_DOMAIN", "http://localhost:8180")
REALM = os.getenv("KEYCLOAK_REALM", "authentication")
CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "public-client")
TOKEN_URL = f"{KEYCLOAK_DOMAIN}/realms/{REALM}/protocol/openid-connect/token"

def login(username: str, password: str):
    try:
        data = {
            "grant_type": "password",
            "client_id": CLIENT_ID,
            "username": username,
            "password": password,
        }
        response = requests.post(TOKEN_URL, data=data, timeout=5)
        if response.status_code == 200:
            return response.json(), None
        return None, response.text
    except Exception as e:
        return None, str(e)

def extract_scope_from_token():
    try:
        parent_dir = os.path.abspath(os.path.join(current_dir, ".."))
        auth_agent_dir = os.path.join(parent_dir, "Authorization_Agent")
        if auth_agent_dir not in sys.path:
            sys.path.insert(0, auth_agent_dir)

        from wrapper import extract_scope_and_roles
        scope_info = extract_scope_and_roles()
        return scope_info.get("scope", "unauthorized")
    except Exception:
        return "unauthorized"

# =====================================================
# ORCHESTRATOR CACHE
# =====================================================
@st.cache_resource
def get_orchestrator(_hash=None):
    return load_orchestrator_agent()

def get_orchestrator_with_invalidation():
    try:
        import hashlib
        config_path = os.path.join(current_dir, "supervisor_config.yaml")
        with open(config_path, "rb") as f:
            return get_orchestrator(hashlib.md5(f.read()).hexdigest())
    except:
        return get_orchestrator("default")

# =====================================================
# SESSION STATE
# =====================================================
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []
if "scope" not in st.session_state:
    st.session_state.scope = "General"
if "tokens" not in st.session_state:
    st.session_state.tokens = None
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# =====================================================
# UI HEADER
# =====================================================
st.title("🤖 DTCC Multi-Agent Orchestrator")
st.caption("Unified interface for all specialized agents")

# =====================================================
# LOGIN UI
# =====================================================
if not st.session_state.logged_in:
    with st.container():
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.subheader("🔐 Keycloak Authentication")
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")

            if st.button("Login", type="primary"):
                tokens, error = login(username, password)
                if tokens:
                    st.session_state.tokens = tokens
                    st.session_state.logged_in = True

                    with open(os.path.join(current_dir, "session.json"), "w") as f:
                        json.dump(tokens, f, indent=2)

                    st.session_state.scope = extract_scope_from_token()
                    st.success("✅ Login successful!")
                    st.rerun()
                else:
                    st.error(error)

    st.info("👆 Please login to continue")
    st.stop()

# =====================================================
# SIDEBAR
# =====================================================
with st.sidebar:
    st.header("⚙️ Configuration")
    st.success("✅ Authenticated")
    st.info(f"**Scope:** {st.session_state.scope}")
    st.info(f"**Thread ID:** {st.session_state.thread_id[:8]}...")

    if st.button("🗑️ Clear History"):
        st.session_state.messages = []
        st.session_state.thread_id = str(uuid.uuid4())
        get_orchestrator.clear()
        st.rerun()

# =====================================================
# CHAT HISTORY
# =====================================================
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# =====================================================
# FILE UPLOAD (AGENT-COMPATIBLE)
# =====================================================
st.divider()
with st.expander("📤 Upload File", expanded=False):
    st.caption("Upload files for trade simulation (CSV, ZIP, TXT, JSON, XML, DAT)")

    uploaded_file = st.file_uploader(
        "Choose a file",
        type=["csv", "zip", "txt", "json", "xml", "dat"],
    )

    if uploaded_file is not None:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.info(f"📄 **{uploaded_file.name}** ({uploaded_file.size / 1024:.2f} KB)")
        with col2:
            if st.button("Upload", type="primary"):
                try:
                    file_path = os.path.join(FILES_DIR, uploaded_file.name)
                    with open(file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())

                    upload_request = f"upload {uploaded_file.name}"

                    st.session_state.messages.append({
                        "role": "user",
                        "content": f"📤 Uploading file: {uploaded_file.name}",
                    })

                    orchestrator = get_orchestrator_with_invalidation()
                    config = {"configurable": {"thread_id": st.session_state.thread_id}}

                    response_text = ""
                    for params in orchestrator.stream(
                        {"messages": [{"role": "user", "content": upload_request}]},
                        config,
                    ):
                        for _, update in params.items():
                            if "messages" in update:
                                response_text = update["messages"][-1].content

                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": response_text,
                    })

                    st.success(f"✅ File {uploaded_file.name} processed!")
                    st.rerun()

                except Exception as e:
                    st.error(f"❌ Upload failed: {str(e)}")

# =====================================================
# CHAT INPUT
# =====================================================
if prompt := st.chat_input("Ask the orchestrator agent..."):
    st.session_state.messages.append({"role": "user", "content": prompt})

    orchestrator = get_orchestrator_with_invalidation()
    config = {"configurable": {"thread_id": st.session_state.thread_id}}

    full_response = ""
    for params in orchestrator.stream(
        {"messages": [{"role": "user", "content": prompt}]},
        config,
    ):
        for _, update in params.items():
            if "messages" in update:
                full_response = update["messages"][-1].content

    st.session_state.messages.append(
        {"role": "assistant", "content": full_response}
    )
    st.rerun()
