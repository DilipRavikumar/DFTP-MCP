import httpx
import json
import base64
from typing import Any
from fastmcp import FastMCP


# =====================================================
# UTIL: CLEAN JSON RESPONSES
# =====================================================
def remove_none_values(data: Any) -> Any:
    if isinstance(data, dict):
        return {k: remove_none_values(v) for k, v in data.items() if v is not None}
    elif isinstance(data, list):
        return [remove_none_values(item) for item in data if item is not None]
    else:
        return data


class ResponseCleaningAsyncClient(httpx.AsyncClient):
    async def request(self, *args, **kwargs):
        response = await super().request(*args, **kwargs)

        if (
            response.status_code == 200
            and "application/json" in response.headers.get("content-type", "")
        ):
            try:
                data = response.json()
                cleaned = remove_none_values(data)
                cleaned_json = json.dumps(cleaned)
                response._content = cleaned_json.encode("utf-8")
                response.headers["content-length"] = str(len(response._content))
            except Exception:
                pass

        return response


# =====================================================
# OPENAPI → MCP SERVER
# =====================================================
def setup_fastmcp_server_from_openapi_spec(
    spec_link: str,
    base_url: str,
    server_name: str,
) -> FastMCP:
    open_api_spec = httpx.get(spec_link).json()
    client = ResponseCleaningAsyncClient(base_url=base_url)

    return FastMCP.from_openapi(
        openapi_spec=open_api_spec,
        client=client,
        name=server_name,
    )


# =====================================================
# MAIN GATEWAY SERVER
# =====================================================
def main():
    trade_capture_server = setup_fastmcp_server_from_openapi_spec(
        spec_link="http://localhost:8088/api-docs",
        base_url="http://localhost:8088",
        server_name="Trade Capture MCP Server",
    )

    trade_simulate_server = setup_fastmcp_server_from_openapi_spec(
        spec_link="http://localhost:8081/v3/api-docs",
        base_url="http://localhost:8081",
        server_name="Trade Simulate MCP Server",
    )

    data_api_server = setup_fastmcp_server_from_openapi_spec(
        spec_link="http://localhost:8080/v3/api-docs",
        base_url="http://localhost:8080",
        server_name="Data API MCP Server",
    )


    main_server = FastMCP(name="Gateway MCP Server")
    main_server.mount(data_api_server)
    main_server.mount(trade_capture_server)
    main_server.mount(trade_simulate_server)   # /simulate/run

    main_server.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=8000,
    )


if __name__ == "__main__":
    main()
