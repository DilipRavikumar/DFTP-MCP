import os
import boto3
from typing import TypedDict
from langgraph.graph import StateGraph, END
from dotenv import load_dotenv
import streamlit as st

load_dotenv()

st.set_page_config(page_title="DTCC MCP Chatbot", page_icon="💬")

with open("style.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

MOCK_TOKENS = {
    "t-111": {"scope": "Assets"},
    "t-222": {"scope": "Wealth"},
    "t-333": {"scope": "General"},
}

def mock_token_service(token: str):
    return MOCK_TOKENS.get(token)

class AgentState(TypedDict):
    token: str
    user_message: str
    scope: str
    error: str

bedrock = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-2"))

def validate_token(state: AgentState) -> AgentState:
    token_input = state["token"]
    token_info = mock_token_service(token_input)

    if not token_info:
        state["error"] = "❌ Invalid token. Please check your token in the sidebar."
        return state

    state["scope"] = token_info["scope"]
    return state

graph = StateGraph(AgentState)
graph.add_node("validate_token", validate_token)
graph.set_entry_point("validate_token")
graph.add_edge("validate_token", END)
compiled_graph = graph.compile()

def stream_nova_pro(scope: str, messages: list):
    system_prompt = f"You are the {scope} agent for DTCC. Answer helpfuly and professionally."
    
    bedrock_messages = []
    for msg in messages:
        role = "user" if msg["role"] == "user" else "assistant"
        bedrock_messages.append({
            "role": role,
            "content": [{"text": msg["content"]}]
        })

    model_id = os.getenv("BEDROCK_MODEL_ID", "arn:aws:bedrock:us-east-2:254800774891:inference-profile/us.amazon.nova-pro-v1:0")

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

st.title("DTCC Context-Aware Chat")

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

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

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
            
            response_placeholder = st.empty()
            full_response = ""
            
            for chunk in stream_nova_pro(scope, st.session_state.messages):
                full_response += chunk
                response_placeholder.markdown(full_response + "▌")
            
            response_placeholder.markdown(full_response)
            status_placeholder.empty()
            
            st.session_state.messages.append({"role": "assistant", "content": full_response})
