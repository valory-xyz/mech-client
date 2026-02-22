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

from unittest.mock import MagicMock, mock_open, patch

import pytest

from mech_client.infrastructure.config import LedgerConfig, MechConfig, get_mech_config


class TestGetMechConfig:
    """Tests for get_mech_config function."""

    @patch("builtins.open", side_effect=FileNotFoundError())
    def test_file_not_found_raises_error(self, mock_file: mock_open) -> None:
        """Test that missing config file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            get_mech_config("gnosis")

    @patch.dict("os.environ", {}, clear=True)
    @patch("mech_client.infrastructure.operate.load_rpc_from_operate")
    def test_none_chain_config_uses_first_chain(
        self, mock_load_rpc: MagicMock
    ) -> None:
        """Test that passing chain_config=None uses the first chain in mechs.json."""
        mock_load_rpc.return_value = None

        # Should not raise; result must be a valid MechConfig
        config = get_mech_config(chain_config=None)

        assert config.rpc_url is not None and len(config.rpc_url) > 0

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
            complementary_metadata_hash_address="0x" + "2" * 40,
            rpc_url="https://rpc.gnosischain.com",
            ledger_config=ledger_config,
            gas_limit=500000,
            transaction_url="https://explorer.com/tx/{tx_hash}",
            subgraph_url="https://subgraph.example.com",
            price=1000000000000000000,
            mech_marketplace_contract="0x" + "3" * 40,
        )

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
            complementary_metadata_hash_address="0x" + "2" * 40,
            rpc_url="https://default.rpc.com",
            ledger_config=ledger_config,
            gas_limit=500000,
            transaction_url="https://explorer.com/tx/{tx_hash}",
            subgraph_url="https://subgraph.example.com",
            price=1000000000000000000,
            mech_marketplace_contract="0x" + "3" * 40,
        )

        # __post_init__ should override with env var
        assert config.rpc_url == "https://custom.rpc.com"


class TestLedgerConfigPriorityOrder:
    """Tests for LedgerConfig RPC configuration priority order."""

    @patch.dict("os.environ", {}, clear=True)
    def test_client_mode_uses_default_rpc(self) -> None:
        """Test that client mode uses default RPC when no env var set."""
        config = LedgerConfig(
            address="https://default.rpc.com",
            chain_id=100,
            poa_chain=False,
            default_gas_price_strategy="medium",
            is_gas_estimation_enabled=True,
            agent_mode=False,
            chain_config="gnosis",
        )

        # Should use default (no operate config loaded in client mode)
        assert config.address == "https://default.rpc.com"

    @patch.dict("os.environ", {"MECHX_CHAIN_RPC": "https://env.rpc.com"}, clear=True)
    def test_client_mode_env_var_overrides_default(self) -> None:
        """Test that client mode env var overrides default."""
        config = LedgerConfig(
            address="https://default.rpc.com",
            chain_id=100,
            poa_chain=False,
            default_gas_price_strategy="medium",
            is_gas_estimation_enabled=True,
            agent_mode=False,
            chain_config="gnosis",
        )

        # Env var should override default
        assert config.address == "https://env.rpc.com"

    @patch.dict("os.environ", {}, clear=True)
    @patch("mech_client.infrastructure.operate.load_rpc_from_operate")
    def test_agent_mode_uses_operate_config_when_available(
        self, mock_load_rpc: MagicMock
    ) -> None:
        """Test that agent mode uses operate config when available."""
        mock_load_rpc.return_value = "https://operate.rpc.com"

        config = LedgerConfig(
            address="https://default.rpc.com",
            chain_id=100,
            poa_chain=False,
            default_gas_price_strategy="medium",
            is_gas_estimation_enabled=True,
            agent_mode=True,
            chain_config="gnosis",
        )

        # Should use operate config (no env var set)
        assert config.address == "https://operate.rpc.com"
        mock_load_rpc.assert_called_once_with("gnosis")

    @patch.dict("os.environ", {}, clear=True)
    @patch("mech_client.infrastructure.operate.load_rpc_from_operate")
    def test_agent_mode_falls_back_to_default_when_operate_unavailable(
        self, mock_load_rpc: MagicMock
    ) -> None:
        """Test that agent mode falls back to default when operate config unavailable."""
        mock_load_rpc.return_value = None

        config = LedgerConfig(
            address="https://default.rpc.com",
            chain_id=100,
            poa_chain=False,
            default_gas_price_strategy="medium",
            is_gas_estimation_enabled=True,
            agent_mode=True,
            chain_config="gnosis",
        )

        # Should fall back to default when operate config returns None
        assert config.address == "https://default.rpc.com"
        mock_load_rpc.assert_called_once_with("gnosis")

    @patch.dict("os.environ", {"MECHX_CHAIN_RPC": "https://env.rpc.com"}, clear=True)
    @patch("mech_client.infrastructure.operate.load_rpc_from_operate")
    def test_agent_mode_env_var_overrides_operate_config(
        self, mock_load_rpc: MagicMock
    ) -> None:
        """Test that agent mode env var overrides operate config."""
        mock_load_rpc.return_value = "https://operate.rpc.com"

        config = LedgerConfig(
            address="https://default.rpc.com",
            chain_id=100,
            poa_chain=False,
            default_gas_price_strategy="medium",
            is_gas_estimation_enabled=True,
            agent_mode=True,
            chain_config="gnosis",
        )

        # Env var should override operate config (highest priority)
        assert config.address == "https://env.rpc.com"
        mock_load_rpc.assert_called_once_with("gnosis")

    @patch.dict("os.environ", {"MECHX_CHAIN_RPC": "https://env.rpc.com"}, clear=True)
    @patch("mech_client.infrastructure.operate.load_rpc_from_operate")
    def test_agent_mode_env_var_overrides_all(self, mock_load_rpc: MagicMock) -> None:
        """Test complete priority order in agent mode: env > operate > default."""
        mock_load_rpc.return_value = "https://operate.rpc.com"

        config = LedgerConfig(
            address="https://default.rpc.com",
            chain_id=100,
            poa_chain=False,
            default_gas_price_strategy="medium",
            is_gas_estimation_enabled=True,
            agent_mode=True,
            chain_config="gnosis",
        )

        # Priority: env var (highest) > operate config > default (lowest)
        assert config.address == "https://env.rpc.com"

    @patch.dict("os.environ", {}, clear=True)
    @patch("mech_client.infrastructure.operate.load_rpc_from_operate")
    def test_agent_mode_does_not_load_operate_when_chain_config_none(
        self, mock_load_rpc: MagicMock
    ) -> None:
        """Test that operate config not loaded when chain_config is None."""
        config = LedgerConfig(
            address="https://default.rpc.com",
            chain_id=100,
            poa_chain=False,
            default_gas_price_strategy="medium",
            is_gas_estimation_enabled=True,
            agent_mode=True,
            chain_config=None,
        )

        # Should not call load_rpc_from_operate when chain_config is None
        mock_load_rpc.assert_not_called()
        assert config.address == "https://default.rpc.com"


class TestMechConfigPriorityOrder:
    """Tests for MechConfig RPC configuration priority order."""

    @patch.dict("os.environ", {}, clear=True)
    def test_client_mode_uses_default_rpc(self) -> None:
        """Test that client mode uses default RPC when no env var set."""
        ledger_config = LedgerConfig(
            address="https://ledger.rpc.com",
            chain_id=100,
            poa_chain=False,
            default_gas_price_strategy="medium",
            is_gas_estimation_enabled=True,
        )

        config = MechConfig(
            complementary_metadata_hash_address="0x" + "2" * 40,
            rpc_url="https://default.rpc.com",
            ledger_config=ledger_config,
            gas_limit=500000,
            transaction_url="https://explorer.com/tx/{tx_hash}",
            subgraph_url="https://subgraph.example.com",
            price=1000000000000000000,
            mech_marketplace_contract="0x" + "3" * 40,
            agent_mode=False,
            chain_config="gnosis",
        )

        # Should use default (no operate config in client mode)
        assert config.rpc_url == "https://default.rpc.com"

    @patch.dict("os.environ", {"MECHX_CHAIN_RPC": "https://env.rpc.com"}, clear=True)
    def test_client_mode_env_var_overrides_default(self) -> None:
        """Test that client mode env var overrides default."""
        ledger_config = LedgerConfig(
            address="https://ledger.rpc.com",
            chain_id=100,
            poa_chain=False,
            default_gas_price_strategy="medium",
            is_gas_estimation_enabled=True,
        )

        config = MechConfig(
            complementary_metadata_hash_address="0x" + "2" * 40,
            rpc_url="https://default.rpc.com",
            ledger_config=ledger_config,
            gas_limit=500000,
            transaction_url="https://explorer.com/tx/{tx_hash}",
            subgraph_url="https://subgraph.example.com",
            price=1000000000000000000,
            mech_marketplace_contract="0x" + "3" * 40,
            agent_mode=False,
            chain_config="gnosis",
        )

        # Env var should override default
        assert config.rpc_url == "https://env.rpc.com"

    @patch.dict("os.environ", {}, clear=True)
    @patch("mech_client.infrastructure.operate.load_rpc_from_operate")
    def test_agent_mode_uses_operate_config_when_available(
        self, mock_load_rpc: MagicMock
    ) -> None:
        """Test that agent mode uses operate config when available."""
        mock_load_rpc.return_value = "https://operate.rpc.com"

        ledger_config = LedgerConfig(
            address="https://ledger.rpc.com",
            chain_id=100,
            poa_chain=False,
            default_gas_price_strategy="medium",
            is_gas_estimation_enabled=True,
        )

        config = MechConfig(
            complementary_metadata_hash_address="0x" + "2" * 40,
            rpc_url="https://default.rpc.com",
            ledger_config=ledger_config,
            gas_limit=500000,
            transaction_url="https://explorer.com/tx/{tx_hash}",
            subgraph_url="https://subgraph.example.com",
            price=1000000000000000000,
            mech_marketplace_contract="0x" + "3" * 40,
            agent_mode=True,
            chain_config="gnosis",
        )

        # Should use operate config (no env var set)
        assert config.rpc_url == "https://operate.rpc.com"
        # Called once for MechConfig (LedgerConfig is passed in already created)
        mock_load_rpc.assert_called_with("gnosis")

    @patch.dict("os.environ", {}, clear=True)
    @patch("mech_client.infrastructure.operate.load_rpc_from_operate")
    def test_agent_mode_falls_back_to_default_when_operate_unavailable(
        self, mock_load_rpc: MagicMock
    ) -> None:
        """Test that agent mode falls back to default when operate config unavailable."""
        mock_load_rpc.return_value = None

        ledger_config = LedgerConfig(
            address="https://ledger.rpc.com",
            chain_id=100,
            poa_chain=False,
            default_gas_price_strategy="medium",
            is_gas_estimation_enabled=True,
        )

        config = MechConfig(
            complementary_metadata_hash_address="0x" + "2" * 40,
            rpc_url="https://default.rpc.com",
            ledger_config=ledger_config,
            gas_limit=500000,
            transaction_url="https://explorer.com/tx/{tx_hash}",
            subgraph_url="https://subgraph.example.com",
            price=1000000000000000000,
            mech_marketplace_contract="0x" + "3" * 40,
            agent_mode=True,
            chain_config="gnosis",
        )

        # Should fall back to default
        assert config.rpc_url == "https://default.rpc.com"

    @patch.dict("os.environ", {"MECHX_CHAIN_RPC": "https://env.rpc.com"}, clear=True)
    @patch("mech_client.infrastructure.operate.load_rpc_from_operate")
    def test_agent_mode_env_var_overrides_operate_config(
        self, mock_load_rpc: MagicMock
    ) -> None:
        """Test that agent mode env var overrides operate config."""
        mock_load_rpc.return_value = "https://operate.rpc.com"

        ledger_config = LedgerConfig(
            address="https://ledger.rpc.com",
            chain_id=100,
            poa_chain=False,
            default_gas_price_strategy="medium",
            is_gas_estimation_enabled=True,
        )

        config = MechConfig(
            complementary_metadata_hash_address="0x" + "2" * 40,
            rpc_url="https://default.rpc.com",
            ledger_config=ledger_config,
            gas_limit=500000,
            transaction_url="https://explorer.com/tx/{tx_hash}",
            subgraph_url="https://subgraph.example.com",
            price=1000000000000000000,
            mech_marketplace_contract="0x" + "3" * 40,
            agent_mode=True,
            chain_config="gnosis",
        )

        # Env var should override (highest priority)
        assert config.rpc_url == "https://env.rpc.com"

    @patch.dict("os.environ", {}, clear=True)
    @patch("mech_client.infrastructure.operate.load_rpc_from_operate")
    def test_agent_mode_does_not_load_operate_when_chain_config_none(
        self, mock_load_rpc: MagicMock
    ) -> None:
        """Test that operate config not loaded when chain_config is None."""
        ledger_config = LedgerConfig(
            address="https://ledger.rpc.com",
            chain_id=100,
            poa_chain=False,
            default_gas_price_strategy="medium",
            is_gas_estimation_enabled=True,
        )

        config = MechConfig(
            complementary_metadata_hash_address="0x" + "2" * 40,
            rpc_url="https://default.rpc.com",
            ledger_config=ledger_config,
            gas_limit=500000,
            transaction_url="https://explorer.com/tx/{tx_hash}",
            subgraph_url="https://subgraph.example.com",
            price=1000000000000000000,
            mech_marketplace_contract="0x" + "3" * 40,
            agent_mode=True,
            chain_config=None,
        )

        # Should not load from operate when chain_config is None
        mock_load_rpc.assert_not_called()
        assert config.rpc_url == "https://default.rpc.com"
