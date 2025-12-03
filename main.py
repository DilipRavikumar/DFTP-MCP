import httpx
from fastmcp import FastMCP
from urllib.parse import urlparse


def main():
    petstore_server: FastMCP = setup_fastmcp_server_from_openapi_spec(
        spec_link="https://petstore3.swagger.io/api/v3/openapi.json",
        base_url="https://petstore3.swagger.io/api/v3",
        server_name="Petstore MCP Server",
    )

    tenable_server: FastMCP = setup_fastmcp_server_from_openapi_spec(
        spec_link="https://developer.tenable.com/openapi/5c926ae6a9b73900ee2740cb",
        base_url="https://www.tenable.com/downloads/api/v2",
        server_name="Tenable MCP Server",
    )

    canonical_server: FastMCP = setup_fastmcp_server_from_openapi_spec(
        spec_link="http://3.21.93.130:8085/v3/api-docs",
        base_url="http://3.21.93.130:8085", 
        server_name="Canonical MCP Server",
    )


    main_server: FastMCP = FastMCP(name="Gateway MCP Server")
    main_server.mount(tenable_server, as_proxy=True, prefix="tenable")
    main_server.mount(petstore_server)
    main_server.mount(canonical_server, as_proxy=True, prefix="canonical")

    main_server.run(transport="streamable-http", host="0.0.0.0", port=8000)


def _normalize_base_url(url: str) -> str:
    """Ensure base URL has a protocol (http:// or https://)"""
    if not url:
        return url
    url = url.strip().rstrip("/")
    if not url.startswith(("http://", "https://")):
        # Default to https if no protocol specified
        url = f"https://{url}"
    return url

def setup_fastmcp_server_from_openapi_spec(
    spec_link: str,
    base_url: str,
    server_name: str,
) -> FastMCP:
    open_api_spec = httpx.get(
        spec_link,
    ).json()

    # Normalize base_url to ensure it has a protocol
    normalized_base_url = _normalize_base_url(base_url)
    
    # Update the servers section in the OpenAPI spec to use the full base_url
    open_api_spec["servers"] = [{"url": normalized_base_url.rstrip("/")}]

    # Create httpx client with proper configuration
    timeout_config = httpx.Timeout(30.0, connect=10.0, read=30.0, write=10.0, pool=10.0)
    client = httpx.AsyncClient(
        base_url=normalized_base_url,
        timeout=timeout_config,
        follow_redirects=True,
        verify=True,  # SSL verification
        limits=httpx.Limits(max_keepalive_connections=10, max_connections=20)
    )

    return FastMCP.from_openapi(
        openapi_spec=open_api_spec,
        client=client,
        name=server_name,
    )


if __name__ == "__main__":
    main()
