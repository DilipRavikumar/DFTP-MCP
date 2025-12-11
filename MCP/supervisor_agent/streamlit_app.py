
import os
import sys
import uuid
import streamlit as st
import requests
import json
from dotenv import load_dotenv

# Import from the current directory (supervisor_agent)
# Use absolute import to avoid conflicts with Authorization_Agent/main.py
import importlib.util
current_dir = os.path.dirname(os.path.abspath(__file__))
main_path = os.path.join(current_dir, "main.py")
spec = importlib.util.spec_from_file_location("supervisor_main", main_path)
supervisor_main = importlib.util.module_from_spec(spec)
spec.loader.exec_module(supervisor_main)
load_supervisor_agent = supervisor_main.load_supervisor_agent

load_dotenv()

st.set_page_config(page_title="DTCC Multi-Agent Supervisor", page_icon="🤖", layout="wide")

# Load CSS
if os.path.exists("style.css"):
    with open("style.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Keycloak Configuration (from Authorization Agent)
KEYCLOAK_DOMAIN = os.getenv("KEYCLOAK_DOMAIN", "http://localhost:8180")
REALM = os.getenv("KEYCLOAK_REALM", "authentication")  # Fixed: was "authentication", should be "authorization"
CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "public-client")
TOKEN_URL = f"{KEYCLOAK_DOMAIN}/realms/{REALM}/protocol/openid-connect/token"

def login(username: str, password: str):
    """Login to Keycloak and get tokens."""
    try:
        data = {
            "grant_type": "password",
            "client_id": CLIENT_ID,
            "username": username,
            "password": password
        }
        response = requests.post(TOKEN_URL, data=data, timeout=5)
        if response.status_code == 200:
            return response.json(), None
        return None, response.text
    except Exception as e:
        return None, str(e)

def extract_scope_from_token():
    """Extract scope from the current session token."""
    try:
        import sys
        import os
        parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        auth_agent_dir = os.path.join(parent_dir, "Authorization_Agent")
        if auth_agent_dir not in sys.path:
            sys.path.insert(0, auth_agent_dir)
        
        # Import authorization wrapper to get scope
        # Since we added auth_agent_dir to sys.path, we can import directly
        from wrapper import extract_scope_and_roles
        scope_info = extract_scope_and_roles()
        return scope_info.get("scope", "unauthorized")
    except Exception as e:
        # Fallback: try to read scope directly from session.json
        try:
            session_path = os.path.join(os.path.dirname(__file__), "session.json")
            if os.path.exists(session_path):
                with open(session_path, "r") as f:
                    tokens = json.load(f)
                    # Try to decode token to get scope
                    from jose import jwt
                    access_token = tokens.get("access_token", "")
                    if access_token:
                        payload = jwt.get_unverified_claims(access_token)
                        scope_string = payload.get("scope", "")
                        if "MutualFunds" in scope_string:
                            return "MutualFunds"
                        if "Assets" in scope_string:
                            return "Assets"
                        if "Wealth" in scope_string:
                            return "Wealth"
                        if "General" in scope_string:
                            return "General"
                        if "ACCOUNT_MANAGER" in scope_string:
                            return "ACCOUNT_MANAGER"
        except:
            pass
        return "unauthorized"

@st.cache_resource
def get_supervisor(_config_hash=None):
    """Load and cache the supervisor agent.
    The _config_hash parameter ensures cache is invalidated when config changes.
    """
    return load_supervisor_agent()

def get_supervisor_with_invalidation():
    """Get supervisor agent, using config file hash to invalidate cache."""
    config_path = os.path.join(os.path.dirname(__file__), "supervisor_config.yaml")
    try:
        import hashlib
        with open(config_path, "rb") as f:
            config_hash = hashlib.md5(f.read()).hexdigest()
        return get_supervisor(config_hash)
    except:
        return get_supervisor(0)

# Initialize session state
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

