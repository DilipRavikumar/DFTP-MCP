from typing import TypedDict, Optional

class State(TypedDict):
    prompt: str
    result: Optional[str]
    scope: Optional[str]