"""Unit tests for authorization and configuration.

Tests the authorization logic and configuration parsing.
"""

import json

from agent.graph import UserContext, _is_write_operation, _parse_mcp_servers


class TestMCPConfiguration:
    """Test MCP servers configuration parsing."""

    def test_parse_empty_mcp_servers(self, monkeypatch):
        """Test parsing when MCP_SERVERS is not set."""
        monkeypatch.delenv("MCP_SERVERS", raising=False)
        result = _parse_mcp_servers()
        assert result == {}

    def test_parse_single_mcp_server(self, monkeypatch):
        """Test parsing single MCP server configuration."""
        config = {
            "servers": [
                {
                    "type": "http",
                    "url": "http://localhost:8000/sse",
                    "name": "local_api",
                }
            ]
        }
        monkeypatch.setenv("MCP_SERVERS", json.dumps(config))
        result = _parse_mcp_servers()
        assert "local_api" in result
        assert result["local_api"]["type"] == "http"
        assert result["local_api"]["url"] == "http://localhost:8000/sse"

    def test_parse_multiple_mcp_servers(self, monkeypatch):
        """Test parsing multiple MCP servers."""
        config = {
            "servers": [
                {"type": "http", "url": "http://localhost:8000/sse", "name": "api1"},
                {"type": "http", "url": "http://localhost:8001/sse", "name": "api2"},
            ]
        }
        monkeypatch.setenv("MCP_SERVERS", json.dumps(config))
        result = _parse_mcp_servers()
        assert len(result) == 2
        assert "api1" in result
        assert "api2" in result

    def test_parse_invalid_json(self, monkeypatch):
        """Test parsing invalid JSON returns empty dict."""
        monkeypatch.setenv("MCP_SERVERS", "invalid json")
        result = _parse_mcp_servers()
        assert result == {}


class TestWriteOperationDetection:
    """Test write operation detection logic."""

    def test_detect_create_operation(self):
        """Test detection of create operations."""
        assert _is_write_operation("create_resource") is True
        assert _is_write_operation("create_pet") is True

    def test_detect_update_operation(self):
        """Test detection of update operations."""
        assert _is_write_operation("update_resource") is True
        assert _is_write_operation("update_user") is True

    def test_detect_delete_operation(self):
        """Test detection of delete operations."""
        assert _is_write_operation("delete_resource") is True
        assert _is_write_operation("delete_pet") is True

    def test_detect_post_operation(self):
        """Test detection of POST operations."""
        assert _is_write_operation("post_data") is True

    def test_detect_put_operation(self):
        """Test detection of PUT operations."""
        assert _is_write_operation("put_update") is True

    def test_read_operations_not_detected_as_write(self):
        """Test that read operations are not detected as write."""
        assert _is_write_operation("get_resource") is False
        assert _is_write_operation("list_pets") is False
        assert _is_write_operation("fetch_data") is False
        assert _is_write_operation("search") is False

    def test_case_insensitive_detection(self):
        """Test that detection is case-insensitive."""
        assert _is_write_operation("CREATE_RESOURCE") is True
        assert _is_write_operation("Delete_Pet") is True
        assert _is_write_operation("UPDATE_user") is True


class TestUserContextAuthorization:
    """Test user context and authorization structures."""

    def test_user_context_with_all_fields(self):
        """Test UserContext with all fields."""
        user: UserContext = {
            "user_id": "user_123",
            "role": "editor",
            "scope": ["server1", "server2"],
        }
        assert user["user_id"] == "user_123"
        assert user["role"] == "editor"
        assert "server1" in user["scope"]

    def test_user_context_with_minimal_fields(self):
        """Test UserContext with minimal fields."""
        user: UserContext = {"user_id": "user_456"}
        assert user["user_id"] == "user_456"
        assert user.get("role") is None
        assert user.get("scope", []) == []

    def test_scope_checking(self):
        """Test checking if user has scope for a server."""
        user: UserContext = {
            "user_id": "user_789",
            "role": "editor",
            "scope": ["api1", "api2"],
        }
        user_scope = user.get("scope", [])
        assert "api1" in user_scope
        assert "api2" in user_scope
        assert "api3" not in user_scope
