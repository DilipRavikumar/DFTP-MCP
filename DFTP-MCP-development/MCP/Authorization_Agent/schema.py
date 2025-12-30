from typing import List, TypedDict, Optional

class State(TypedDict):
    prompt: str
    token: str
    result: Optional[str]
    scope: Optional[str]
    roles: Optional[List[str]]