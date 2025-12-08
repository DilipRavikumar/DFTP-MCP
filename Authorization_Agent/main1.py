import sys
from build import build_graph

if len(sys.argv) < 2:
    print("Error: Please provide a prompt as an argument")
    print("Usage: python main1.py <prompt>")
    sys.exit(1)

user_prompt = " ".join(sys.argv[1:])
print(f"Processing prompt: {user_prompt}\n")

try:
    app = build_graph()
    final_state = app.invoke({"prompt": user_prompt})
    print("\n" + "="*50)
    print(final_state["result"])
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)

#example usage: python Authorization_Agent/main1.py  "token:LIC_, request: get status of Mutual Funds"                        