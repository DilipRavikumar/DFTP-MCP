import sys
from build import build_graph
from schema import State

def run():
    """Run the authorization agent with a prompt from command line."""
    if len(sys.argv) < 2:
        print("Error: Provide a prompt")
        sys.exit(1)

    user_prompt = " ".join(sys.argv[1:])
    print(f"Processing prompt: {user_prompt}")

    try:
        app = build_graph()
        final_state = app.invoke({"prompt": user_prompt})
        print("\n" + "="*50)
        print(final_state["result"])
        
    except Exception as e:
        print("Error:", e)

# Only execute when run as script, not when imported
if __name__ == "__main__":
    run()
