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

"""Tests for infrastructure.nvm.config."""

import os
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from mech_client.infrastructure.nvm.config import NVMConfig


class TestNVMConfig:
    """Tests for NVMConfig."""

    @pytest.fixture
    def sample_mechs_content(self) -> str:
        """Sample mechs.json content."""
        return """
{
  "gnosis": {
    "service_registry_contract": "0x9338b5153AE39BB89f50468E608eD9d764B755fD",
    "mech_marketplace_contract": "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd",
    "ledger_config": {
      "address": "https://rpc.gnosischain.com",
      "chain_id": 100,
      "poa_chain": false,
      "default_gas_price_strategy": "eip1559",
      "is_gas_estimation_enabled": false
    },
    "nvm_subscription": {
      "subscription_nft_address": "0x1234567890123456789012345678901234567890",
      "receiver_plan": "0x1111111111111111111111111111111111111111",
      "token_address": "0x0000000000000000000000000000000000000000",
      "plan_did": "did:nv:test123",
      "subscription_credits": "100",
      "plan_fee_nvm": "500000",
      "plan_price_mechs": "500000"
    }
  }
}
"""

    @pytest.fixture
    def sample_networks_content(self) -> str:
        """Sample networks.json content."""
        return """
{
  "GNOSIS": {
    "etherscanUrl": "https://gnosisscan.io",
    "nativeToken": "xDAI",
    "nvm": {
      "web3ProviderUri": "https://rpc.gnosischain.com",
      "marketplaceUri": "https://marketplace.gnosis.nvm",
      "neverminedNodeUri": "https://node.gnosis.nvm",
      "neverminedNodeAddress": "0x2222222222222222222222222222222222222222",
      "subscription_id": 1
    }
  }
}
"""

    def test_requires_token_approval_gnosis(self) -> None:
        """Test token approval not required for Gnosis (zero address)."""
        config = NVMConfig(
            chain_config="gnosis",
            chain_id=100,
            network_name="GNOSIS",
            plan_did="did:nvm:test",
            subscription_credits="100",
            plan_fee_nvm="500000",
            plan_price_mechs="500000",
            subscription_nft_address="0x" + "1" * 40,
            receiver_plan="0x" + "3" * 40,
            token_address="0x0000000000000000000000000000000000000000",  # nosec
            web3_provider_uri="https://rpc.gnosischain.com",
            marketplace_uri="https://marketplace.nvm",
            nevermined_node_uri="https://node.nvm",
            nevermined_node_address="0x" + "4" * 40,
            subscription_id="1",
            etherscan_url="https://gnosisscan.io",
            native_token="xDAI",
        )

        assert config.requires_token_approval() is False

    def test_requires_token_approval_base(self) -> None:
        """Test token approval required for Base (USDC address)."""
        config = NVMConfig(
            chain_config="base",
            chain_id=8453,
            network_name="BASE",
            plan_did="did:nvm:test",
            subscription_credits="100",
            plan_fee_nvm="5000000",
            plan_price_mechs="5000000",
            subscription_nft_address="0x" + "1" * 40,
            receiver_plan="0x" + "3" * 40,
            token_address="0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",  # USDC on Base
            web3_provider_uri="https://mainnet.base.org",
            marketplace_uri="https://marketplace.nvm",
            nevermined_node_uri="https://node.nvm",
            nevermined_node_address="0x" + "4" * 40,
            subscription_id="1",
            etherscan_url="https://basescan.org",
            native_token="ETH",
        )

        assert config.requires_token_approval() is True

    def test_get_transaction_value_gnosis(self) -> None:
        """Test transaction value for Gnosis (native payment)."""
        config = NVMConfig(
            chain_config="gnosis",
            chain_id=100,
            network_name="GNOSIS",
            plan_did="did:nvm:test",
            subscription_credits="100",
            plan_fee_nvm="500000",
            plan_price_mechs="400000",
            subscription_nft_address="0x" + "1" * 40,
            receiver_plan="0x" + "3" * 40,
            token_address="0x0000000000000000000000000000000000000000",  # nosec
            web3_provider_uri="https://rpc.gnosischain.com",
            marketplace_uri="https://marketplace.nvm",
            nevermined_node_uri="https://node.nvm",
            nevermined_node_address="0x" + "4" * 40,
            subscription_id="1",
            etherscan_url="https://gnosisscan.io",
            native_token="xDAI",
        )

        assert config.get_transaction_value() == 900000  # 500000 + 400000

    def test_get_transaction_value_base(self) -> None:
        """Test transaction value for Base (USDC payment, no native value)."""
        config = NVMConfig(
            chain_config="base",
            chain_id=8453,
            network_name="BASE",
            plan_did="did:nvm:test",
            subscription_credits="100",
            plan_fee_nvm="5000000",
            plan_price_mechs="5000000",
            subscription_nft_address="0x" + "1" * 40,
            receiver_plan="0x" + "3" * 40,
            token_address="0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",  # USDC
            web3_provider_uri="https://mainnet.base.org",
            marketplace_uri="https://marketplace.nvm",
            nevermined_node_uri="https://node.nvm",
            nevermined_node_address="0x" + "4" * 40,
            subscription_id="1",
            etherscan_url="https://basescan.org",
            native_token="ETH",
        )

        assert config.get_transaction_value() == 0  # No native token value

    def test_get_total_payment_amount(self) -> None:
        """Test total payment amount calculation."""
        config = NVMConfig(
            chain_config="gnosis",
            chain_id=100,
            network_name="GNOSIS",
            plan_did="did:nvm:test",
            subscription_credits="100",
            plan_fee_nvm="500000",
            plan_price_mechs="400000",
            subscription_nft_address="0x" + "1" * 40,
            receiver_plan="0x" + "3" * 40,
            token_address="0x0000000000000000000000000000000000000000",  # nosec
            web3_provider_uri="https://rpc.gnosischain.com",
            marketplace_uri="https://marketplace.nvm",
            nevermined_node_uri="https://node.nvm",
            nevermined_node_address="0x" + "4" * 40,
            subscription_id="1",
            etherscan_url="https://gnosisscan.io",
            native_token="xDAI",
        )

        assert config.get_total_payment_amount() == 900000  # 500000 + 400000

    @patch.dict(os.environ, {"MECHX_CHAIN_RPC": "https://custom-rpc.example.com"})
    def test_post_init_rpc_override(self) -> None:
        """Test __post_init__ overrides web3_provider_uri with MECHX_CHAIN_RPC."""
        config = NVMConfig(
            chain_config="gnosis",
            chain_id=100,
            network_name="GNOSIS",
            plan_did="did:nvm:test",
            subscription_credits="100",
            plan_fee_nvm="500000",
            plan_price_mechs="500000",
            subscription_nft_address="0x" + "1" * 40,
            receiver_plan="0x" + "3" * 40,
            token_address="0x0000000000000000000000000000000000000000",  # nosec
            web3_provider_uri="https://rpc.gnosischain.com",
            marketplace_uri="https://marketplace.nvm",
            nevermined_node_uri="https://node.nvm",
            nevermined_node_address="0x" + "4" * 40,
            subscription_id="1",
            etherscan_url="https://gnosisscan.io",
            native_token="xDAI",
        )

        assert config.web3_provider_uri == "https://custom-rpc.example.com"

    @patch("builtins.open", new_callable=mock_open)
    @patch("pathlib.Path.exists")
    def test_from_chain_gnosis(
        self,
        mock_exists: MagicMock,
        mock_file: MagicMock,
        sample_mechs_content: str,
        sample_networks_content: str,
    ) -> None:
        """Test loading configuration from chain (gnosis)."""
        mock_exists.return_value = True

        # Mock file reads - mechs.json and networks.json
        def file_content(path, *args, **kwargs):
            if "networks.json" in str(path):
                return mock_open(read_data=sample_networks_content)()
            if "mechs.json" in str(path):
                return mock_open(read_data=sample_mechs_content)()
            return mock_open(read_data="")()

        mock_file.side_effect = file_content

        config = NVMConfig.from_chain("gnosis")

        assert config.chain_config == "gnosis"
        assert config.chain_id == 100
        assert config.network_name == "GNOSIS"
        assert config.plan_did == "did:nv:test123"
        assert config.subscription_nft_address == "0x1234567890123456789012345678901234567890"

    def test_from_chain_unsupported_chain(self) -> None:
        """Test from_chain raises ValueError for unsupported chains."""
        with pytest.raises(
            ValueError, match="NVM subscriptions not supported for chain"
        ):
            NVMConfig.from_chain("polygon")

    @patch("pathlib.Path.exists")
    def test_from_chain_missing_mechs_file(self, mock_exists: MagicMock) -> None:
        """Test from_chain raises FileNotFoundError if mechs.json missing."""
        mock_exists.return_value = False

        with pytest.raises(FileNotFoundError, match="Configuration file not found"):
            NVMConfig.from_chain("gnosis")


