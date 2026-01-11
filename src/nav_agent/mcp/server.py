import json
from pathlib import Path

import httpx
from fastmcp import FastMCP


def setup_fastmcp_server_from_openapi_spec(
    spec_link: str,
    base_url: str,
    server_name: str,
) -> FastMCP:
    """Create a FastMCP server from an OpenAPI specification.

    Args:
        spec_link: URL to the OpenAPI specification
        base_url: Base URL for the API
        server_name: Name of the MCP server

    Returns:
        Configured FastMCP instance
    """
    open_api_spec = httpx.get(spec_link).json()
    client = httpx.AsyncClient(base_url=base_url)
    return FastMCP.from_openapi(
        openapi_spec=open_api_spec,
        client=client,
        name=server_name,
    )


def load_config(config_path: str = "order_agent_servers_config.json") -> dict:
    """Load server configuration from JSON file.

    Args:
        config_path: Path to the configuration file

    Returns:
        Configuration dictionary
    """
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_file) as f:
        config = json.load(f)

    return config


def start_server(server_config: dict) -> FastMCP:
    """Start a single MCP server in a separate thread.

    Args:
        server_config: Configuration dictionary for the server
    """
    server_name = server_config.get("server_name")
    spec_link = server_config.get("spec_link")
    base_url = server_config.get("base_url")

    if not all([server_name, spec_link, base_url]):
        print(f"Skipping incomplete server config: {server_config}")
        return

    try:
        mcp_server = setup_fastmcp_server_from_openapi_spec(
            spec_link=spec_link,
            base_url=base_url,
            server_name=server_name,
        )
        return mcp_server
    except Exception as e:
        print(f"Failed to start {server_name}: {str(e)}")


def main():
    """Entry point for the MCP servers!"""
    try:
        # Load configuration
        config = load_config("order_agent_servers_config.json")

        # Run main server
        main_server = FastMCP("Main MCP Server")
        for server_config in config.get("servers"):
            main_server.mount(start_server(server_config))
        main_server.run(host="0.0.0.0", port=8000, transport="streamable-http")
    except FileNotFoundError as e:
        print(f"Error: {str(e)}")
    except KeyboardInterrupt as ke:
        print("Shutting down the mpc servers.")


if __name__ == "__main__":
    main()
