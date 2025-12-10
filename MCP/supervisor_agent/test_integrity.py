import sys
import os

# Add parent dir
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

print("Starting integrity check...", flush=True)

print("Checking Order_Ingestion_Agent...", flush=True)
try:
    from Order_Ingestion_Agent.agent2.TradeSimulateSpecific import process_request as func1
    print("MATCH: Order_Ingestion_Agent.process_request found.", flush=True)
except ImportError as e:
    print(f"FAIL: Order_Ingestion_Agent - {e}", flush=True)
except Exception as e:
    print(f"ERROR: Order_Ingestion_Agent - {e}", flush=True)

print("Checking Order_Details_Agent...", flush=True)
try:
    from Order_Details_Agent.agent1.TradeGeneralAgent import process_request as func2
    print("MATCH: Order_Details_Agent.process_request found.", flush=True)
except ImportError as e:
    print(f"FAIL: Order_Details_Agent - {e}", flush=True)

print("Checking Position_Agent...", flush=True)
try:
    from Position_Agent.src.position.main import process_request as func3
    print("MATCH: Position_Agent.process_request found.", flush=True)
except ImportError as e:
    print(f"FAIL: Position_Agent - {e}", flush=True)

print("Integrity check complete.", flush=True)