class TestNVMConfigFromChainErrors:
    """Tests for NVMConfig.from_chain error branches."""

    @patch("pathlib.Path.exists", return_value=True)
    @patch("builtins.open", new_callable=mock_open)
    def test_chain_not_in_mechs_raises_value_error(
        self,
        mock_file: MagicMock,
        mock_exists: MagicMock,
    ) -> None:
        """Test that ValueError is raised when chain is absent from mechs.json."""
        import json  # pylint: disable=import-outside-toplevel

        # mechs.json contains only 'other_chain', not 'gnosis'
        mock_file.return_value.read.return_value = json.dumps({"other_chain": {}})

        with patch("json.load", return_value={"other_chain": {}}):
            with pytest.raises(ValueError, match="not found in mechs.json"):
                NVMConfig.from_chain("gnosis")

    @patch("pathlib.Path.exists", return_value=True)
    @patch("builtins.open", new_callable=mock_open)
    def test_missing_nvm_subscription_key_raises_value_error(
        self,
        mock_file: MagicMock,
        mock_exists: MagicMock,
    ) -> None:
        """Test that ValueError is raised when nvm_subscription key is absent from chain data."""
        mechs_data = {
            "gnosis": {
                "ledger_config": {
                    "address": "https://rpc.gnosischain.com",
                    "chain_id": 100,
                    "poa_chain": False,
                    "default_gas_price_strategy": "eip1559",
                    "is_gas_estimation_enabled": False,
                },
                "other_key": "val",
                # 'nvm_subscription' is deliberately absent
            }
        }

        with patch("json.load", return_value=mechs_data):
            with pytest.raises(
                ValueError, match="NVM subscription configuration not found"
            ):
                NVMConfig.from_chain("gnosis")

    @patch("builtins.open", new_callable=mock_open)
    def test_networks_file_not_found_raises_file_not_found_error(
        self,
        mock_file: MagicMock,
    ) -> None:
        """Test that FileNotFoundError is raised when networks.json is missing."""
        mechs_data = {
            "gnosis": {
                "ledger_config": {
                    "address": "https://rpc.gnosischain.com",
                    "chain_id": 100,
                    "poa_chain": False,
                    "default_gas_price_strategy": "eip1559",
                    "is_gas_estimation_enabled": False,
                },
                "nvm_subscription": {
                    "subscription_nft_address": "0x" + "1" * 40,
                    "receiver_plan": "0x" + "2" * 40,
                    "token_address": "0x0000000000000000000000000000000000000000",
                    "plan_did": "did:nv:test",
                    "subscription_credits": "100",
                    "plan_fee_nvm": "500000",
                    "plan_price_mechs": "500000",
                },
            }
        }

        # First call to Path.exists() is mechs.json (True), second is networks.json (False)
        exists_side_effects = [True, False]
        with patch(
            "pathlib.Path.exists", side_effect=exists_side_effects
        ) as mock_exists:
            with patch("json.load", return_value=mechs_data):
                with pytest.raises(
                    FileNotFoundError, match="Networks configuration file not found"
                ):
                    NVMConfig.from_chain("gnosis")
                _ = mock_exists  # silence unused variable warning

    @patch("builtins.open", new_callable=mock_open)
    def test_network_key_not_in_networks_raises_value_error(
        self,
        mock_file: MagicMock,
    ) -> None:
        """Test that ValueError is raised when network key is absent from networks.json."""
        import json  # pylint: disable=import-outside-toplevel

        mechs_data = {
            "gnosis": {
                "ledger_config": {
                    "address": "https://rpc.gnosischain.com",
                    "chain_id": 100,
                    "poa_chain": False,
                    "default_gas_price_strategy": "eip1559",
                    "is_gas_estimation_enabled": False,
                },
                "nvm_subscription": {
                    "subscription_nft_address": "0x" + "1" * 40,
                    "receiver_plan": "0x" + "2" * 40,
                    "token_address": "0x0000000000000000000000000000000000000000",
                    "plan_did": "did:nv:test",
                    "subscription_credits": "100",
                    "plan_fee_nvm": "500000",
                    "plan_price_mechs": "500000",
                },
            }
        }

        # Both files exist; mechs.json loads mechs_data, networks.json loads empty {}
        with patch("pathlib.Path.exists", return_value=True):
            json_load_calls = [mechs_data, {}]
            with patch("json.load", side_effect=json_load_calls):
                with pytest.raises(
                    ValueError, match="not found in networks.json"
                ):
                    NVMConfig.from_chain("gnosis")
            _ = json  # silence unused import warning
