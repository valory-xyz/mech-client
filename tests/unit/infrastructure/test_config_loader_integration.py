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

"""Integration tests for configuration loader with real mechs.json file."""

import pytest

from mech_client.infrastructure.config import get_mech_config


class TestGetMechConfigIntegration:
    """Integration tests that load actual mechs.json file."""

    def test_load_gnosis_config_with_nvm_subscription(self) -> None:
        """Test loading gnosis config handles nvm_subscription field correctly.

        This test loads the actual mechs.json file which contains nvm_subscription
        for gnosis chain. The loader should exclude this field when creating MechConfig.
        """
        config = get_mech_config("gnosis")

        # Verify core config loaded
        assert config is not None
        assert config.mech_marketplace_contract is not None
        assert config.complementary_metadata_hash_address is not None
        assert config.rpc_url is not None
        assert config.ledger_config is not None
        assert config.ledger_config.chain_id == 100

        # Verify MechConfig doesn't have nvm_subscription attribute
        assert not hasattr(config, "nvm_subscription")

    def test_load_base_config_with_nvm_subscription(self) -> None:
        """Test loading base config handles nvm_subscription field correctly.

        Base chain also has nvm_subscription in mechs.json.
        """
        config = get_mech_config("base")

        # Verify core config loaded
        assert config is not None
        assert config.mech_marketplace_contract is not None
        assert config.ledger_config.chain_id == 8453

        # Verify MechConfig doesn't have nvm_subscription attribute
        assert not hasattr(config, "nvm_subscription")

    def test_load_polygon_config_without_nvm_subscription(self) -> None:
        """Test loading polygon config (no nvm_subscription field)."""
        config = get_mech_config("polygon")

        # Verify core config loaded
        assert config is not None
        assert config.mech_marketplace_contract is not None
        assert config.ledger_config.chain_id == 137

    def test_load_optimism_config_without_nvm_subscription(self) -> None:
        """Test loading optimism config (no nvm_subscription field)."""
        config = get_mech_config("optimism")

        # Verify core config loaded
        assert config is not None
        assert config.mech_marketplace_contract is not None
        assert config.ledger_config.chain_id == 10

    def test_all_chains_load_successfully(self) -> None:
        """Test all chains in mechs.json can be loaded without errors."""
        chains = ["gnosis", "base", "polygon", "optimism"]

        for chain in chains:
            config = get_mech_config(chain)
            assert config is not None
            assert config.mech_marketplace_contract is not None
            assert config.ledger_config is not None

    def test_gnosis_config_has_expected_fields(self) -> None:
        """Test gnosis config has all expected MechConfig fields."""
        config = get_mech_config("gnosis")

        # Required MechConfig fields
        assert config.complementary_metadata_hash_address is not None
        assert config.rpc_url is not None
        assert config.ledger_config is not None
        assert config.gas_limit > 0
        assert config.transaction_url is not None
        assert config.subgraph_url is not None
        assert config.price > 0
        assert config.mech_marketplace_contract is not None

    def test_ledger_config_fields_populated(self) -> None:
        """Test ledger_config is properly populated for all chains."""
        chains = ["gnosis", "base", "polygon", "optimism"]

        for chain in chains:
            config = get_mech_config(chain)
            ledger_config = config.ledger_config

            # Verify all ledger config fields populated
            assert ledger_config.address is not None
            assert ledger_config.chain_id > 0
            assert isinstance(ledger_config.poa_chain, bool)
            assert ledger_config.default_gas_price_strategy is not None
            assert isinstance(ledger_config.is_gas_estimation_enabled, bool)