# Available agents info
AVAILABLE_AGENTS = [
    "🤖 Position Agent - Calculates positions, submits orders, fetches NAV data",
    "📋 Order Details Agent - Handles general trade order details and routing",
    "📤 Order Ingestion Agent - Handles file uploads and trade simulations",
    "🔐 Authorization Agent - Handles authorization inquiries and token validation"
]

st.title("🤖 DTCC Multi-Agent Supervisor")
st.caption("Unified interface for all specialized agents")

# Login Section (if not logged in)
if not st.session_state.logged_in:
    with st.container():
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.subheader("🔐 Keycloak Authentication")
            
            username = st.text_input("Username", key="login_username")
            password = st.text_input("Password", type="password", key="login_password")
            
            if st.button("Login", type="primary"):
                tokens, error = login(username, password)
                if tokens:
                    st.session_state.tokens = tokens
                    st.session_state.logged_in = True
                    # Save to session.json for Authorization Agent
                    try:
                        session_path = os.path.join(os.path.dirname(__file__), "session.json")
                        with open(session_path, "w") as f:
                            json.dump(tokens, f, indent=4)
                        # Also save to Authorization_Agent directory
                        auth_agent_dir = os.path.join(os.path.dirname(__file__), "..", "Authorization_Agent")
                        auth_session_path = os.path.join(auth_agent_dir, "session.json")
                        with open(auth_session_path, "w") as f:
                            json.dump(tokens, f, indent=4)
                    except Exception as e:
                        st.warning(f"Could not save session: {e}")
                    
                    # Extract scope from token
                    try:
                        scope = extract_scope_from_token()
                        st.session_state.scope = scope
                    except:
                        st.session_state.scope = "unauthorized"
                    
                    st.success("✅ Login successful!")
                    st.rerun()
                else:
                    st.error(f"❌ Login failed: {error}")
    
    st.info("👆 Please login or enter a token to continue")
    st.stop()

# Main Chat Interface
with st.sidebar:
    if os.path.exists("dtcc_logo.png"):
        st.image("dtcc_logo.png", use_container_width=True)
    
    st.header("⚙️ Configuration")
    
    # Show login status
    if st.session_state.tokens:
        st.success("✅ Authenticated via Keycloak")
        # Extract and display current scope
        try:
            current_scope = extract_scope_from_token()
            st.session_state.scope = current_scope
            st.info(f"**Current Scope:** {current_scope}")
        except:
            st.warning("Could not extract scope from token")
        
        if st.button("Logout"):
            st.session_state.tokens = None
            st.session_state.logged_in = False
            st.session_state.scope = "unauthorized"
            # Clear session.json
            try:
                session_path = os.path.join(os.path.dirname(__file__), "session.json")
                if os.path.exists(session_path):
                    os.remove(session_path)
            except:
                pass
            st.rerun()
    else:
        st.warning("⚠️ Please login via Keycloak to access agents")
    
    st.divider()
    
    st.subheader("📋 Available Agents")
    for agent in AVAILABLE_AGENTS:
        st.markdown(f"• {agent}")
    
    st.divider()
    
    st.info(f"**Active Scope:** {st.session_state.scope}")
    st.info(f"**Thread ID:** {st.session_state.thread_id[:8]}...")
    
    if st.button("🗑️ Clear History"):
        st.session_state.messages = []
        st.session_state.thread_id = str(uuid.uuid4())
        # Clear supervisor cache
        get_supervisor.clear()
        st.rerun()
    
    if st.button("🔄 Reload Supervisor"):
        """Reload supervisor agent (clears cache and reloads config)."""
        get_supervisor.clear()
        st.success("✅ Supervisor reloaded! Configuration refreshed.")
        st.rerun()

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# File Upload Section (in chat area)
st.divider()
with st.expander("📤 Upload File", expanded=False):
    st.caption("Upload files for trade simulation (CSV, ZIP, TXT, JSON, XML, DAT)")
    
    uploaded_file = st.file_uploader(
        "Choose a file",
        type=["csv", "zip", "txt", "json", "xml", "dat"],
        key="file_uploader"
    )
    
    if uploaded_file is not None:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.info(f"📄 **{uploaded_file.name}** ({uploaded_file.size / 1024:.2f} KB)")
        with col2:
            if st.button("Upload", type="primary", key="upload_btn"):
                try:
                    # Create files directory if it doesn't exist
                    files_dir = os.path.join(os.path.dirname(__file__), "..", "files")
                    os.makedirs(files_dir, exist_ok=True)
                    
                    # Save the uploaded file
                    file_path = os.path.join(files_dir, uploaded_file.name)
                    with open(file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    
                    # Send request to order_ingestion_agent via chat
                    upload_request = f"upload {uploaded_file.name}"
                    
                    # Add to session state messages
                    st.session_state.messages.append({
                        "role": "user", 
                        "content": f"📤 Uploading file: {uploaded_file.name}"
                    })
                    
                    # Process through supervisor
                    with st.spinner("Processing file upload..."):
                        supervisor = get_supervisor_with_invalidation()
                        config = {"configurable": {"thread_id": st.session_state.thread_id}}
                        
                        response_text = ""
                        for params in supervisor.stream(
                            {"messages": [{"role": "user", "content": upload_request}]},
                            config,
                        ):
                            for node_name, update in params.items():
                                if "messages" in update:
                                    last_msg = update["messages"][-1]
                                    if hasattr(last_msg, "content") and last_msg.type == "ai":
                                        response_text = last_msg.content
                        
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": response_text or f"✅ File {uploaded_file.name} uploaded successfully"
                        })
                        
                        st.success(f"✅ File {uploaded_file.name} processed!")
                        st.rerun()
                        
                except Exception as e:
                    st.error(f"❌ Upload failed: {str(e)}")
