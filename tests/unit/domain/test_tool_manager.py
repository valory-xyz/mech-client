# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2025 Valory AG
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
# ------------------------------------------------------------------------------

"""Tests for tool manager."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from mech_client.domain.tools.manager import ToolManager
from mech_client.domain.tools.models import ToolInfo, ToolsForMarketplaceMech
from mech_client.infrastructure.config.chain_config import LedgerConfig


def create_mock_mech_config() -> MagicMock:
    """
    Create a mock MechConfig with proper LedgerConfig dataclass.

    :return: Mock MechConfig instance
    """
    ledger_config = LedgerConfig(
        address="https://rpc.example.com",
        chain_id=100,
        poa_chain=False,
        default_gas_price_strategy="eip1559",
        is_gas_estimation_enabled=True,
    )
    mock_mech_config = MagicMock()
    mock_mech_config.ledger_config = ledger_config
    mock_mech_config.complementary_metadata_hash_address = "0x" + "1" * 40
    return mock_mech_config


class TestToolManagerInitialization:
    """Tests for ToolManager initialization."""

    @patch("mech_client.domain.tools.manager.EthereumApi")
    @patch("mech_client.domain.tools.manager.get_mech_config")
    def test_initialization(
        self, mock_config: MagicMock, mock_ledger_api: MagicMock
    ) -> None:
        """Test ToolManager initialization."""
        # Setup mocks
        mock_config.return_value = create_mock_mech_config()

        # Create manager
        manager = ToolManager(chain_config="gnosis")

        # Verify initialization
        assert manager.chain_config == "gnosis"
        mock_config.assert_called_once_with("gnosis")
        mock_ledger_api.assert_called_once()


class TestParseToolId:
    """Tests for _parse_tool_id static method."""

    def test_parse_valid_tool_id(self) -> None:
        """Test parsing valid tool ID."""
        service_id, tool_name = ToolManager._parse_tool_id(  # pylint: disable=protected-access
            "42-openai-gpt-4"
        )
        assert service_id == 42
        assert tool_name == "openai-gpt-4"

    def test_parse_tool_id_with_multiple_dashes(self) -> None:
        """Test parsing tool ID with multiple dashes in tool name."""
        service_id, tool_name = ToolManager._parse_tool_id(  # pylint: disable=protected-access
            "1-stability-ai-sdxl-1-0"
        )
        assert service_id == 1
        assert tool_name == "stability-ai-sdxl-1-0"

    def test_parse_tool_id_missing_dash(self) -> None:
        """Test parsing tool ID without dash raises error."""
        with pytest.raises(ValueError, match="Invalid tool ID format"):
            ToolManager._parse_tool_id("invalid")  # pylint: disable=protected-access

    def test_parse_tool_id_invalid_service_id(self) -> None:
        """Test parsing tool ID with non-integer service ID raises error."""
        with pytest.raises(ValueError, match="Invalid service ID"):
            ToolManager._parse_tool_id(  # pylint: disable=protected-access
                "not-a-number-tool"
            )

    def test_parse_tool_id_empty_string(self) -> None:
        """Test parsing empty tool ID raises error."""
        with pytest.raises(ValueError, match="Invalid tool ID format"):
            ToolManager._parse_tool_id("")  # pylint: disable=protected-access


class TestFetchToolsMetadata:
    """Tests for fetch_tools_metadata method."""

    @patch("mech_client.domain.tools.manager.requests")
    @patch("mech_client.domain.tools.manager.get_contract")
    @patch("mech_client.domain.tools.manager.get_abi")
    @patch("mech_client.domain.tools.manager.EthereumApi")
    @patch("mech_client.domain.tools.manager.get_mech_config")
    def test_fetch_tools_metadata_success(
        self,
        mock_config: MagicMock,
        mock_ledger_api: MagicMock,
        mock_get_abi: MagicMock,
        mock_get_contract: MagicMock,
        mock_requests: MagicMock,
    ) -> None:
        """Test successful metadata fetching."""
        # Setup mocks
        mock_config.return_value = create_mock_mech_config()

        # Mock contract returning metadata URI
        mock_contract = MagicMock()
        mock_contract.functions.tokenURI.return_value.call.return_value = (
            "https://metadata.example.com/tool.json"
        )
        mock_get_contract.return_value = mock_contract

        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "tools": ["openai-gpt-4", "stability-ai"],
            "toolMetadata": {
                "openai-gpt-4": {"description": "GPT-4 model"},
                "stability-ai": {"description": "Image generation"},
            },
        }
        mock_requests.get.return_value = mock_response

        # Create manager and fetch
        manager = ToolManager(chain_config="gnosis")
        metadata = manager.fetch_tools_metadata(service_id=1)

        # Verify
        assert metadata is not None
        assert "tools" in metadata
        assert "toolMetadata" in metadata
        assert len(metadata["tools"]) == 2
        mock_contract.functions.tokenURI.assert_called_once_with(1)
        mock_requests.get.assert_called_once_with(
            "https://metadata.example.com/tool.json", timeout=10
        )

    @patch("mech_client.domain.tools.manager.EthereumApi")
    @patch("mech_client.domain.tools.manager.get_mech_config")
    def test_fetch_tools_metadata_zero_address(
        self, mock_config: MagicMock, mock_ledger_api: MagicMock
    ) -> None:
        """Test fetch with zero metadata address raises error."""
        # Setup mocks with zero address
        mock_mech_config = create_mock_mech_config()
        mock_mech_config.complementary_metadata_hash_address = (
            "0x0000000000000000000000000000000000000000"
        )
        mock_config.return_value = mock_mech_config

        # Create manager
        manager = ToolManager(chain_config="gnosis")

        # Fetch should raise
        with pytest.raises(ValueError, match="not yet implemented"):
            manager.fetch_tools_metadata(service_id=1)

    @patch("mech_client.domain.tools.manager.requests")
    @patch("mech_client.domain.tools.manager.get_contract")
    @patch("mech_client.domain.tools.manager.get_abi")
    @patch("mech_client.domain.tools.manager.EthereumApi")
    @patch("mech_client.domain.tools.manager.get_mech_config")
    def test_fetch_tools_metadata_http_error(
        self,
        mock_config: MagicMock,
        mock_ledger_api: MagicMock,
        mock_get_abi: MagicMock,
        mock_get_contract: MagicMock,
        mock_requests: MagicMock,
    ) -> None:
        """Test fetch with HTTP error returns None."""
        # Setup mocks
        mock_config.return_value = create_mock_mech_config()

        mock_contract = MagicMock()
        mock_contract.functions.tokenURI.return_value.call.return_value = (
            "https://metadata.example.com/tool.json"
        )
        mock_get_contract.return_value = mock_contract

        # Mock HTTP error
        mock_requests.get.side_effect = IOError("Network error")

        # Create manager and fetch
        manager = ToolManager(chain_config="gnosis")
        metadata = manager.fetch_tools_metadata(service_id=1)

        # Should return None on error
        assert metadata is None

    @patch("mech_client.domain.tools.manager.requests")
    @patch("mech_client.domain.tools.manager.get_contract")
    @patch("mech_client.domain.tools.manager.get_abi")
    @patch("mech_client.domain.tools.manager.EthereumApi")
    @patch("mech_client.domain.tools.manager.get_mech_config")
    def test_fetch_tools_metadata_invalid_json(
        self,
        mock_config: MagicMock,
        mock_ledger_api: MagicMock,
        mock_get_abi: MagicMock,
        mock_get_contract: MagicMock,
        mock_requests: MagicMock,
    ) -> None:
        """Test fetch with invalid JSON returns None."""
        # Setup mocks
        mock_config.return_value = create_mock_mech_config()

        mock_contract = MagicMock()
        mock_contract.functions.tokenURI.return_value.call.return_value = (
            "https://metadata.example.com/tool.json"
        )
        mock_get_contract.return_value = mock_contract

        # Mock response with invalid JSON
        mock_response = MagicMock()
        mock_response.json.side_effect = requests.exceptions.JSONDecodeError(
            "Invalid JSON", "", 0
        )
        mock_requests.get.return_value = mock_response

        # Create manager and fetch
        manager = ToolManager(chain_config="gnosis")
        metadata = manager.fetch_tools_metadata(service_id=1)

        # Should return None on JSON error
        assert metadata is None


class TestGetTools:
    """Tests for get_tools method."""

    @patch("mech_client.domain.tools.manager.EthereumApi")
    @patch("mech_client.domain.tools.manager.get_mech_config")
    def test_get_tools_success(
        self, mock_config: MagicMock, mock_ledger_api: MagicMock
    ) -> None:
        """Test successful tool retrieval."""
        # Setup mocks
        mock_config.return_value = create_mock_mech_config()

        # Create manager
        manager = ToolManager(chain_config="gnosis")

        # Mock fetch_tools_metadata
        manager.fetch_tools_metadata = MagicMock(  # type: ignore
            return_value={
                "tools": ["openai-gpt-4", "stability-ai"],
                "toolMetadata": {},
            }
        )

        # Get tools
        result = manager.get_tools(service_id=1)

        # Verify
        assert result is not None
        assert isinstance(result, ToolsForMarketplaceMech)
        assert result.service_id == 1
        assert len(result.tools) == 2
        assert result.tools[0].tool_name == "openai-gpt-4"
        assert result.tools[0].unique_identifier == "1-openai-gpt-4"
        assert result.tools[1].tool_name == "stability-ai"
        assert result.tools[1].unique_identifier == "1-stability-ai"

    @patch("mech_client.domain.tools.manager.EthereumApi")
    @patch("mech_client.domain.tools.manager.get_mech_config")
    def test_get_tools_no_metadata(
        self, mock_config: MagicMock, mock_ledger_api: MagicMock
    ) -> None:
        """Test get_tools with no metadata returns None."""
        # Setup mocks
        mock_config.return_value = create_mock_mech_config()

        # Create manager
        manager = ToolManager(chain_config="gnosis")

        # Mock fetch returning None
        manager.fetch_tools_metadata = MagicMock(return_value=None)  # type: ignore

        # Get tools
        result = manager.get_tools(service_id=1)

        # Should return None
        assert result is None

    @patch("mech_client.domain.tools.manager.EthereumApi")
    @patch("mech_client.domain.tools.manager.get_mech_config")
    def test_get_tools_empty_tools_list(
        self, mock_config: MagicMock, mock_ledger_api: MagicMock
    ) -> None:
        """Test get_tools with empty tools list returns None."""
        # Setup mocks
        mock_config.return_value = create_mock_mech_config()

        # Create manager
        manager = ToolManager(chain_config="gnosis")

        # Mock fetch returning empty tools
        manager.fetch_tools_metadata = MagicMock(  # type: ignore
            return_value={"tools": [], "toolMetadata": {}}
        )

        # Get tools
        result = manager.get_tools(service_id=1)

        # Should return None
        assert result is None

    @patch("mech_client.domain.tools.manager.EthereumApi")
    @patch("mech_client.domain.tools.manager.get_mech_config")
    def test_get_tools_missing_tools_key(
        self, mock_config: MagicMock, mock_ledger_api: MagicMock
    ) -> None:
        """Test get_tools with missing 'tools' key returns None."""
        # Setup mocks
        mock_config.return_value = create_mock_mech_config()

        # Create manager
        manager = ToolManager(chain_config="gnosis")

        # Mock fetch returning metadata without 'tools' key
        manager.fetch_tools_metadata = MagicMock(  # type: ignore
            return_value={"toolMetadata": {}}
        )

        # Get tools
        result = manager.get_tools(service_id=1)

        # Should return None
        assert result is None


class TestGetToolDescription:
    """Tests for get_tool_description method."""

    @patch("mech_client.domain.tools.manager.EthereumApi")
    @patch("mech_client.domain.tools.manager.get_mech_config")
    def test_get_tool_description_success(
        self, mock_config: MagicMock, mock_ledger_api: MagicMock
    ) -> None:
        """Test successful tool description retrieval."""
        # Setup mocks
        mock_config.return_value = create_mock_mech_config()

        # Create manager
        manager = ToolManager(chain_config="gnosis")

        # Mock fetch_tools_metadata
        manager.fetch_tools_metadata = MagicMock(  # type: ignore
            return_value={
                "tools": ["openai-gpt-4"],
                "toolMetadata": {
                    "openai-gpt-4": {
                        "description": "OpenAI GPT-4 language model for text generation"
                    }
                },
            }
        )

        # Get description
        description = manager.get_tool_description("1-openai-gpt-4")

        # Verify
        assert description == "OpenAI GPT-4 language model for text generation"

    @patch("mech_client.domain.tools.manager.EthereumApi")
    @patch("mech_client.domain.tools.manager.get_mech_config")
    def test_get_tool_description_no_description_field(
        self, mock_config: MagicMock, mock_ledger_api: MagicMock
    ) -> None:
        """Test get_tool_description with missing description field."""
        # Setup mocks
        mock_config.return_value = create_mock_mech_config()

        # Create manager
        manager = ToolManager(chain_config="gnosis")

        # Mock fetch_tools_metadata without description field
        manager.fetch_tools_metadata = MagicMock(  # type: ignore
            return_value={
                "tools": ["openai-gpt-4"],
                "toolMetadata": {"openai-gpt-4": {}},
            }
        )

        # Get description
        description = manager.get_tool_description("1-openai-gpt-4")

        # Should return default message
        assert description == "No description available"

    @patch("mech_client.domain.tools.manager.EthereumApi")
    @patch("mech_client.domain.tools.manager.get_mech_config")
    def test_get_tool_description_metadata_fetch_fails(
        self, mock_config: MagicMock, mock_ledger_api: MagicMock
    ) -> None:
        """Test get_tool_description when metadata fetch fails."""
        # Setup mocks
        mock_config.return_value = create_mock_mech_config()

        # Create manager
        manager = ToolManager(chain_config="gnosis")

        # Mock fetch returning None
        manager.fetch_tools_metadata = MagicMock(return_value=None)  # type: ignore

        # Get description should raise
        with pytest.raises(ValueError, match="Could not fetch metadata"):
            manager.get_tool_description("1-openai-gpt-4")

    @patch("mech_client.domain.tools.manager.EthereumApi")
    @patch("mech_client.domain.tools.manager.get_mech_config")
    def test_get_tool_description_tool_not_found(
        self, mock_config: MagicMock, mock_ledger_api: MagicMock
    ) -> None:
        """Test get_tool_description for non-existent tool."""
        # Setup mocks
        mock_config.return_value = create_mock_mech_config()

        # Create manager
        manager = ToolManager(chain_config="gnosis")

        # Mock fetch_tools_metadata without the requested tool
        manager.fetch_tools_metadata = MagicMock(  # type: ignore
            return_value={
                "tools": ["openai-gpt-4"],
                "toolMetadata": {"openai-gpt-4": {"description": "GPT-4"}},
            }
        )

        # Get description for non-existent tool should raise
        with pytest.raises(ValueError, match="not found in metadata"):
            manager.get_tool_description("1-non-existent-tool")


class TestGetToolSchema:
    """Tests for get_tool_schema method."""

    @patch("mech_client.domain.tools.manager.EthereumApi")
    @patch("mech_client.domain.tools.manager.get_mech_config")
    def test_get_tool_schema_success(
        self, mock_config: MagicMock, mock_ledger_api: MagicMock
    ) -> None:
        """Test successful tool schema retrieval."""
        # Setup mocks
        mock_config.return_value = create_mock_mech_config()

        # Create manager
        manager = ToolManager(chain_config="gnosis")

        # Mock fetch_tools_metadata
        manager.fetch_tools_metadata = MagicMock(  # type: ignore
            return_value={
                "tools": ["openai-gpt-4"],
                "toolMetadata": {
                    "openai-gpt-4": {
                        "description": "GPT-4 model",
                        "input": {
                            "type": "object",
                            "properties": {"prompt": {"type": "string"}},
                        },
                        "output": {"type": "string"},
                    }
                },
            }
        )

        # Get schema
        schema = manager.get_tool_schema("1-openai-gpt-4")

        # Verify
        assert schema["name"] == "openai-gpt-4"
        assert schema["description"] == "GPT-4 model"
        assert schema["input"]["type"] == "object"
        assert "prompt" in schema["input"]["properties"]
        assert schema["output"]["type"] == "string"

    @patch("mech_client.domain.tools.manager.EthereumApi")
    @patch("mech_client.domain.tools.manager.get_mech_config")
    def test_get_tool_schema_missing_fields(
        self, mock_config: MagicMock, mock_ledger_api: MagicMock
    ) -> None:
        """Test get_tool_schema with missing optional fields."""
        # Setup mocks
        mock_config.return_value = create_mock_mech_config()

        # Create manager
        manager = ToolManager(chain_config="gnosis")

        # Mock fetch_tools_metadata with minimal data
        manager.fetch_tools_metadata = MagicMock(  # type: ignore
            return_value={
                "tools": ["openai-gpt-4"],
                "toolMetadata": {"openai-gpt-4": {}},
            }
        )

        # Get schema
        schema = manager.get_tool_schema("1-openai-gpt-4")

        # Should have default/empty values
        assert schema["name"] == "openai-gpt-4"
        assert schema["description"] == ""
        assert schema["input"] == {}
        assert schema["output"] == {}

    @patch("mech_client.domain.tools.manager.EthereumApi")
    @patch("mech_client.domain.tools.manager.get_mech_config")
    def test_get_tool_schema_metadata_fetch_fails(
        self, mock_config: MagicMock, mock_ledger_api: MagicMock
    ) -> None:
        """Test get_tool_schema when metadata fetch fails."""
        # Setup mocks
        mock_config.return_value = create_mock_mech_config()

        # Create manager
        manager = ToolManager(chain_config="gnosis")

        # Mock fetch returning None
        manager.fetch_tools_metadata = MagicMock(return_value=None)  # type: ignore

        # Get schema should raise
        with pytest.raises(ValueError, match="Could not fetch metadata"):
            manager.get_tool_schema("1-openai-gpt-4")

    @patch("mech_client.domain.tools.manager.EthereumApi")
    @patch("mech_client.domain.tools.manager.get_mech_config")
    def test_get_tool_schema_tool_not_found(
        self, mock_config: MagicMock, mock_ledger_api: MagicMock
    ) -> None:
        """Test get_tool_schema for non-existent tool."""
        # Setup mocks
        mock_config.return_value = create_mock_mech_config()

        # Create manager
        manager = ToolManager(chain_config="gnosis")

        # Mock fetch_tools_metadata without the requested tool
        manager.fetch_tools_metadata = MagicMock(  # type: ignore
            return_value={
                "tools": ["openai-gpt-4"],
                "toolMetadata": {"openai-gpt-4": {"description": "GPT-4"}},
            }
        )

        # Get schema for non-existent tool should raise
        with pytest.raises(ValueError, match="not found in metadata"):
            manager.get_tool_schema("1-non-existent-tool")
