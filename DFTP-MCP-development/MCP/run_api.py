import sys
import os
import uvicorn

# Ensure the current directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

if __name__ == "__main__":
    print("Starting DFTP-MCP Backend...")
    try:
        # Import here to check for errors immediately
        from supervisor_agent.api import app
        print("Successfully imported API app.")
        uvicorn.run("supervisor_agent.api:app", host="127.0.0.1", port=8001, reload=True)
    except Exception as e:
        print(f"FAILED to start: {e}")
        import traceback
        traceback.print_exc()
