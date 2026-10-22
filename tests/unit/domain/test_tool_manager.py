# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2025-2026 Valory AG
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

import json
import socket
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

import pytest
import requests
from mech_client.domain.identification import VALORY_TERMS_NOTICE
from mech_client.domain.operator import (
    BENCHMARK_NOTE,
    NO_AGENT_ID_NOTE,
    DomainVerification,
)
from mech_client.domain.tools.manager import (
    DELIVERY_NOTE,
    DOMAIN_CHECK_FAILED_NOTE,
    EXPECTED_COST_NOTE,
    MANIFEST_HASH_NOTE,
    MANIFEST_UNREADABLE_NOTE,
    NAME_NOTE,
    IDENTIFICATION_NOTE,
    PAYMENT_NOTE,
    ToolManager,
    claimed_operator,
    manifest_matches_uri,
    payment_asset,
    payment_label,
)
from mech_client.infrastructure.ipfs.local_cid import compute_cidv1_bytes
from mech_client.domain.tools.models import ToolInfo, ToolsForMarketplaceMech
from mech_client.infrastructure.config.chain_config import LedgerConfig
from mech_client.infrastructure.config.payment_config import PaymentType
from mech_client.infrastructure.subgraph.queries import MechRecord
from mech_client.utils.errors import SubgraphError
from mech_client.utils.errors.exceptions import ManifestError


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


GATEWAY = "https://gateway.autonolas.tech/ipfs/"
TOOLS_MANIFEST: Dict[str, Any] = {
    "tools": ["openai-gpt-4", "stability-ai"],
    "toolMetadata": {
        "openai-gpt-4": {"description": "GPT-4 model"},
        "stability-ai": {"description": "Image generation"},
    },
}


def _published(document: Any, body: Optional[bytes] = None) -> tuple:
    """
    Publish a manifest the way the contract and a gateway present it.

    :param document: the manifest the operator pinned, whose CID the URI names
    :param body: what the gateway serves, the pinned bytes unless given
    :return: the on-chain metadata URI and the HTTP response for it
    """
    pinned = json.dumps(document).encode()
    uri = GATEWAY + "f" + compute_cidv1_bytes(pinned).hex()
    response = MagicMock()
    response.content = pinned if body is None else body
    return uri, response


class TestManifestMatchesUri:
    """The served bytes must hash to the CID the on-chain URI names."""

    def test_the_pinned_bytes_match_their_own_uri(self) -> None:
        """A faithful gateway serves exactly what was pinned."""
        uri, response = _published(TOOLS_MANIFEST)
        assert manifest_matches_uri(uri, response.content) is True

    def test_a_trailing_slash_and_upper_case_hex_still_match(self) -> None:
        """The CID is read from the last path segment, case-insensitively."""
        uri, response = _published(TOOLS_MANIFEST)
        assert manifest_matches_uri(uri.upper() + "/", response.content) is True

    def test_a_single_changed_byte_does_not_match(self) -> None:
        """Any other document, however close, hashes elsewhere."""
        uri, _ = _published(TOOLS_MANIFEST)
        other = json.dumps({**TOOLS_MANIFEST, "url": "https://else.example"}).encode()
        assert manifest_matches_uri(uri, other) is False

    @pytest.mark.parametrize(
        "uri",
        [
            "https://metadata.example.com/tool.json",
            GATEWAY + "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            GATEWAY + "f01551220" + "a" * 64,
            GATEWAY,
            "",
        ],
        ids=["plain_url", "base32_cid", "raw_codec_cid", "no_segment", "empty"],
    )
    def test_a_uri_without_a_dag_pb_sha256_cid_never_matches(self, uri: str) -> None:
        """Only the base16 CIDv1 the contract writes can be checked, so anything else fails."""
        assert manifest_matches_uri(uri, json.dumps(TOOLS_MANIFEST).encode()) is False

    def test_a_body_too_large_for_one_block_does_not_match(self) -> None:
        """A multi-block document is not a manifest this client can verify."""
        uri, _ = _published(TOOLS_MANIFEST)
        assert manifest_matches_uri(uri, b"x" * (256 * 1024 + 1)) is False


