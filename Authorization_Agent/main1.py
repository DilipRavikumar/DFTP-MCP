
import sys
from build import build_graph

if len(sys.argv) < 2:
    sys.exit()

user_prompt = " ".join(sys.argv[1:])
app = build_graph()
final_state = app.invoke({"prompt": user_prompt})

print(final_state["result"])
