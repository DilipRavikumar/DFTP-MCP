import json
import boto3
from result import get_service_result
from auth_service import get_role_from_token

# add bedrock client code (with the aws credentials i removed it for security reasons while pushing in the git)

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
        modelId="amazon.nova-pro-v1:0",
        accept="application/json",
        contentType="application/json",
        body=json.dumps(body)
    )

    result = json.loads(response["body"].read())
    return result["output"]["message"]["content"][0]["text"]



def llm_agent(user_prompt: str) -> str:
    try:
        token = user_prompt.split("token:")[1].split(",")[0].strip()
    except:
        token = ""
    role = get_role_from_token(token)
    try:
        query = user_prompt.split(",", 1)[1].strip()
    except:
        query = user_prompt
    service_result = get_service_result(role, query)


    final_prompt = (
        f"You are a {role} assistant. The service returned this:\n{service_result}\n"
        f"Now answer the user's query: {query}"
    )
    final_output = call_nova_llm(final_prompt)
    return final_output