@patch("mech_client.domain.tools.manager.requests")
@patch("mech_client.domain.tools.manager.get_contract")
@patch("mech_client.domain.tools.manager.get_abi")
@patch("mech_client.domain.tools.manager.EthereumApi")
@patch("mech_client.domain.tools.manager.get_mech_config")
class TestFetchToolsMetadata:
    """The manifest is read from the on-chain URI and kept only when it hashes to it."""

    @staticmethod
    def _fetch(
        mock_config: MagicMock,
        mock_get_contract: MagicMock,
        mock_requests: MagicMock,
        uri: str,
        response: Any,
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch service 1's manifest against a contract naming ``uri``.

        :param mock_config: the patched config loader
        :param mock_get_contract: the patched contract factory
        :param mock_requests: the patched requests module
        :param uri: what ``tokenURI`` returns
        :param response: what the gateway answers, or an exception to raise
        :return: what ``fetch_tools_metadata`` returns
        """
        mock_config.return_value = create_mock_mech_config()
        mock_contract = MagicMock()
        mock_contract.functions.tokenURI.return_value.call.return_value = uri
        mock_get_contract.return_value = mock_contract
        if isinstance(response, Exception):
            mock_requests.get.side_effect = response
        else:
            mock_requests.get.return_value = response
        return ToolManager(chain_config="gnosis").fetch_tools_metadata(service_id=1)

    def test_a_manifest_that_hashes_to_its_uri_is_returned(
        self,
        mock_config: MagicMock,
        _ledger: MagicMock,
        _abi: MagicMock,
        mock_get_contract: MagicMock,
        mock_requests: MagicMock,
    ) -> None:
        """The pinned document comes back parsed, read from the contract's URI."""
        uri, response = _published(TOOLS_MANIFEST)

        metadata = self._fetch(mock_config, mock_get_contract, mock_requests, uri, response)

        assert metadata == TOOLS_MANIFEST
        mock_get_contract.return_value.functions.tokenURI.assert_called_once_with(1)
        mock_requests.get.assert_called_once_with(uri, timeout=10)

    def test_a_manifest_that_does_not_hash_to_its_uri_is_not_used(
        self,
        mock_config: MagicMock,
        _ledger: MagicMock,
        _abi: MagicMock,
        mock_get_contract: MagicMock,
        mock_requests: MagicMock,
    ) -> None:
        """A document other than the one recorded on-chain is treated as unreadable."""
        served = json.dumps({**TOOLS_MANIFEST, "url": "https://else.example"}).encode()
        uri, response = _published(TOOLS_MANIFEST, body=served)

        with patch("mech_client.domain.tools.manager.logger.error") as error:
            metadata = self._fetch(mock_config, mock_get_contract, mock_requests, uri, response)

        assert metadata is None
        error.assert_called_once_with(MANIFEST_HASH_NOTE.format(service_id=1))

    def test_a_uri_without_a_cid_cannot_be_checked_and_is_not_used(
        self,
        mock_config: MagicMock,
        _ledger: MagicMock,
        _abi: MagicMock,
        mock_get_contract: MagicMock,
        mock_requests: MagicMock,
    ) -> None:
        """Without the on-chain CID in the URI there is nothing to check the bytes against."""
        _, response = _published(TOOLS_MANIFEST)

        metadata = self._fetch(
            mock_config, mock_get_contract, mock_requests, "https://metadata.example.com/tool.json", response
        )

        assert metadata is None

    def test_zero_metadata_address_raises(
        self,
        mock_config: MagicMock,
        _ledger: MagicMock,
        _abi: MagicMock,
        _contract: MagicMock,
        _requests: MagicMock,
    ) -> None:
        """A chain without the metadata contract cannot serve a manifest."""
        mock_mech_config = create_mock_mech_config()
        mock_mech_config.complementary_metadata_hash_address = (
            "0x0000000000000000000000000000000000000000"
        )
        mock_config.return_value = mock_mech_config

        with pytest.raises(ValueError, match="not yet implemented"):
            ToolManager(chain_config="gnosis").fetch_tools_metadata(service_id=1)

    def test_an_http_error_gives_no_manifest(
        self,
        mock_config: MagicMock,
        _ledger: MagicMock,
        _abi: MagicMock,
        mock_get_contract: MagicMock,
        mock_requests: MagicMock,
    ) -> None:
        """A gateway that cannot be reached means an unreadable manifest, not an exception."""
        uri, _ = _published(TOOLS_MANIFEST)

        metadata = self._fetch(
            mock_config, mock_get_contract, mock_requests, uri, IOError("Network error")
        )

        assert metadata is None

    def test_bytes_that_hash_right_but_are_not_json_give_no_manifest(
        self,
        mock_config: MagicMock,
        _ledger: MagicMock,
        _abi: MagicMock,
        mock_get_contract: MagicMock,
        mock_requests: MagicMock,
    ) -> None:
        """A pinned document that is not JSON passes the hash check and fails parsing."""
        pinned = b"not json"
        uri = GATEWAY + "f" + compute_cidv1_bytes(pinned).hex()
        response = MagicMock()
        response.content = pinned

        metadata = self._fetch(mock_config, mock_get_contract, mock_requests, uri, response)

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


class TestGetOffchainUrl:
    """Tests for get_offchain_url method."""

    @patch("mech_client.domain.tools.manager.EthereumApi")
    @patch("mech_client.domain.tools.manager.get_mech_config")
    def test_get_offchain_url_returns_url_from_metadata(
        self, mock_config: MagicMock, mock_ledger_api: MagicMock
    ) -> None:
        """Test that get_offchain_url returns the URL from metadata."""
        # Setup mocks
        mock_config.return_value = create_mock_mech_config()

        # Create manager
        manager = ToolManager(chain_config="gnosis")

        # Mock fetch_tools_metadata to return metadata with url
        manager.fetch_tools_metadata = MagicMock(  # type: ignore
            return_value={
                "url": "https://mech.example.com/",
                "tools": ["openai-gpt-4"],
            }
        )

        # Get offchain URL
        url = manager.get_offchain_url(service_id=42)

        # Verify
        assert url == "https://mech.example.com/"
        manager.fetch_tools_metadata.assert_called_once_with(42)

    @patch("mech_client.domain.tools.manager.EthereumApi")
    @patch("mech_client.domain.tools.manager.get_mech_config")
    def test_get_offchain_url_raises_when_no_url(
        self, mock_config: MagicMock, mock_ledger_api: MagicMock
    ) -> None:
        """Test that get_offchain_url raises ValueError when url key is missing."""
        # Setup mocks
        mock_config.return_value = create_mock_mech_config()

        # Create manager
        manager = ToolManager(chain_config="gnosis")

        # Mock fetch_tools_metadata to return metadata without url
        manager.fetch_tools_metadata = MagicMock(  # type: ignore
            return_value={
                "tools": ["openai-gpt-4"],
                "toolMetadata": {},
            }
        )

        # Should raise ValueError
        with pytest.raises(ValueError, match="does not contain an offchain URL"):
            manager.get_offchain_url(service_id=42)

    @patch("mech_client.domain.tools.manager.EthereumApi")
    @patch("mech_client.domain.tools.manager.get_mech_config")
    def test_get_offchain_url_raises_when_metadata_none(
        self, mock_config: MagicMock, mock_ledger_api: MagicMock
    ) -> None:
        """Test that get_offchain_url raises ValueError when metadata is None."""
        # Setup mocks
        mock_config.return_value = create_mock_mech_config()

        # Create manager
        manager = ToolManager(chain_config="gnosis")

        # Mock fetch_tools_metadata to return None
        manager.fetch_tools_metadata = MagicMock(return_value=None)  # type: ignore

        # Should raise ValueError
        with pytest.raises(ValueError, match="Could not fetch metadata"):
            manager.get_offchain_url(service_id=42)

    @patch("mech_client.domain.tools.manager.EthereumApi")
    @patch("mech_client.domain.tools.manager.get_mech_config")
    def test_get_offchain_url_raises_when_url_empty(
        self, mock_config: MagicMock, mock_ledger_api: MagicMock
    ) -> None:
        """Test that get_offchain_url raises ValueError when url is empty string."""
        # Setup mocks
        mock_config.return_value = create_mock_mech_config()

        # Create manager
        manager = ToolManager(chain_config="gnosis")

        # Mock fetch_tools_metadata to return metadata with empty url
        manager.fetch_tools_metadata = MagicMock(  # type: ignore
            return_value={
                "url": "  ",
                "tools": ["openai-gpt-4"],
            }
        )

        # Should raise ValueError
        with pytest.raises(ValueError, match="does not contain an offchain URL"):
            manager.get_offchain_url(service_id=42)


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


class TestExtractTermsUrl:
    """extract_terms_url reads termsUrl from a document that came from a third party."""

    @pytest.mark.parametrize(
        ("metadata", "expected"),
        [
            ({"termsUrl": "https://www.valory.xyz/terms/mechs"}, "https://www.valory.xyz/terms/mechs"),
            ({"termsUrl": "  https://example.test/terms  "}, "https://example.test/terms"),
            ({"tools": []}, None),  # field absent
            ({"termsUrl": ""}, None),  # empty string
            ({"termsUrl": "   "}, None),  # whitespace only
            ({"termsUrl": None}, None),  # explicit null
            ({"termsUrl": 123}, None),  # not a string
            ({"termsUrl": ["x"]}, None),  # not a string
            ({"termsUrl": {"href": "x"}}, None),  # not a string
            (["not", "a", "dict"], None),  # document is a list
            ("just a string", None),  # document is a scalar
            (None, None),  # no document
            ({"termsUrl": "http://example.test/terms"}, None),  # not https
            ({"termsUrl": "javascript:alert(1)"}, None),  # not a web URL
            ({"termsUrl": "https:///terms"}, None),  # no host
            ({"termsUrl": "example.test/terms"}, None),  # no scheme
            ({"termsUrl": "https://example.test/a b"}, None),  # inner space
            ({"termsUrl": "https://example.test/\x1b[31m"}, None),  # control char
            ({"termsUrl": "https://example.test/\u202e"}, None),  # bidi override
            ({"termsUrl": "https://[::1/terms"}, None),  # unparseable host
            ({"termsUrl": "https://example.test/" + "a" * 2027}, "https://example.test/" + "a" * 2027),  # at the cap
            ({"termsUrl": "https://example.test/" + "a" * 2028}, None),  # over the cap
        ],
        ids=[
            "present", "stripped", "absent", "empty", "whitespace", "null",
            "int", "list_value", "dict_value", "list_document", "scalar_document", "none",
            "http", "javascript", "no_host", "no_scheme", "inner_space",
            "control_char", "bidi_override", "bad_ipv6", "at_cap", "over_cap",
        ],
    )
    def test_extract_terms_url(self, metadata: Any, expected: Optional[str]) -> None:
        """Only a plain https link on a JSON object is returned; everything else is None."""
        assert ToolManager.extract_terms_url(metadata) == expected


IDENTIFICATION = "mech_client.domain.identification"
GNOSIS_MECH = "0xC05e7412439bD7e91730a6880E18d5D5873F632C"
GNOSIS_NAME = "c05e7412439bd7e91730a6880e18d5d5873f632c-100.mech.valory.xyz"
OPERATOR_TERMS = "https://operator.test/terms"


def _resolver(outcome: str) -> Any:
    """
    Build a getaddrinfo stand-in for one identification outcome.

    :param outcome: "valory", "not_valory" or "broken"
    :return: A side effect for socket.getaddrinfo
    """

    def getaddrinfo(name: str, _port: Any) -> list:
        if outcome == "broken":
            raise OSError("network unreachable")
        if outcome == "valory" and name == GNOSIS_NAME:
            return [("ok",)]
        raise socket.gaierror(socket.EAI_NONAME, "not known")

    return getaddrinfo


class TestTermsReport:
    """terms_report says whose terms apply, keyed on the manager's own chain."""

    @pytest.fixture
    def manager(self) -> ToolManager:
        """A manager on Gnosis, with no network behind it."""
        with (
            patch("mech_client.domain.tools.manager.EthereumApi"),
            patch(
                "mech_client.domain.tools.manager.get_mech_config",
                return_value=create_mock_mech_config(),
            ),
        ):
            return ToolManager(chain_config="gnosis")

    @pytest.mark.parametrize(
        ("outcome", "metadata", "expected"),
        [
            (
                "valory",
                {"termsUrl": OPERATOR_TERMS},
                {
                    "valory_operated": True,
                    "terms": VALORY_TERMS_NOTICE,
                    "terms_url": OPERATOR_TERMS,
                },
            ),
            ("valory", {}, {"valory_operated": True, "terms": VALORY_TERMS_NOTICE}),
            (
                "not_valory",
                {"termsUrl": OPERATOR_TERMS},
                {"valory_operated": False, "terms_url": OPERATOR_TERMS},
            ),
            ("not_valory", None, {"valory_operated": False}),
            (
                "broken",
                {"termsUrl": OPERATOR_TERMS},
                {
                    "valory_operated": False,
                    "identification_note": IDENTIFICATION_NOTE,
                    "terms_url": OPERATOR_TERMS,
                },
            ),
            (
                "not_valory",
                {"termsUrl": "http://operator.test/terms"},
                {"valory_operated": False},
            ),
        ],
        ids=[
            "valory_with_link",
            "valory_without_link",
            "other_with_link",
            "other_without_document",
            "check_failed",
            "invalid_link_dropped",
        ],
    )
    def test_report(
        self,
        manager: ToolManager,
        outcome: str,
        metadata: Any,
        expected: Dict[str, Any],
    ) -> None:
        """Only a confirmed Valory mech gets the statement; a published link always passes."""
        with (
            patch(f"{IDENTIFICATION}.socket.getaddrinfo", side_effect=_resolver(outcome)),
            patch(f"{IDENTIFICATION}.logger"),
        ):
            assert manager.terms_report(GNOSIS_MECH, metadata) == expected

    def test_the_chain_comes_from_the_manager(self, manager: ToolManager) -> None:
        """The caller passes no chain; the lookup uses the manager's chain id."""
        looked_up: list = []

        def getaddrinfo(name: str, _port: Any) -> list:
            looked_up.append(name)
            raise socket.gaierror(socket.EAI_NONAME, "not known")

        with patch(f"{IDENTIFICATION}.socket.getaddrinfo", side_effect=getaddrinfo):
            manager.terms_report(GNOSIS_MECH, None)
        assert looked_up == [GNOSIS_NAME]


MANAGER = "mech_client.domain.tools.manager"
NATIVE = "0xba699a34be8fe0e7725e93dcbce1701b0211a8ca61330aaeb8a05bf2ec7abed1"
USDC = "0x6406bb5f31a732f898e1ce9fdd988a80a808d36ab5d9a4a4805a8be8d197d5e3"
CREATED_AT = datetime(2025, 6, 4, 16, 35, 20, tzinfo=timezone.utc)
OPERATOR_MANIFEST = {
    "termsUrl": OPERATOR_TERMS,
    "operator": {"name": "Valory", "domain": "www.valory.xyz"},
    "toolMetadata": {
        "tool-a": {
            "benchmark": {
                "metric": "accuracy",
                "value": 0.9,
                "window": "30d",
                "url": "https://analytics.test/a",
            }
        },
        "tool-b": {"benchmark": {"url": "http://a/b"}},
    },
}


def _record(payment_type: str = NATIVE) -> MechRecord:
    """Build a mech record as the indexer returns it."""
    return MechRecord(
        service_id=2182,
        received_requests=1020284,
        self_delivered=896660,
        delivered_by_others=123617,
        created_at=CREATED_AT,
        payment_type=payment_type,
        metadata_hash="0x" + "d" * 64,
    )


class TestPaymentLabel:
    """A payment type hash names its method, or "unknown"."""

    @pytest.mark.parametrize(
        ("payment_type", "expected"),
        [
            (NATIVE, "native"),
            (NATIVE[2:], "native"),
            (NATIVE.upper(), "native"),
            (USDC, "usdc"),
            (
                "0x3679d66ef546e66ce9057c4a052f317b135bc8e8c509638f7966edfd4fcf45e9",
                "olas",
            ),
            (
                "0x803dd08fe79d91027fc9024e254a0942372b92f3ccabc1bd19f4a5c2b251c316",
                "native_nvm",
            ),
            (
                "0x0d6fd99afa9c4c580fab5e341922c2a5c4b61d880da60506193d7bf88944dd14",
                "usdc_nvm",
            ),
            ("0x" + "0" * 64, "unknown"),
            ("", "unknown"),
        ],
        ids=[
            "native",
            "native_no_prefix",
            "native_upper",
            "usdc",
            "olas",
            "native_nvm",
            "usdc_nvm",
            "unknown_hash",
            "empty",
        ],
    )
    def test_label(self, payment_type: str, expected: str) -> None:
        """Every known type has a name; anything else is unknown, never a guess."""
        assert payment_label(payment_type) == expected


@pytest.mark.parametrize(
    "payment_type, expected",
    [
        (PaymentType.NATIVE, "native"),
        (PaymentType.NATIVE_NVM, "native"),
        (PaymentType.OLAS_TOKEN, "olas"),
        (PaymentType.USDC_TOKEN, "usdc"),
        (PaymentType.TOKEN_NVM_USDC, "usdc"),
    ],
)
def test_payment_asset_names_what_the_mech_is_settled_in(
    payment_type: PaymentType, expected: str
) -> None:
    """A subscription is settled in the same asset as its pay-per-request kin."""
    assert payment_asset(payment_type) == expected


class TestClaimedOperator:
    """The operator claim is passed on as data and checked against the domain."""

    def test_no_operator_block_means_no_claim_and_no_lookup(self) -> None:
        """Without a claim there is nothing to check, so no registry call is made."""
        with patch(f"{MANAGER}.query_erc8004_agent_id") as lookup:
            assert (
                claimed_operator("gnosis", 100, 2182, {"termsUrl": OPERATOR_TERMS})
                is None
            )
        lookup.assert_not_called()

    def test_a_verified_claim(self) -> None:
        """The agent id is looked up by service, and the domain checked with it."""
        with (
            patch(f"{MANAGER}.query_erc8004_agent_id", return_value=516) as lookup,
            patch(
                f"{MANAGER}.verify_domain", return_value=DomainVerification(True)
            ) as verify,
        ):
            block = claimed_operator("optimism", 10, 195, OPERATOR_MANIFEST)
        assert block == {
            "domain": "www.valory.xyz",
            "url": "https://www.valory.xyz",
            "domain_verified": True,
            "claimed_name": "Valory",
            "name_note": NAME_NOTE,
        }
        assert "name" not in block
        lookup.assert_called_once_with("optimism", 195)
        verify.assert_called_once_with("www.valory.xyz", 10, 516)

    def test_a_lookalike_domain_is_verified_only_as_itself(self) -> None:
        """A verified domain proves the domain; the name it claims stays a claim."""
        manifest = {"operator": {"name": "Valory AG", "domain": "valory-mechs.xyz"}}
        with (
            patch(f"{MANAGER}.query_erc8004_agent_id", return_value=2182),
            patch(f"{MANAGER}.verify_domain", return_value=DomainVerification(True)),
        ):
            block = claimed_operator("gnosis", 100, 2182, manifest)
        assert block is not None
        assert block["domain"] == "valory-mechs.xyz"
        assert block["domain_verified"] is True
        assert block["claimed_name"] == "Valory AG"
        assert block["name_note"] == NAME_NOTE

    def test_an_unverified_claim_carries_the_reason(self) -> None:
        """The domain check's note reaches the report."""
        with (
            patch(f"{MANAGER}.query_erc8004_agent_id", return_value=2182),
            patch(
                f"{MANAGER}.verify_domain",
                return_value=DomainVerification(False, "no proof"),
            ),
        ):
            block = claimed_operator("gnosis", 100, 2182, OPERATOR_MANIFEST)
        assert block is not None
        assert block["domain_verified"] is False
        assert block["verification_note"] == "no proof"

    def test_a_service_without_an_identity_says_so_without_a_fetch(self) -> None:
        """No agent id is a known answer: the note says there is no identity."""
        with (
            patch(f"{MANAGER}.query_erc8004_agent_id", return_value=None),
            patch("mech_client.domain.operator.requests.get") as get,
        ):
            block = claimed_operator("gnosis", 100, 2182, OPERATOR_MANIFEST)
        assert block is not None
        assert block["domain_verified"] is False
        assert block["verification_note"] == NO_AGENT_ID_NOTE
        get.assert_not_called()

    @pytest.mark.parametrize(
        "error",
        [SubgraphError("no registry"), RuntimeError("transport down")],
        ids=["subgraph_error", "transport_error"],
    )
    def test_a_failed_lookup_is_unverified_not_an_error(self, error: Exception) -> None:
        """A registry outage leaves the domain unverified and logs why; the claim stays."""
        with (
            patch(f"{MANAGER}.query_erc8004_agent_id", side_effect=error),
            patch(f"{MANAGER}.verify_domain") as verify,
            patch(f"{MANAGER}.logger") as logger,
        ):
            block = claimed_operator("gnosis", 100, 2182, OPERATOR_MANIFEST)
        assert block is not None
        assert block["claimed_name"] == "Valory"
        assert block["domain_verified"] is False
        assert block["verification_note"] == DOMAIN_CHECK_FAILED_NOTE
        assert block["verification_note"] != NO_AGENT_ID_NOTE
        verify.assert_not_called()
        logger.warning.assert_called_once()

    @pytest.mark.parametrize(
        "error",
        [RecursionError("too deep"), RuntimeError("boom"), ValueError("bad")],
        ids=["recursion", "runtime", "value"],
    )
    def test_a_domain_check_that_blows_up_is_unverified_not_an_error(
        self, error: Exception
    ) -> None:
        """Nothing the proof fetch raises escapes; the claim stays, unverified, with the note."""
        with patch(f"{MANAGER}.query_erc8004_agent_id", return_value=2182), patch(
            f"{MANAGER}.verify_domain", side_effect=error
        ), patch(f"{MANAGER}.logger") as logger:
            block = claimed_operator("gnosis", 100, 2182, OPERATOR_MANIFEST)
        assert block is not None
        assert block["claimed_name"] == "Valory"
        assert block["domain_verified"] is False
        assert block["verification_note"] == DOMAIN_CHECK_FAILED_NOTE
        logger.warning.assert_called_once()


class TestMechReport:
    """mech_report extends terms_report with the operator, benchmarks, record and payment."""

    @pytest.fixture
    def manager(self) -> ToolManager:
        """A manager on Gnosis, with no network behind it."""
        with (
            patch(f"{MANAGER}.EthereumApi"),
            patch(
                f"{MANAGER}.get_mech_config",
                return_value=create_mock_mech_config(),
            ),
        ):
            return ToolManager(chain_config="gnosis")

    @pytest.fixture
    def offline(self) -> Any:
        """A resolver that says the mech is not Valory operated."""
        with patch(
            f"{IDENTIFICATION}.socket.getaddrinfo", side_effect=_resolver("not_valory")
        ):
            yield

    @pytest.mark.usefixtures("offline")
    def test_full_report(self, manager: ToolManager) -> None:
        """Every section is present, and the benchmark value is dropped."""
        with (
            patch(f"{MANAGER}.query_mech_record", return_value=_record()) as record,
            patch(
                f"{MANAGER}.claimed_operator",
                return_value={"claimed_name": "Valory", "domain_verified": True},
            ) as claim,
        ):
            report = manager.mech_report(GNOSIS_MECH, OPERATOR_MANIFEST)
        record.assert_called_once_with("gnosis", GNOSIS_MECH)
        claim.assert_called_once_with("gnosis", 100, 2182, OPERATOR_MANIFEST)
        assert report["valory_operated"] is False
        assert report["terms_url"] == OPERATOR_TERMS
        assert report["operator"] == {"claimed_name": "Valory", "domain_verified": True}
        assert report["benchmarks"] == {"tool-a": "https://analytics.test/a"}
        assert report["benchmark_note"] == BENCHMARK_NOTE
        assert report["delivery"]["received_requests"] == 1020284
        assert report["delivery"]["note"] == DELIVERY_NOTE
        assert report["payment"] == {"type": "native", "note": PAYMENT_NOTE}

    @pytest.mark.usefixtures("offline")
    def test_published_expected_costs_are_passed_on_as_guidance(
        self, manager: ToolManager
    ) -> None:
        """Each tool's expected cost is reported as published, amount as a string, with its note."""
        manifest = {
            **OPERATOR_MANIFEST,
            "toolMetadata": {
                "tool-a": {"expectedCost": {"asset": "native", "amount": "12000000000000000"}},
                "tool-b": {"expectedCost": {"asset": "usdc", "amount": "0"}},
            },
        }
        with (
            patch(f"{MANAGER}.query_mech_record", return_value=_record()),
            patch(f"{MANAGER}.claimed_operator", return_value=None),
        ):
            report = manager.mech_report(GNOSIS_MECH, manifest)
        assert report["payment"] == {
            "type": "native",
            "note": PAYMENT_NOTE,
            "expected_costs": {"tool-a": {"asset": "native", "amount": "12000000000000000"}},
            "expected_cost_note": EXPECTED_COST_NOTE,
        }

    @pytest.mark.usefixtures("offline")
    def test_a_given_record_is_not_queried_again(self, manager: ToolManager) -> None:
        """A caller that already has the record hands it in; no second query."""
        with (
            patch(f"{MANAGER}.query_mech_record") as query,
            patch(f"{MANAGER}.claimed_operator", return_value=None),
        ):
            report = manager.mech_report(GNOSIS_MECH, {}, _record(USDC))
        query.assert_not_called()
        assert report["payment"]["type"] == "usdc"
        assert "operator" not in report
        assert "benchmarks" not in report
        assert "benchmark_note" not in report

    @pytest.mark.parametrize(
        "metadata", [None, [], "manifest", 7], ids=["none", "list", "string", "int"]
    )
    def test_an_unreadable_manifest_means_no_report(
        self, manager: ToolManager, metadata: Any
    ) -> None:
        """Nothing is reported from a document that is not an object, not even the record."""
        with (
            patch(f"{MANAGER}.query_mech_record") as query,
            pytest.raises(ManifestError, match=f"{GNOSIS_MECH} could not be read"),
        ):
            manager.mech_report(GNOSIS_MECH, metadata)
        query.assert_not_called()

    @pytest.mark.usefixtures("offline")
    def test_a_record_that_cannot_be_read_propagates(
        self, manager: ToolManager
    ) -> None:
        """A subgraph failure is the caller's to handle; no partial report is made."""
        with (
            patch(
                f"{MANAGER}.query_mech_record", side_effect=SubgraphError("not indexed")
            ),
            pytest.raises(SubgraphError, match="not indexed"),
        ):
            manager.mech_report(GNOSIS_MECH, {})

    def test_the_terms_keys_are_unchanged(self, manager: ToolManager) -> None:
        """A Valory mech still gets the statement, exactly as terms_report gives it."""
        with (
            patch(
                f"{IDENTIFICATION}.socket.getaddrinfo", side_effect=_resolver("valory")
            ),
            patch(f"{MANAGER}.claimed_operator", return_value=None),
        ):
            report = manager.mech_report(GNOSIS_MECH, {}, _record())
        assert report["valory_operated"] is True
        assert report["terms"] == VALORY_TERMS_NOTICE


class TestMechReportOrTerms:
    """Before paying, the terms always come back; the rest only when it can be read."""

    @pytest.fixture
    def manager(self) -> ToolManager:
        """A manager on Gnosis, with no network behind it."""
        with (
            patch(f"{MANAGER}.EthereumApi"),
            patch(
                f"{MANAGER}.get_mech_config",
                return_value=create_mock_mech_config(),
            ),
        ):
            return ToolManager(chain_config="gnosis")

    @pytest.fixture(autouse=True)
    def offline(self) -> Any:
        """A resolver that says the mech is not Valory operated."""
        with patch(
            f"{IDENTIFICATION}.socket.getaddrinfo", side_effect=_resolver("not_valory")
        ):
            yield

    @pytest.mark.parametrize(
        "metadata", [None, [], "manifest"], ids=["none", "list", "string"]
    )
    def test_an_unreadable_manifest_gives_the_terms_and_a_note(
        self, manager: ToolManager, metadata: Any
    ) -> None:
        """No manifest means no operator or record, but the terms and why."""
        with patch(f"{MANAGER}.query_mech_record") as query:
            report = manager.mech_report_or_terms(GNOSIS_MECH, metadata)
        assert report == {
            "valory_operated": False,
            "report_note": MANIFEST_UNREADABLE_NOTE,
        }
        query.assert_not_called()

    @pytest.mark.parametrize(
        "error",
        [SubgraphError("not indexed"), TimeoutError(), RuntimeError("transport")],
        ids=["subgraph_error", "timeout", "transport"],
    )
    def test_an_unreadable_record_gives_the_terms_and_a_note(
        self, manager: ToolManager, error: Exception
    ) -> None:
        """An indexer failure keeps the terms, including the operator's link."""
        with (
            patch(f"{MANAGER}.query_mech_record", side_effect=error),
            patch(f"{MANAGER}.claimed_operator") as claim,
            patch(f"{MANAGER}.logger") as logger,
        ):
            report = manager.mech_report_or_terms(GNOSIS_MECH, OPERATOR_MANIFEST)
        assert report["valory_operated"] is False
        assert report["terms_url"] == OPERATOR_TERMS
        assert type(error).__name__ in report["report_note"]
        assert "only the terms are reported" in report["report_note"]
        assert "delivery" not in report and "operator" not in report
        claim.assert_not_called()
        logger.warning.assert_called_once()

    def test_a_readable_record_gives_the_full_report(self, manager: ToolManager) -> None:
        """With the record in hand it is the full report, queried once."""
        with (
            patch(f"{MANAGER}.query_mech_record", return_value=_record()) as query,
            patch(f"{MANAGER}.claimed_operator", return_value=None),
        ):
            report = manager.mech_report_or_terms(
                GNOSIS_MECH, {"termsUrl": OPERATOR_TERMS}
            )
        query.assert_called_once_with("gnosis", GNOSIS_MECH)
        assert report["delivery"]["received_requests"] == 1020284
        assert report["payment"]["type"] == "native"
        assert "report_note" not in report


class TestDeliveryRecord:
    """The record is shaped with an ISO 8601 UTC time and a whole-day age."""

    def test_shape(self) -> None:
        """Counters pass through, the time is ISO UTC, the age counts whole days."""
        now = CREATED_AT + timedelta(days=491, hours=5)
        with patch(f"{MANAGER}.datetime") as clock:
            clock.now.return_value = now
            delivery = ToolManager.delivery_record(_record())
        assert delivery == {
            "received_requests": 1020284,
            "self_delivered": 896660,
            "delivered_by_others": 123617,
            "since": "2025-06-04T16:35:20+00:00",
            "age_days": 491,
            "note": DELIVERY_NOTE,
        }

    def test_a_future_creation_time_is_not_a_negative_age(self) -> None:
        """A clock behind the chain yields zero days, never a negative count."""
        with patch(f"{MANAGER}.datetime") as clock:
            clock.now.return_value = CREATED_AT - timedelta(days=2)
            assert ToolManager.delivery_record(_record())["age_days"] == 0
