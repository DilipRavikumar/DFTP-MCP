import httpx
from fastmcp import FastMCP

def create_server():
    try:
        # Create an HTTP client for your API
        client = httpx.AsyncClient(base_url="http://localhost:8080/")

        # Load your OpenAPI spec 
        openapi_spec = httpx.get("http://localhost:8080/v3/api-docs").json()

        # Create the MCP server
        mcp = FastMCP.from_openapi(
            openapi_spec=openapi_spec,
            client=client,
            name="PositionService"
        )
        return mcp
    except Exception as e:
        print(f"Warning: Could not connect to PositionService API: {e}")
        # Return a dummy or minimal server if connection fails to allow import
        return FastMCP("PositionService_Fallback")

if __name__ == "__main__":
    mcp = create_server()
    # Position Agent MCP Server - Port 8001
    mcp.run(transport="streamable-http", host="127.0.0.1", port=8001)
