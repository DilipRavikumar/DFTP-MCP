from fastapi import FastAPI, Response, Request, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
import requests
import httpx
import jwt
import logging

app = FastAPI()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

origins = [
    "http://localhost:4200",
    "http://localhost:8081",
    "http://localhost:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

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
        f"&redirect_uri={GATEWAY_CALLBACK}" 
    )
    return RedirectResponse(keycloak_login_url)


@app.get("/api/auth/logout")
def logout():
    logout_url = (
        f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/logout"
        f"?client_id={CLIENT_ID}"
        f"&post_logout_redirect_uri=http://localhost:8081/api/auth/post-logout"
    )
    response = RedirectResponse(url=logout_url)

    for cookie_name in ["access_token", "user_id", "username", "roles", "scope"]:
        response.delete_cookie(cookie_name, path="/", domain="localhost")

    return response

@app.get("/api/auth/post-logout")
def post_logout():
    return RedirectResponse(url="http://localhost:4200")

@app.get("/api/auth/callback")
def callback(code: str = None):
    if not code:
        logger.error("No code received from Keycloak")
        return RedirectResponse("http://localhost:4200/login-error")

    try:
        payload = {
            "client_id": CLIENT_ID,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": "http://localhost:8081/api/auth/callback" # MUST MATCH LOGIN
        }
        
        token_response = requests.post(
            f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/token",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10
        )
        if token_response.status_code != 200:
            logger.error(f"Keycloak exchange failed: {token_response.text}")
            raise HTTPException(status_code=400, detail=token_response.text)

        token_data = token_response.json()
        access_token = token_data.get("access_token")

        response = RedirectResponse(url="http://localhost:4200/login-callback")
        
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=False, 
            samesite="lax",
            path="/"
        )
        return response

    except Exception as e:
        logger.error(f"Callback Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/auth/me")
async def me(request: Request):
    user_id = request.headers.get("X-User-Id")
    if not user_id:
        return {"authenticated": False}

    return {
        "authenticated": True,
        "user_id": user_id,
        "username": request.headers.get("X-Username"),
        "roles": request.headers.get("X-User-Roles", "").split(",") if request.headers.get("X-User-Roles") else [],
        "scope": request.headers.get("X-User-Scope", "")
    }


# @app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
# async def proxy(request: Request, path: str):
#     if request.method == "OPTIONS":
#         return Response(status_code=204)

#     token = request.cookies.get("access_token")
#     user_context = {}
    
#     if token:
#         try:
#             payload = jwt.decode(token, options={"verify_signature": False})
#             user_context = {
#                 "user_id": payload.get("sub", "anonymous"),
#                 "role": "user", # Default or extract from payload
#                 "scope": payload.get("scope", "").split(" ")
#             }
#         except Exception as e:
#             logger.error(f"Token decode error: {e}")
    
#     target_url = f"http://localhost:2024/{path}"
    
#     headers = dict(request.headers)
#     headers.pop("host", None)
#     if token and "authorization" not in headers:
#         headers["authorization"] = f"Bearer {token}"
        
#     async with httpx.AsyncClient() as client:
#         try:
#             body = await request.body()
            
#             proxy_res = await client.request(
#                 method=request.method,
#                 url=target_url,
#                 headers=headers,
#                 content=body,
#                 params=request.query_params,
#                 timeout=60.0
#             )
#             response = Response(
#                 content=proxy_res.content,
#                 status_code=proxy_res.status_code,
#                 headers=dict(proxy_res.headers)
#             )
#             return response
            
#         except Exception as e:
#             logger.error(f"Proxy error: {e}")
#             raise HTTPException(status_code=502, detail=f"Backend unavailable: {e}")
