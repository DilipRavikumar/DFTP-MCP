def get_scope_from_token(token: str) -> str:
    if token.startswith("LIC_"):
        return "LIC"
    elif token.startswith("MF_"):
        return "MF"
    else:
        return "unauthorized"
