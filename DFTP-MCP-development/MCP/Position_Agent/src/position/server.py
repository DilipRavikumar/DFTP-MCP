import httpx
from fastmcp import FastMCP

def create_server():
    try:
        client = httpx.AsyncClient(base_url="http://localhost:8080/")

        openapi_spec = httpx.get("http://localhost:8080/v3/api-docs").json()

        mcp = FastMCP.from_openapi(
            openapi_spec=openapi_spec,
            client=client,
            name="PositionService"
        )
        return mcp
    except Exception as e:
        print(f"Warning: Could not connect to PositionService API: {e}")
        return FastMCP("PositionService_Fallback")

if __name__ == "__main__":
    mcp = create_server()
    mcp.run(transport="streamable-http", host="127.0.0.1", port=8000)
