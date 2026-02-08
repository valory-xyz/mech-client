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

"""Tests for chain configuration and RPC validation."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from mech_client.infrastructure.config.chain_config import (
    LedgerConfig,
    get_rpc_chain_id,
)


class TestGetRpcChainId:
    """Tests for get_rpc_chain_id function."""

    @patch("mech_client.infrastructure.config.chain_config.requests.post")
    def test_get_rpc_chain_id_success(self, mock_post: MagicMock) -> None:
        """Test successful RPC chain ID query."""
        # Mock successful response with chain ID 100 (Gnosis)
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": "0x64"}  # 100 in hex
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = get_rpc_chain_id("https://rpc.gnosis.example")

        assert result == 100
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["json"]["method"] == "eth_chainId"

    @patch("mech_client.infrastructure.config.chain_config.requests.post")
    def test_get_rpc_chain_id_base_chain(self, mock_post: MagicMock) -> None:
        """Test RPC chain ID query for Base chain."""
        # Mock response with chain ID 8453 (Base)
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": "0x2105"}  # 8453 in hex
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = get_rpc_chain_id("https://base.example")

        assert result == 8453

    @patch("mech_client.infrastructure.config.chain_config.requests.post")
    def test_get_rpc_chain_id_polygon_chain(self, mock_post: MagicMock) -> None:
        """Test RPC chain ID query for Polygon chain."""
        # Mock response with chain ID 137 (Polygon)
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": "0x89"}  # 137 in hex
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = get_rpc_chain_id("https://polygon.example")

        assert result == 137

    @patch("mech_client.infrastructure.config.chain_config.requests.post")
    def test_get_rpc_chain_id_connection_error(self, mock_post: MagicMock) -> None:
        """Test RPC chain ID query with connection error."""
        mock_post.side_effect = requests.ConnectionError("Connection failed")

        result = get_rpc_chain_id("https://unreachable.example")

        assert result is None

    @patch("mech_client.infrastructure.config.chain_config.requests.post")
    def test_get_rpc_chain_id_timeout(self, mock_post: MagicMock) -> None:
        """Test RPC chain ID query with timeout."""
        mock_post.side_effect = requests.Timeout("Request timeout")

        result = get_rpc_chain_id("https://slow.example")

        assert result is None

    @patch("mech_client.infrastructure.config.chain_config.requests.post")
    def test_get_rpc_chain_id_http_error(self, mock_post: MagicMock) -> None:
        """Test RPC chain ID query with HTTP error."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("500 Error")
        mock_post.return_value = mock_response

        result = get_rpc_chain_id("https://error.example")

        assert result is None

    @patch("mech_client.infrastructure.config.chain_config.requests.post")
    def test_get_rpc_chain_id_invalid_json(self, mock_post: MagicMock) -> None:
        """Test RPC chain ID query with invalid JSON response."""
        mock_response = MagicMock()
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = get_rpc_chain_id("https://invalid.example")

        assert result is None

    @patch("mech_client.infrastructure.config.chain_config.requests.post")
    def test_get_rpc_chain_id_missing_result(self, mock_post: MagicMock) -> None:
        """Test RPC chain ID query with missing result field."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"error": "Something went wrong"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = get_rpc_chain_id("https://error.example")

        assert result is None

    @patch("mech_client.infrastructure.config.chain_config.requests.post")
    def test_get_rpc_chain_id_invalid_hex(self, mock_post: MagicMock) -> None:
        """Test RPC chain ID query with invalid hex value."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": "invalid_hex"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = get_rpc_chain_id("https://invalid.example")

        assert result is None

    @patch("mech_client.infrastructure.config.chain_config.requests.post")
    def test_get_rpc_chain_id_custom_timeout(self, mock_post: MagicMock) -> None:
        """Test RPC chain ID query with custom timeout."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": "0x64"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = get_rpc_chain_id("https://rpc.example", timeout=10.0)

        assert result == 100
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["timeout"] == 10.0


class TestLedgerConfigRpcValidation:
    """Tests for LedgerConfig RPC chain ID validation."""

    @patch("mech_client.infrastructure.config.chain_config.get_rpc_chain_id")
    @patch.dict("os.environ", {"MECHX_CHAIN_RPC": "https://base.example"})
    def test_ledger_config_warns_on_chain_mismatch(
        self, mock_get_chain_id: MagicMock
    ) -> None:
        """Test that warning is logged when RPC chain ID doesn't match config."""
        # Mock RPC returning Base chain ID (8453) when Polygon (137) is expected
        mock_get_chain_id.return_value = 8453

        with patch("mech_client.utils.logger.get_logger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            config = LedgerConfig(
                address="https://polygon.example",
                chain_id=137,  # Polygon
                poa_chain=True,
                default_gas_price_strategy="eip1559",
                is_gas_estimation_enabled=False,
            )

            # Verify warning was logged
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args[0]
            warning_format = call_args[0]
            warning_args = call_args[1:]

            assert "MECHX_CHAIN_RPC mismatch detected" in warning_format
            assert "polygon" in warning_args
            assert 137 in warning_args
            assert "base" in warning_args
            assert 8453 in warning_args

            # Verify RPC was overridden
            assert config.address == "https://base.example"

    @patch("mech_client.infrastructure.config.chain_config.get_rpc_chain_id")
    @patch.dict("os.environ", {"MECHX_CHAIN_RPC": "https://gnosis.example"})
    def test_ledger_config_no_warning_when_chains_match(
        self, mock_get_chain_id: MagicMock
    ) -> None:
        """Test that no warning is logged when RPC chain ID matches config."""
        # Mock RPC returning correct Gnosis chain ID (100)
        mock_get_chain_id.return_value = 100

        with patch("mech_client.utils.logger.get_logger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            config = LedgerConfig(
                address="https://gnosis.example",
                chain_id=100,  # Gnosis
                poa_chain=False,
                default_gas_price_strategy="eip1559",
                is_gas_estimation_enabled=False,
            )

            # Verify no warning was logged
            mock_logger.warning.assert_not_called()

            # Verify RPC was overridden
            assert config.address == "https://gnosis.example"

    @patch("mech_client.infrastructure.config.chain_config.get_rpc_chain_id")
    @patch.dict("os.environ", {}, clear=True)
    def test_ledger_config_no_warning_without_env_var(
        self, mock_get_chain_id: MagicMock
    ) -> None:
        """Test that no warning is logged when MECHX_CHAIN_RPC is not set."""
        config = LedgerConfig(
            address="https://polygon.example",
            chain_id=137,
            poa_chain=True,
            default_gas_price_strategy="eip1559",
            is_gas_estimation_enabled=False,
        )

        # Verify get_rpc_chain_id was not called
        mock_get_chain_id.assert_not_called()

        # Verify RPC was not overridden
        assert config.address == "https://polygon.example"

    @patch("mech_client.infrastructure.config.chain_config.get_rpc_chain_id")
    @patch.dict("os.environ", {"MECHX_CHAIN_RPC": "https://unreachable.example"})
    def test_ledger_config_no_warning_when_rpc_unreachable(
        self, mock_get_chain_id: MagicMock
    ) -> None:
        """Test that no warning is logged when RPC is unreachable."""
        # Mock RPC query returning None (unreachable)
        mock_get_chain_id.return_value = None

        with patch("mech_client.utils.logger.get_logger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            config = LedgerConfig(
                address="https://polygon.example",
                chain_id=137,
                poa_chain=True,
                default_gas_price_strategy="eip1559",
                is_gas_estimation_enabled=False,
            )

            # Verify no warning was logged (RPC unreachable, can't verify)
            mock_logger.warning.assert_not_called()

            # Verify RPC was still overridden
            assert config.address == "https://unreachable.example"

    @patch("mech_client.infrastructure.config.chain_config.get_rpc_chain_id")
    @patch.dict("os.environ", {"MECHX_CHAIN_RPC": "https://optimism.example"})
    def test_ledger_config_warns_for_optimism_mismatch(
        self, mock_get_chain_id: MagicMock
    ) -> None:
        """Test warning for Optimism chain mismatch."""
        # Mock RPC returning Gnosis chain ID (100) when Optimism (10) is expected
        mock_get_chain_id.return_value = 100

        with patch("mech_client.utils.logger.get_logger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            config = LedgerConfig(
                address="https://optimism.example",
                chain_id=10,  # Optimism
                poa_chain=False,
                default_gas_price_strategy="eip1559",
                is_gas_estimation_enabled=False,
            )

            # Verify warning was logged
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args[0]
            warning_format = call_args[0]
            warning_args = call_args[1:]

            assert "MECHX_CHAIN_RPC mismatch detected" in warning_format
            assert "optimism" in warning_args
            assert 10 in warning_args
            assert "gnosis" in warning_args
            assert 100 in warning_args

    @patch("mech_client.infrastructure.config.chain_config.get_rpc_chain_id")
    @patch.dict("os.environ", {"MECHX_CHAIN_RPC": "https://unknown.example"})
    def test_ledger_config_warns_for_unknown_chain(
        self, mock_get_chain_id: MagicMock
    ) -> None:
        """Test warning for unknown chain ID."""
        # Mock RPC returning unknown chain ID
        mock_get_chain_id.return_value = 99999

        with patch("mech_client.utils.logger.get_logger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            config = LedgerConfig(
                address="https://polygon.example",
                chain_id=137,
                poa_chain=True,
                default_gas_price_strategy="eip1559",
                is_gas_estimation_enabled=False,
            )

            # Verify warning was logged with unknown chain format
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args[0]
            warning_format = call_args[0]
            warning_args = call_args[1:]

            assert "MECHX_CHAIN_RPC mismatch detected" in warning_format
            assert "polygon" in warning_args
            assert 137 in warning_args
            assert "chain 99999" in warning_args
            assert 99999 in warning_args


