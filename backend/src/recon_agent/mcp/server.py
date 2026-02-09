import json
from pathlib import Path


import httpx
from fastmcp import FastMCP


def load_config(config_path: str = "server_config.json") -> dict:
    """Load MCP server configuration from a JSON file."""
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")


    with config_file.open() as f:
        return json.load(f)


def setup_fastmcp_server_from_openapi_spec(
    *,
    spec_link: str,
    base_url: str,
    server_name: str,
) -> FastMCP:
    """
    Create a FastMCP server from an OpenAPI specification,
    excluding tools tagged as 'internal' (e.g. triggeredadhoc).
    """
    openapi_spec = httpx.get(spec_link, timeout=30).json()


    client = httpx.AsyncClient(base_url=base_url)


    return FastMCP.from_openapi(
        openapi_spec=openapi_spec,
        client=client,
        name=server_name,
        exclude_tags={"Ad-hoc Reconciliation"},
    )


def start_server(server_config: dict) -> FastMCP | None:
    """Create a FastMCP server from config."""
    server_name = server_config.get("server_name")
    spec_link = server_config.get("spec_link")
    base_url = server_config.get("base_url")


    if not all([server_name, spec_link, base_url]):
        print(f"Skipping incomplete server config: {server_config}")
        return None


    try:
        return setup_fastmcp_server_from_openapi_spec(
            spec_link=spec_link,
            base_url=base_url,
            server_name=server_name,
        )
    except Exception as e:
        print(f"Failed to start server '{server_name}': {e}")
        return None


def main() -> None:
    """Entry point for the Recon MCP Server."""
    try:
        config = load_config("server_config.json")


        # Main aggregator server
        main_server = FastMCP(
            name="Recon MCP Server",
            instructions="""
            This server aggregates multiple MCP servers generated
            from OpenAPI specifications.


            Internal or admin-only tools (e.g. triggeredadhoc)
            are intentionally hidden.
            """,
            exclude_tags={"internal"},
        )


        for server_cfg in config.get("servers", []):
            mcp_server = start_server(server_cfg)
            if mcp_server:
                main_server.mount(mcp_server)


        main_server.run(
            host="0.0.0.0",
            port=8003,
            transport="streamable-http",
        )

    except FileNotFoundError as e:
        print(f"Configuration error: {e}")
    except KeyboardInterrupt:
        print("Shutting down MCP servers gracefully.")


if __name__ == "__main__":
    main()
