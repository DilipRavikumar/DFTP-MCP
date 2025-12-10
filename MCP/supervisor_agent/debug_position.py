import sys
import os
import traceback

# Add parent dir to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from Position_Agent.src.position.main import process_request

print("--- Starting Debug of Position Agent ---")
try:
    query = "Check the validity and scope of token LIC_123"
    print(f"Query: {query}")
    result = process_request(query)
    print("--- Result ---")
    print(result)
except Exception:
    print("--- Exception ---")
    traceback.print_exc()