class TestLedgerConfigEnvironmentOverrides:
    """Tests for LedgerConfig environment variable overrides."""

    @patch.dict("os.environ", {"MECHX_LEDGER_CHAIN_ID": "42161"})
    def test_ledger_config_chain_id_override(self) -> None:
        """Test that MECHX_LEDGER_CHAIN_ID overrides chain ID."""
        config = LedgerConfig(
            address="https://example.com",
            chain_id=100,
            poa_chain=False,
            default_gas_price_strategy="eip1559",
            is_gas_estimation_enabled=False,
        )

        assert config.chain_id == 42161

    @patch.dict("os.environ", {"MECHX_LEDGER_POA_CHAIN": "true"})
    def test_ledger_config_poa_chain_override(self) -> None:
        """Test that MECHX_LEDGER_POA_CHAIN overrides POA setting."""
        config = LedgerConfig(
            address="https://example.com",
            chain_id=100,
            poa_chain=False,
            default_gas_price_strategy="eip1559",
            is_gas_estimation_enabled=False,
        )

        assert config.poa_chain is True

    @patch.dict(
        "os.environ", {"MECHX_LEDGER_DEFAULT_GAS_PRICE_STRATEGY": "gas_station"}
    )
    def test_ledger_config_gas_price_strategy_override(self) -> None:
        """Test that MECHX_LEDGER_DEFAULT_GAS_PRICE_STRATEGY overrides strategy."""
        config = LedgerConfig(
            address="https://example.com",
            chain_id=100,
            poa_chain=False,
            default_gas_price_strategy="eip1559",
            is_gas_estimation_enabled=False,
        )

        assert config.default_gas_price_strategy == "gas_station"

    @patch.dict("os.environ", {"MECHX_LEDGER_IS_GAS_ESTIMATION_ENABLED": "true"})
    def test_ledger_config_gas_estimation_override(self) -> None:
        """Test that MECHX_LEDGER_IS_GAS_ESTIMATION_ENABLED overrides setting."""
        config = LedgerConfig(
            address="https://example.com",
            chain_id=100,
            poa_chain=False,
            default_gas_price_strategy="eip1559",
            is_gas_estimation_enabled=False,
        )

        assert config.is_gas_estimation_enabled is True
