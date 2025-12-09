from langgraph.graph import StateGraph, END
from typing import TypedDict, Dict, Any
import boto3
import json
import streamlit as st

MOCK_TOKENS = {
    "t-111": {"scope": "Assets"},
    "t-222": {"scope": "Wealth"},
    "t-333": {"scope": "General"},
}


def mock_token_service(token: str):
    """Fake token validator service."""
    return MOCK_TOKENS.get(token)

class AgentState(TypedDict):
    token: str
    user_message: str
    scope: str
    fm_response: str
    error: str

bedrock = boto3.client("bedrock-runtime", region_name="us-east-2")

st.title("MCP Chatbot")


def call_nova_pro(prompt: str):
    """Call Nova Pro model on AWS Bedrock using the Converse API."""

    response = bedrock.converse(
        modelId="arn:aws:bedrock:us-east-2:254800774891:inference-profile/us.amazon.nova-pro-v1:0",
        messages=[{"role": "user", "content": [{"text": prompt}]}]
    )

    try:
        return response["output"]["message"]["content"][0]["text"]
    except:
        return "No response from model"

def validate_token(state: AgentState) -> AgentState:
    token = state["token"]
    token_info = mock_token_service(token)

    if not token_info:
        state["error"] = "❌ Invalid token"
        return state

    state["scope"] = token_info["scope"]
    return state

def call_foundation_model(state: AgentState) -> AgentState:
    if state.get("error"):
        return state

    scope = state["scope"]
    msg = state["user_message"]

    prompt = f"""
You are the {scope} agent.
User message: {msg}
Respond appropriately.
"""

    fm_output = call_nova_pro(prompt)
    state["fm_response"] = fm_output
    return state

graph = StateGraph(AgentState)
graph.add_node("validate_token", validate_token)
graph.add_node("call_foundation_model", call_foundation_model)

graph.set_entry_point("validate_token")
graph.add_edge("validate_token", "call_foundation_model")
graph.add_edge("call_foundation_model", END)

compiled_graph = graph.compile()

token = st.text_input("Enter your token")

def generate_response(user_message: str):
    
    state = {
        "token": token,
        "user_message": user_message,
        "scope": "",
        "fm_response": "",
        "error": ""
    }

    result = compiled_graph.invoke(state)

    if result.get("error"):
        st.error(result["error"])
    else:
        st.success("Response Generated:")
        st.write(f"Scope: {result['scope']}")
        st.write(f"Model Response: {result['fm_response']}")

with st.form("my_form"):
    text = st.text_area(
        "Enter text:",
        "What are the three key pieces of advice for learning how to code?",
    )
    submitted = st.form_submit_button("Submit")
    if submitted:
        generate_response(text)

