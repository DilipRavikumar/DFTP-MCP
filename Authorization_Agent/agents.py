import json
import boto3
from result import get_service_result
from auth_service import get_scope_from_token
from schema import State

# Initialize Bedrock client (add AWS credentials as needed)
bedrock = boto3.client('bedrock-runtime', region_name='us-east-2')

def call_nova_llm(prompt):
    body = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "text": prompt
                    }
                ]
            }
        ],
        "inferenceConfig": {
            "maxTokens": 512,
            "temperature": 0.2
        }
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
        # Example: prompt="request:get status, token:LIC_123"
        token = user_prompt.split("token:")[1].split(",")[0].strip()
    except:
        token = ""
    scope = get_scope_from_token(token)
    return token, scope

def MCPAgent_Node(state: State) -> State:
    scope = state["scope"]
    user_prompt = state["prompt"]

    try:
        query = user_prompt.split(",", 1)[1].strip()
    except:
        query = user_prompt 

    service_result = get_service_result(scope, query)

    final_prompt = (
        f"You are a {scope} assistant. The service returned this:\n{service_result}\n"
        f"Now answer the user's query: {query}"
    )
    final_output = call_nova_llm(final_prompt)
    
    return {**state, "result": final_output}