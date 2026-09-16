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

"""Integration tests for configuration loader with real mechs.json file."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

import mech_client.infrastructure.config.loader as config_loader
from mech_client.infrastructure.config import get_mech_config
from mech_client.infrastructure.config.constants import CHAIN_ID_TO_NAME, MECH_CONFIGS
from mech_client.utils.constants import CHAIN_NAME_TO_ID


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

    def test_load_robinhood_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test loading robinhood config: its marketplace indexer is an SQD squid."""
        monkeypatch.delenv("MECHX_SUBGRAPH_URL", raising=False)

        config = get_mech_config("robinhood")

        assert config.ledger_config.chain_id == 4663
        assert (
            config.mech_marketplace_contract
            == "0xa45E64d13A30a51b91ae0eb182e88a40e9b18eD8"
        )
        assert (
            config.complementary_metadata_hash_address
            == "0xD1155408D58293BE0743225bcDe28b9FD0C12378"
        )
        assert (
            config.subgraph_url
            == "https://subgraph.autonolas.tech/squid/marketplace-robinhood/graphql"
        )
        assert config.subgraph_dialect == "squid"
        assert get_mech_config("gnosis").subgraph_dialect == "graph"
        assert CHAIN_ID_TO_NAME[4663] == "robinhood"
        assert CHAIN_NAME_TO_ID["robinhood"] == 4663

    def test_every_mechs_json_entry_loads_with_a_valid_dialect(self) -> None:
        """Test every chain shipped in mechs.json loads with a known dialect."""
        for chain in json.loads(MECH_CONFIGS.read_text()):
            config = get_mech_config(chain)
            assert config.mech_marketplace_contract is not None
            assert config.ledger_config is not None
            assert config.subgraph_dialect in ("graph", "squid")

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
        chains = ["gnosis", "base", "polygon", "optimism", "robinhood"]

        for chain in chains:
            config = get_mech_config(chain)
            ledger_config = config.ledger_config

            # Verify all ledger config fields populated
            assert ledger_config.address is not None
            assert ledger_config.chain_id > 0
            assert isinstance(ledger_config.poa_chain, bool)
            assert ledger_config.default_gas_price_strategy is not None
            assert isinstance(ledger_config.is_gas_estimation_enabled, bool)

    def test_unknown_subgraph_dialect_fails_when_the_config_loads(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test a mistyped subgraph_dialect in mechs.json fails at load, not at query."""
        configs = json.loads(MECH_CONFIGS.read_text())
        configs["robinhood"]["subgraph_dialect"] = "hasura"
        mistyped = tmp_path / "mechs.json"
        mistyped.write_text(json.dumps(configs))
        monkeypatch.setattr(config_loader, "MECH_CONFIGS", mistyped)

        with pytest.raises(
            ValueError, match="Unknown subgraph_dialect 'hasura' for chain 'robinhood'"
        ):
            get_mech_config("robinhood")

    def test_missing_subgraph_dialect_fails_when_the_config_loads(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test a chain entry without subgraph_dialect fails instead of defaulting."""
        configs = json.loads(MECH_CONFIGS.read_text())
        del configs["robinhood"]["subgraph_dialect"]
        incomplete = tmp_path / "mechs.json"
        incomplete.write_text(json.dumps(configs))
        monkeypatch.setattr(config_loader, "MECH_CONFIGS", incomplete)

        with pytest.raises(ValueError, match="'robinhood' has no subgraph_dialect"):
            get_mech_config("robinhood")

    def test_subgraph_url_override_warns_on_a_squid_chain(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test overriding the URL of a squid chain warns that the dialect is unchanged."""
        monkeypatch.setenv("MECHX_SUBGRAPH_URL", "https://subgraph.example/graphql")

        with patch(
            "mech_client.infrastructure.config.chain_config.logger"
        ) as mock_logger:
            config = get_mech_config("robinhood")

        assert config.subgraph_url == "https://subgraph.example/graphql"
        assert config.subgraph_dialect == "squid"
        mock_logger.warning.assert_called_once()
        assert "robinhood" in mock_logger.warning.call_args[0]

