from fastapi import FastAPI, Response, Request, HTTPException
from fastapi.responses import RedirectResponse
import requests
import jwt
import logging

app = FastAPI()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

KEYCLOAK_URL = "http://localhost:8180"
REALM = "authentication"
CLIENT_ID = "public-client"
GATEWAY_CALLBACK = "http://localhost:8081/api/auth/callback"
FRONTEND_CALLBACK = "http://localhost:4200/login-callback"
KEYCLOAK_PUBLIC_KEY = "YOUR_KEYCLOAK_PUBLIC_KEY_HERE"

@app.get("/api/auth/login")
def login():
    keycloak_login_url = (
        f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/auth"
        f"?client_id={CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={GATEWAY_CALLBACK}"
    )
    return RedirectResponse(keycloak_login_url)


@app.get("/api/auth/logout")
def logout():
    response = RedirectResponse(
        url=(
            f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/logout"
            f"?client_id={CLIENT_ID}"
            f"&post_logout_redirect_uri=http://localhost:4200"
        )
    )
    response.delete_cookie("access_token", path="/")
    return response


@app.get("/api/auth/callback")
def callback(code: str = None):
    if not code:
        return RedirectResponse(FRONTEND_CALLBACK)

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
    access_token = token_data.get("access_token")

    if not access_token:
        raise HTTPException(status_code=401, detail="Access token missing")

    logger.info("Access token received, setting cookie")

    redirect_response = RedirectResponse(
        url=FRONTEND_CALLBACK,
        status_code=302
    )

    redirect_response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False, 
        samesite="Lax",
        path="/"
    )

    return redirect_response


@app.get("/api/auth/me")
def me(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        logger.info("No access_token found in cookies.")
        return {"authenticated": False, "scope": "General"}

    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        logger.info(f"Token payload: {payload}")

        user_scope = payload.get("scope", "General")

        logger.info(f"User scope: {user_scope}")

    except Exception as e:
        logger.error(f"Error decoding token: {e}")
        return {
            "authenticated": False,
            "scope": "General",
            "error": str(e)
        }

    return {
        "authenticated": True,
        "scope": user_scope
    }

