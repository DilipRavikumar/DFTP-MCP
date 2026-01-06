from fastapi import FastAPI
from fastapi.responses import RedirectResponse
import requests

app = FastAPI()

KEYCLOAK_URL = "http://localhost:8180"
REALM = "authentication"
CLIENT_ID = "public-client"


GATEWAY_CALLBACK = "http://localhost:8081/api/auth/callback"
FRONTEND_CALLBACK = "http://localhost:4200/login-callback"

@app.get("/api/auth/login")
def login():
    keycloak_login_url = (
        f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/auth"
        f"?client_id={CLIENT_ID}"
        f"&response_type=code"
        f"&scope=openid"
        f"&redirect_uri={GATEWAY_CALLBACK}"
    )
    return RedirectResponse(keycloak_login_url)

@app.get("/api/auth/callback")
def callback(code: str):
    token_response = requests.post(
        f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/token",
        data={
            "client_id": CLIENT_ID,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": GATEWAY_CALLBACK
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )

    token_response.raise_for_status()
    token_data = token_response.json()

    access_token = token_data["access_token"]

    return RedirectResponse(
        f"{FRONTEND_CALLBACK}?token={access_token}"
    )
