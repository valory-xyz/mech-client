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

"""Tests for configuration loader."""

from unittest.mock import mock_open, patch

import pytest

from mech_client.infrastructure.config import LedgerConfig, MechConfig, get_mech_config


class TestGetMechConfig:
    """Tests for get_mech_config function."""

    @patch("builtins.open", side_effect=FileNotFoundError())
    def test_file_not_found_raises_error(self, mock_file: mock_open) -> None:
        """Test that missing config file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            get_mech_config("gnosis")

    @patch("builtins.open", new_callable=mock_open, read_data='invalid json')
    def test_invalid_json_raises_error(self, mock_file: mock_open) -> None:
        """Test that malformed JSON raises JSONDecodeError."""
        with pytest.raises(Exception):  # JSONDecodeError
            get_mech_config("gnosis")

    @patch("builtins.open", new_callable=mock_open, read_data='{"gnosis": {}}')
    def test_nonexistent_chain_raises_error(self, mock_file: mock_open) -> None:
        """Test that requesting non-existent chain raises KeyError."""
        with pytest.raises(KeyError):
            get_mech_config("nonexistent_chain")


class TestLedgerConfigDataclass:
    """Tests for LedgerConfig dataclass."""

    def test_ledger_config_initialization(self) -> None:
        """Test LedgerConfig can be initialized with required fields."""
        config = LedgerConfig(
            address="https://rpc.gnosischain.com",
            chain_id=100,
            poa_chain=False,
            default_gas_price_strategy="medium",
            is_gas_estimation_enabled=True,
        )

        assert config.address == "https://rpc.gnosischain.com"
        assert config.chain_id == 100
        assert config.poa_chain is False
        assert config.default_gas_price_strategy == "medium"
        assert config.is_gas_estimation_enabled is True

    @patch.dict("os.environ", {"MECHX_CHAIN_RPC": "https://custom.rpc.com"})
    def test_ledger_config_env_override(self) -> None:
        """Test that environment variables override ledger config."""
        config = LedgerConfig(
            address="https://default.rpc.com",
            chain_id=100,
            poa_chain=False,
            default_gas_price_strategy="medium",
            is_gas_estimation_enabled=True,
        )

        # __post_init__ should override with env var
        assert config.address == "https://custom.rpc.com"


class TestMechConfigDataclass:
    """Tests for MechConfig dataclass."""

    def test_config_initialization(self) -> None:
        """Test MechConfig can be initialized with required fields."""
        ledger_config = LedgerConfig(
            address="https://rpc.gnosischain.com",
            chain_id=100,
            poa_chain=False,
            default_gas_price_strategy="medium",
            is_gas_estimation_enabled=True,
        )

        config = MechConfig(
            service_registry_contract="0x" + "1" * 40,
            complementary_metadata_hash_address="0x" + "2" * 40,
            rpc_url="https://rpc.gnosischain.com",
            wss_endpoint="wss://wss.gnosischain.com",
            ledger_config=ledger_config,
            gas_limit=500000,
            transaction_url="https://explorer.com/tx/{tx_hash}",
            subgraph_url="https://subgraph.example.com",
            price=1000000000000000000,
            mech_marketplace_contract="0x" + "3" * 40,
        )

        assert config.service_registry_contract == "0x" + "1" * 40
        assert config.mech_marketplace_contract == "0x" + "3" * 40
        assert config.ledger_config.chain_id == 100
        assert config.price == 1000000000000000000

    @patch.dict("os.environ", {"MECHX_CHAIN_RPC": "https://custom.rpc.com"})
    def test_config_env_override(self) -> None:
        """Test that environment variables override config."""
        ledger_config = LedgerConfig(
            address="https://rpc.gnosischain.com",
            chain_id=100,
            poa_chain=False,
            default_gas_price_strategy="medium",
            is_gas_estimation_enabled=True,
        )

        config = MechConfig(
            service_registry_contract="0x" + "1" * 40,
            complementary_metadata_hash_address="0x" + "2" * 40,
            rpc_url="https://default.rpc.com",
            wss_endpoint="wss://default.wss.com",
            ledger_config=ledger_config,
            gas_limit=500000,
            transaction_url="https://explorer.com/tx/{tx_hash}",
            subgraph_url="https://subgraph.example.com",
            price=1000000000000000000,
            mech_marketplace_contract="0x" + "3" * 40,
        )

        # __post_init__ should override with env var
        assert config.rpc_url == "https://custom.rpc.com"
