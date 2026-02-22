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

"""Tests for infrastructure.config.environment module."""

from unittest.mock import patch

from mech_client.infrastructure.config.environment import EnvironmentConfig


class TestEnvironmentConfigLoading:
    """Tests for EnvironmentConfig loading from environment variables."""

    @patch.dict(
        "os.environ",
        {"MECHX_SUBGRAPH_URL": "https://custom-subgraph.example.com/"},
        clear=True,
    )
    def test_subgraph_url_loaded_from_env(self) -> None:
        """Test that MECHX_SUBGRAPH_URL is loaded and stored in mechx_subgraph_url."""
        env_config = EnvironmentConfig.load()

        assert env_config.mechx_subgraph_url == "https://custom-subgraph.example.com/"

    @patch.dict(
        "os.environ",
        {"MECHX_MECH_OFFCHAIN_URL": "https://offchain-mech.example.com/"},
        clear=True,
    )
    def test_offchain_url_loaded_from_env(self) -> None:
        """Test that MECHX_MECH_OFFCHAIN_URL is loaded and stored in mechx_mech_offchain_url."""
        env_config = EnvironmentConfig.load()

        assert (
            env_config.mechx_mech_offchain_url == "https://offchain-mech.example.com/"
        )

    @patch.dict(
        "os.environ",
        {"MECHX_GAS_LIMIT": "800000"},
        clear=True,
    )
    def test_gas_limit_loaded_from_env(self) -> None:
        """Test that MECHX_GAS_LIMIT is loaded as an integer in mechx_gas_limit."""
        env_config = EnvironmentConfig.load()

        assert env_config.mechx_gas_limit == 800000
        assert isinstance(env_config.mechx_gas_limit, int)

    @patch.dict(
        "os.environ",
        {"MECHX_TRANSACTION_URL": "https://explorer.example.com/tx/{transaction_digest}"},
        clear=True,
    )
    def test_transaction_url_loaded_from_env(self) -> None:
        """Test that MECHX_TRANSACTION_URL is loaded and stored in mechx_transaction_url."""
        env_config = EnvironmentConfig.load()

        assert (
            env_config.mechx_transaction_url
            == "https://explorer.example.com/tx/{transaction_digest}"
        )

    @patch.dict("os.environ", {}, clear=True)
    def test_all_optional_fields_are_none_when_env_empty(self) -> None:
        """Test that optional fields are None when no environment variables are set."""
        env_config = EnvironmentConfig.load()

        assert env_config.mechx_chain_rpc is None
        assert env_config.mechx_subgraph_url is None
        assert env_config.mechx_mech_offchain_url is None
        assert env_config.mechx_gas_limit is None
        assert env_config.mechx_transaction_url is None

    @patch.dict(
        "os.environ",
        {
            "MECHX_SUBGRAPH_URL": "https://sg.example.com/",
            "MECHX_GAS_LIMIT": "1000000",
            "MECHX_MECH_OFFCHAIN_URL": "https://offchain.example.com/",
            "MECHX_TRANSACTION_URL": "https://tx.example.com/{transaction_digest}",
        },
        clear=True,
    )
    def test_multiple_env_vars_loaded_simultaneously(self) -> None:
        """Test that multiple environment variables are loaded correctly at once."""
        env_config = EnvironmentConfig.load()

        assert env_config.mechx_subgraph_url == "https://sg.example.com/"
        assert env_config.mechx_gas_limit == 1000000
        assert env_config.mechx_mech_offchain_url == "https://offchain.example.com/"
        assert (
            env_config.mechx_transaction_url
            == "https://tx.example.com/{transaction_digest}"
        )
