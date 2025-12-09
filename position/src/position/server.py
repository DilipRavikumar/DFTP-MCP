import httpx
from fastmcp import FastMCP

# Create an HTTP client for your API
client = httpx.AsyncClient(base_url="http://localhost:8080/")

# Load your OpenAPI spec 
openapi_spec = httpx.get("http://localhost:8080/v3/api-docs").json()

# Create the MCP server
mcp = FastMCP.from_openapi(
    openapi_spec=openapi_spec,
    client=client,
    name="Petstore"
)

if __name__ == "__main__":
    mcp.run(transport="streamable-http",host="127.0.0.1",port=8000)