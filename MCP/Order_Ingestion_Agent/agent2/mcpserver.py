import httpx
from fastmcp import FastMCP
from typing import Any
import json


def remove_none_values(data: Any) -> Any:
    """Recursively remove None values from dicts and lists."""
    if isinstance(data, dict):
        return {k: remove_none_values(v) for k, v in data.items() if v is not None}
    elif isinstance(data, list):
        return [remove_none_values(item) for item in data if item is not None]
    else:
        return data


class ResponseCleaningAsyncClient(httpx.AsyncClient):
    """AsyncClient wrapper that removes None values from JSON responses."""
    
    async def request(self, *args, **kwargs):
        response = await super().request(*args, **kwargs)
        
        # Try to clean the response JSON if it exists
        if response.status_code == 200 and "application/json" in response.headers.get("content-type", ""):
            try:
                data = response.json()
                cleaned = remove_none_values(data)
                # Create a new response with cleaned data
                cleaned_json = json.dumps(cleaned)
                response._content = cleaned_json.encode('utf-8')
                response.headers['content-length'] = str(len(response._content))
            except Exception:
                # If cleaning fails, return original response
                pass
        
        return response


def main():
    trade_capture_server: FastMCP = setup_fastmcp_server_from_openapi_spec(
        spec_link="http://localhost:8088/api-docs",
        base_url="http://localhost:8088",
        server_name="Trade Capture MCP Server",
    )

    trade_simulate_server: FastMCP = setup_fastmcp_server_from_openapi_spec(
        spec_link="http://localhost:8081/v3/api-docs",
        base_url="http://localhost:8081",
        server_name="Trade Simulate MCP Server",
    )

    main_server: FastMCP = FastMCP(name="Gateway MCP Server")
    main_server.mount(trade_capture_server)
    main_server.mount(trade_simulate_server, as_proxy=True, prefix="trade simulation")

    # Order Ingestion Agent MCP Server - Port 8003
    main_server.run(transport="streamable-http", host="0.0.0.0", port=8003)


def setup_fastmcp_server_from_openapi_spec(
    spec_link: str,
    base_url: str,
    server_name: str,
) -> FastMCP:
    open_api_spec = httpx.get(
        spec_link,
    ).json()

    # Use the custom client that cleans responses
    client = ResponseCleaningAsyncClient(base_url=base_url)

    return FastMCP.from_openapi(
        openapi_spec=open_api_spec,
        client=client,
        name=server_name,
    )


if __name__ == "__main__":
    main()