st.divider()

# Chat input
if prompt := st.chat_input("Ask the supervisor agent... (connects to all specialized agents)"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        # Get supervisor with cache invalidation based on config file
        supervisor = get_supervisor_with_invalidation()
        config = {"configurable": {"thread_id": st.session_state.thread_id}}
        
        # Contextualize prompt with scope
        full_prompt = f"[Context: {st.session_state.scope}] {prompt}"
        
        response_placeholder = st.empty()
        status_placeholder = st.empty()
        status_placeholder.info("🔄 Processing request through supervisor agent...")
        
        full_response = ""
        agent_used = None
        
        # Stream response from Supervisor
        try:
            for params in supervisor.stream(
                {"messages": [{"role": "user", "content": full_prompt}]},
                config,
            ):
                for node_name, update in params.items():
                    # Track which agent/tool is being used
                    if node_name and "agent" in node_name.lower():
                        agent_used = node_name
                        status_placeholder.info(f"🔄 Using: {node_name}")
                    
                    if "messages" in update:
                        # Get the last message from the update
                        last_msg = update["messages"][-1]
                        
                        # Display AI messages
                        if hasattr(last_msg, "content") and last_msg.type == "ai":
                            chunk = last_msg.content
                            # If content is a list (multimodal?), join it
                            if isinstance(chunk, list):
                                chunk = " ".join([c.get("text", "") for c in chunk if "text" in c])
                            
                            full_response = chunk
                            response_placeholder.markdown(full_response)
                        
                        # Display tool messages (show which agent was called and output)
                        elif hasattr(last_msg, "type") and last_msg.type == "tool":
                            tool_name = getattr(last_msg, "name", "Unknown tool")
                            if tool_name and "agent" in tool_name.lower():
                                agent_used = tool_name
                                status_placeholder.info(f"🔧 Calling: {tool_name}")
                                
                                # Show tool output for debugging
                                with st.expander(f"Tool Output: {tool_name}", expanded=False):
                                    st.code(last_msg.content, language="markdown")
        
        except Exception as e:
            full_response = f"❌ Error: {str(e)}"
            response_placeholder.error(full_response)
            status_placeholder.error("❌ Request failed")
        
        # Clear status and show final response
        status_placeholder.empty()
        if agent_used:
            st.caption(f"✅ Processed via: {agent_used}")
        
        st.session_state.messages.append({"role": "assistant", "content": full_response})
