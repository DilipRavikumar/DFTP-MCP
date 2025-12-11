import json
import boto3
from result import get_service_result
from auth_service import get_scope_from_token, get_roles_from_token
from schema import State

bedrock = boto3.client('bedrock-runtime', region_name='us-east-2')

def call_nova_llm(prompt):
    body = {
        "messages": [
            {"role": "user", "content": [{"text": prompt}]}
        ],
        "inferenceConfig": {"maxTokens": 512, "temperature": 0.2}
    }

    response = bedrock.invoke_model(
        modelId="arn:aws:bedrock:us-east-2:254800774891:inference-profile/us.amazon.nova-pro-v1:0",
        accept="application/json",
        contentType="application/json",
        body=json.dumps(body)
    )

    result = json.loads(response["body"].read())
    return result["output"]["message"]["content"][0]["text"]


def extract_token_and_scope(user_prompt: str):
    try:
        # Try multiple locations for session.json
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Try current directory (Authorization_Agent)
        session_path = os.path.join(current_dir, "session.json")
        if not os.path.exists(session_path):
            # Try parent directory (MCP root)
            parent_dir = os.path.dirname(current_dir)
            session_path = os.path.join(parent_dir, "session.json")
        if not os.path.exists(session_path):
            # Try supervisor_agent directory
            supervisor_dir = os.path.join(parent_dir, "supervisor_agent")
            session_path = os.path.join(supervisor_dir, "session.json")
        
        if os.path.exists(session_path):
            with open(session_path, "r") as f:
                tokens = json.load(f)
            token = tokens.get("access_token", "")
        else:
            token = ""
    except:
        token = ""

    scope = get_scope_from_token(token)
    roles = get_roles_from_token(token)

    return token, scope, roles


def MCPAgent_Node(state: State) -> State:
    scope = state["scope"]
    roles = state["roles"]
    user_prompt = state["prompt"]

    query = user_prompt

    service_result = get_service_result(scope, query)

    final_prompt = (
        f"You are a {scope} assistant.\n"
        f"User roles: {roles}\n"
        f"Service output: {service_result}\n"
        f"Now answer the user's query: {query}"
    )

    final_output = call_nova_llm(final_prompt)

    return {**state, "result": final_output}
