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

"""Tests for subgraph queries."""

import json
from dataclasses import replace
from unittest.mock import MagicMock, patch

import pytest

from mech_client.infrastructure.config import get_mech_config
from mech_client.infrastructure.config.constants import MECH_CONFIGS
from mech_client.infrastructure.subgraph.queries import (
    CHAIN_TO_MECH_FACTORY_TO_MECH_TYPE,
    RESULTS_LIMIT,
    query_mm_mechs_info,
)
from mech_client.utils.constants import CHAIN_NAME_TO_ID
from mech_client.utils.errors import SubgraphError


class TestChainToMechFactoryMapping:
    """Tests for CHAIN_TO_MECH_FACTORY_TO_MECH_TYPE constant."""

    def test_mapping_contains_all_chains(self) -> None:
        """Test mapping contains all supported chains."""
        expected_chains = {"gnosis", "base", "optimism", "polygon", "robinhood"}
        assert set(CHAIN_TO_MECH_FACTORY_TO_MECH_TYPE.keys()) == expected_chains

    def test_robinhood_mapping(self) -> None:
        """Test robinhood chain factory mappings."""
        robinhood_mapping = CHAIN_TO_MECH_FACTORY_TO_MECH_TYPE["robinhood"]
        assert len(robinhood_mapping) == 2
        assert (
            robinhood_mapping["0x04b0007b2aFb398015B76e5f22993a1fddF83644"]
            == "Fixed Price Native"
        )
        assert (
            robinhood_mapping["0x7Fd1F4b764fA41d19fe3f63C85d12bf64d2bbf68"]
            == "Fixed Price Token USDC"
        )

    def test_every_chain_with_a_subgraph_has_a_factory_mapping(self) -> None:
        """Test mech list can type every chain it can query, keyed by known chains."""
        configs = json.loads(MECH_CONFIGS.read_text())
        with_subgraph = {name for name, cfg in configs.items() if cfg["subgraph_url"]}

        assert set(CHAIN_TO_MECH_FACTORY_TO_MECH_TYPE) == with_subgraph
        assert set(CHAIN_TO_MECH_FACTORY_TO_MECH_TYPE) <= set(CHAIN_NAME_TO_ID)

    def test_gnosis_mapping(self) -> None:
        """Test gnosis chain factory mappings."""
        gnosis_mapping = CHAIN_TO_MECH_FACTORY_TO_MECH_TYPE["gnosis"]
        assert len(gnosis_mapping) == 3
        assert (
            gnosis_mapping["0x8b299c20F87e3fcBfF0e1B86dC0acC06AB6993EF"]
            == "Fixed Price Native"
        )
        assert (
            gnosis_mapping["0x31ffDC795FDF36696B8eDF7583A3D115995a45FA"]
            == "Fixed Price Token"
        )
        assert (
            gnosis_mapping["0x65fd74C29463afe08c879a3020323DD7DF02DA57"]
            == "NvmSubscription Native"
        )

    def test_base_mapping(self) -> None:
        """Test base chain factory mappings."""
        base_mapping = CHAIN_TO_MECH_FACTORY_TO_MECH_TYPE["base"]
        assert len(base_mapping) == 4
        assert (
            base_mapping["0x2E008211f34b25A7d7c102403c6C2C3B665a1abe"]
            == "Fixed Price Native"
        )
        assert (
            base_mapping["0x97371B1C0cDA1D04dFc43DFb50a04645b7Bc9BEe"]
            == "Fixed Price Token"
        )
        assert (
            base_mapping["0x847bBE8b474e0820215f818858e23F5f5591855A"]
            == "NvmSubscription Native"
        )
        assert (
            base_mapping["0x7beD01f8482fF686F025628e7780ca6C1f0559fc"]
            == "NvmSubscription Token USDC"
        )

    def test_optimism_mapping(self) -> None:
        """Test optimism chain factory mappings."""
        optimism_mapping = CHAIN_TO_MECH_FACTORY_TO_MECH_TYPE["optimism"]
        assert len(optimism_mapping) == 4
        assert (
            optimism_mapping["0xf76953444C35F1FcE2F6CA1b167173357d3F5C17"]
            == "Fixed Price Native"
        )
        assert (
            optimism_mapping["0x26Ea2dC7ce1b41d0AD0E0521535655d7a94b684c"]
            == "Fixed Price Token"
        )
        assert (
            optimism_mapping["0x93111f6C267068A5d7356114D61d0f09bFD53a54"]
            == "Fixed Price Token USDC"
        )
        assert (
            optimism_mapping["0x02C26437B292D86c5F4F21bbCcE0771948274f84"]
            == "NvmSubscription Token USDC"
        )

    def test_polygon_mapping(self) -> None:
        """Test polygon chain factory mappings."""
        polygon_mapping = CHAIN_TO_MECH_FACTORY_TO_MECH_TYPE["polygon"]
        assert len(polygon_mapping) == 4
        assert (
            polygon_mapping["0x87f89F94033305791B6269AE2F9cF4e09983E56e"]
            == "Fixed Price Native"
        )
        assert (
            polygon_mapping["0xa0DA53447C0f6C4987964d8463da7e6628B30f82"]
            == "Fixed Price Token"
        )
        assert (
            polygon_mapping["0x85899f9d8C058A5BBBaF344ea0f0b63c0CcBe851"]
            == "Fixed Price Token USDC"
        )
        assert (
            polygon_mapping["0x43fB32f25dce34EB76c78C7A42C8F40F84BCD237"]
            == "NvmSubscription Token USDC"
        )


class TestResultsLimit:
    """Tests for RESULTS_LIMIT constant."""

    def test_results_limit_value(self) -> None:
        """Test RESULTS_LIMIT is set to 20."""
        assert RESULTS_LIMIT == 20


class TestQueryMmMechsInfo:
    """Tests for query_mm_mechs_info function."""

    @patch("mech_client.infrastructure.subgraph.queries.SubgraphClient")
    @patch("mech_client.infrastructure.subgraph.queries.get_mech_config")
    def test_query_mechs_success_gnosis(
        self, mock_get_config: MagicMock, mock_subgraph_client: MagicMock
    ) -> None:
        """Test successful query for gnosis chain."""
        # Setup mock config
        mock_config = MagicMock()
        mock_config.subgraph_url = "https://subgraph.example.com/gnosis"
        mock_config.subgraph_dialect = "graph"
        mock_get_config.return_value = mock_config

        # Setup mock subgraph response
        mock_client = MagicMock()
        mock_client.query_mechs.return_value = {
            "meches": [
                {
                    "id": "0xmech1",
                    "mechFactory": "0x8b299c20F87e3fcBfF0e1B86dC0acC06AB6993EF",
                    "totalDeliveriesTransactions": "5",
                },
                {
                    "id": "0xmech2",
                    "mechFactory": "0x31ffDC795FDF36696B8eDF7583A3D115995a45FA",
                    "totalDeliveriesTransactions": "10",
                },
            ]
        }
        mock_subgraph_client.return_value = mock_client

        # Query mechs
        result = query_mm_mechs_info("gnosis")

        # Verify
        assert result is not None
        assert len(result) == 2
        assert result[0]["mech_type"] == "Fixed Price Native"
        assert result[1]["mech_type"] == "Fixed Price Token"
        mock_get_config.assert_called_once_with("gnosis")
        mock_subgraph_client.assert_called_once_with(
            "https://subgraph.example.com/gnosis", dialect="graph"
        )

    @patch("mech_client.infrastructure.subgraph.queries.SubgraphClient")
    @patch("mech_client.infrastructure.subgraph.queries.get_mech_config")
    def test_query_mechs_filters_zero_deliveries(
        self, mock_get_config: MagicMock, mock_subgraph_client: MagicMock
    ) -> None:
        """Test query filters out mechs with zero deliveries."""
        # Setup mock config
        mock_config = MagicMock()
        mock_config.subgraph_url = "https://subgraph.example.com/base"
        mock_get_config.return_value = mock_config

        # Setup mock subgraph response with mixed delivery counts
        mock_client = MagicMock()
        mock_client.query_mechs.return_value = {
            "meches": [
                {
                    "id": "0xmech1",
                    "mechFactory": "0x2E008211f34b25A7d7c102403c6C2C3B665a1abe",
                    "totalDeliveriesTransactions": "5",
                },
                {
                    "id": "0xmech2",
                    "mechFactory": "0x97371B1C0cDA1D04dFc43DFb50a04645b7Bc9BEe",
                    "totalDeliveriesTransactions": "0",
                },
                {
                    "id": "0xmech3",
                    "mechFactory": "0x847bBE8b474e0820215f818858e23F5f5591855A",
                    "totalDeliveriesTransactions": "1",
                },
            ]
        }
        mock_subgraph_client.return_value = mock_client

        # Query mechs
        result = query_mm_mechs_info("base")

        # Verify only mechs with deliveries > 0 are returned
        assert result is not None
        assert len(result) == 2
        assert result[0]["id"] == "0xmech1"
        assert result[1]["id"] == "0xmech3"

    @patch("mech_client.infrastructure.subgraph.queries.SubgraphClient")
    @patch("mech_client.infrastructure.subgraph.queries.get_mech_config")
    def test_query_mechs_case_insensitive_factory(
        self, mock_get_config: MagicMock, mock_subgraph_client: MagicMock
    ) -> None:
        """Test query handles factory addresses case-insensitively."""
        # Setup mock config
        mock_config = MagicMock()
        mock_config.subgraph_url = "https://subgraph.example.com/gnosis"
        mock_get_config.return_value = mock_config

        # Setup mock subgraph response with lowercase factory
        mock_client = MagicMock()
        mock_client.query_mechs.return_value = {
            "meches": [
                {
                    "id": "0xmech1",
                    "mechFactory": "0x8b299c20f87e3fcbff0e1b86dc0acc06ab6993ef",  # lowercase
                    "totalDeliveriesTransactions": "5",
                }
            ]
        }
        mock_subgraph_client.return_value = mock_client

        # Query mechs
        result = query_mm_mechs_info("gnosis")

        # Verify mech type mapped correctly despite lowercase
        assert result is not None
        assert len(result) == 1
        assert result[0]["mech_type"] == "Fixed Price Native"

    @patch("mech_client.infrastructure.subgraph.queries.SubgraphClient")
    @patch("mech_client.infrastructure.subgraph.queries.get_mech_config")
    def test_query_mechs_unknown_factory(
        self, mock_get_config: MagicMock, mock_subgraph_client: MagicMock
    ) -> None:
        """Test query handles unknown factory addresses."""
        # Setup mock config
        mock_config = MagicMock()
        mock_config.subgraph_url = "https://subgraph.example.com/gnosis"
        mock_get_config.return_value = mock_config

        # Setup mock subgraph response with unknown factory
        mock_client = MagicMock()
        mock_client.query_mechs.return_value = {
            "meches": [
                {
                    "id": "0xmech1",
                    "mechFactory": "0x0000000000000000000000000000000000000000",
                    "totalDeliveriesTransactions": "5",
                }
            ]
        }
        mock_subgraph_client.return_value = mock_client

        # Query mechs
        result = query_mm_mechs_info("gnosis")

        # Verify unknown factory gets "Unknown" mech type
        assert result is not None
        assert len(result) == 1
        assert result[0]["mech_type"] == "Unknown"

    @patch("mech_client.infrastructure.subgraph.queries.SubgraphClient")
    @patch("mech_client.infrastructure.subgraph.queries.get_mech_config")
    def test_query_mechs_respects_results_limit(
        self, mock_get_config: MagicMock, mock_subgraph_client: MagicMock
    ) -> None:
        """Test query respects RESULTS_LIMIT."""
        # Setup mock config
        mock_config = MagicMock()
        mock_config.subgraph_url = "https://subgraph.example.com/gnosis"
        mock_get_config.return_value = mock_config

        # Setup mock subgraph response with more than RESULTS_LIMIT mechs
        mechs = []
        for i in range(30):  # More than RESULTS_LIMIT (20)
            mechs.append(
                {
                    "id": f"0xmech{i}",
                    "mechFactory": "0x8b299c20F87e3fcBfF0e1B86dC0acC06AB6993EF",
                    "totalDeliveriesTransactions": "1",
                }
            )

        mock_client = MagicMock()
        mock_client.query_mechs.return_value = {"meches": mechs}
        mock_subgraph_client.return_value = mock_client

        # Query mechs
        result = query_mm_mechs_info("gnosis")

        # Verify only RESULTS_LIMIT returned
        assert result is not None
        assert len(result) == RESULTS_LIMIT

    @patch("mech_client.infrastructure.subgraph.queries.get_mech_config")
    def test_query_mechs_no_subgraph_url(
        self, mock_get_config: MagicMock
    ) -> None:
        """Test query raises SubgraphError when subgraph URL not set."""
        # Setup mock config with no subgraph URL
        mock_config = MagicMock()
        mock_config.subgraph_url = None
        mock_get_config.return_value = mock_config

        # Query mechs should raise exception
        with pytest.raises(SubgraphError) as exc_info:
            query_mm_mechs_info("gnosis")

        assert "Subgraph URL not set for chain config: gnosis" in str(exc_info.value)

    @patch("mech_client.infrastructure.subgraph.queries.SubgraphClient")
    @patch("mech_client.infrastructure.subgraph.queries.get_mech_config")
    def test_query_mechs_empty_results(
        self, mock_get_config: MagicMock, mock_subgraph_client: MagicMock
    ) -> None:
        """Test query handles empty results."""
        # Setup mock config
        mock_config = MagicMock()
        mock_config.subgraph_url = "https://subgraph.example.com/gnosis"
        mock_get_config.return_value = mock_config

        # Setup mock subgraph response with empty results
        mock_client = MagicMock()
        mock_client.query_mechs.return_value = {"meches": []}
        mock_subgraph_client.return_value = mock_client

        # Query mechs
        result = query_mm_mechs_info("gnosis")

        # Verify empty list returned
        assert result is not None
        assert len(result) == 0

    @patch("mech_client.infrastructure.subgraph.queries.SubgraphClient")
    @patch("mech_client.infrastructure.subgraph.queries.get_mech_config")
    def test_query_mechs_all_chains(
        self, mock_get_config: MagicMock, mock_subgraph_client: MagicMock
    ) -> None:
        """Test query works for all supported chains."""
        chains = ["gnosis", "base", "optimism", "polygon"]

        for chain in chains:
            # Setup mock config
            mock_config = MagicMock()
            mock_config.subgraph_url = f"https://subgraph.example.com/{chain}"
            mock_get_config.return_value = mock_config

            # Get first factory for this chain
            first_factory = list(CHAIN_TO_MECH_FACTORY_TO_MECH_TYPE[chain].keys())[0]

            # Setup mock subgraph response
            mock_client = MagicMock()
            mock_client.query_mechs.return_value = {
                "meches": [
                    {
                        "id": "0xmech1",
                        "mechFactory": first_factory,
                        "totalDeliveriesTransactions": "5",
                    }
                ]
            }
            mock_subgraph_client.return_value = mock_client

            # Query mechs
            result = query_mm_mechs_info(chain)

            # Verify
            assert result is not None
            assert len(result) == 1
            assert result[0]["mech_type"] != "Unknown"

    @patch("mech_client.infrastructure.subgraph.queries.SubgraphClient")
    @patch("mech_client.infrastructure.subgraph.queries.get_mech_config")
    def test_query_mechs_preserves_original_fields(
        self, mock_get_config: MagicMock, mock_subgraph_client: MagicMock
    ) -> None:
        """Test query preserves all original fields from subgraph response."""
        # Setup mock config
        mock_config = MagicMock()
        mock_config.subgraph_url = "https://subgraph.example.com/gnosis"
        mock_get_config.return_value = mock_config

        # Setup mock subgraph response with realistic GraphQL structure
        mock_client = MagicMock()
        mock_client.query_mechs.return_value = {
            "meches": [
                {
                    "id": "2182",
                    "mechFactory": "0x8b299c20F87e3fcBfF0e1B86dC0acC06AB6993EF",
                    "totalDeliveriesTransactions": "5",
                    "address": "0xabcdef",
                    "service": {
                        "id": "2182",
                        "totalDeliveries": "5",
                        "metadata": [
                            {"metadata": "0x1234567890abcdef"}
                        ],  # Realistic structure
                    },
                }
            ]
        }
        mock_subgraph_client.return_value = mock_client

        # Query mechs
        result = query_mm_mechs_info("gnosis")

        # Verify all fields preserved plus mech_type added
        assert result is not None
        assert len(result) == 1
        assert result[0]["id"] == "2182"
        assert result[0]["mechFactory"] == "0x8b299c20F87e3fcBfF0e1B86dC0acC06AB6993EF"
        assert result[0]["totalDeliveriesTransactions"] == "5"
        assert result[0]["address"] == "0xabcdef"
        assert result[0]["service"]["id"] == "2182"
        assert result[0]["service"]["totalDeliveries"] == "5"
        assert result[0]["service"]["metadata"][0]["metadata"] == "0x1234567890abcdef"
        assert result[0]["mech_type"] == "Fixed Price Native"


class TestQueryMechsChainWithoutSubgraph:
    """Tests for a chain with a deployed marketplace but a blank subgraph URL."""

    def test_blank_subgraph_url_raises_subgraph_url_not_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test mech list fails fast when a marketplace chain has no subgraph URL."""
        monkeypatch.delenv("MECHX_SUBGRAPH_URL", raising=False)
        blank = replace(get_mech_config("robinhood"), subgraph_url="")
        assert int(blank.mech_marketplace_contract, 16) != 0

        with patch(
            "mech_client.infrastructure.subgraph.queries.get_mech_config",
            return_value=blank,
        ), pytest.raises(
            SubgraphError, match="Subgraph URL not set for chain config: robinhood"
        ):
            query_mm_mechs_info("robinhood")


class TestQueryMechsRobinhoodSquid:
    """Tests for mech list on Robinhood, whose indexer is an SQD squid."""

    @patch("mech_client.infrastructure.subgraph.queries.SubgraphClient")
    def test_robinhood_queries_the_squid_and_maps_its_factories(
        self, mock_client_class: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test robinhood uses the squid dialect and names its USDC-type mech."""
        monkeypatch.delenv("MECHX_SUBGRAPH_URL", raising=False)
        mock_client_class.return_value.query_mechs.return_value = {
            "meches": [
                {
                    "address": "0x65ea02825e7c21e47d768f3fc6c1e7597e5830af",
                    "mechFactory": "0x7fd1f4b764fa41d19fe3f63c85d12bf64d2bbf68",
                    "totalDeliveriesTransactions": "3",
                    "service": {"id": "1", "totalDeliveries": "2", "metadata": []},
                },
                {
                    "address": "0x00000000000000000000000000000000000000aa",
                    "mechFactory": "0x04b0007b2afb398015b76e5f22993a1fddf83644",
                    "totalDeliveriesTransactions": "1",
                    "service": {"id": "2", "totalDeliveries": "1", "metadata": []},
                },
            ]
        }

        result = query_mm_mechs_info("robinhood")

        assert mock_client_class.call_args[0] == (
            "https://subgraph.autonolas.tech/squid/marketplace-robinhood/graphql",
        )
        assert mock_client_class.call_args[1] == {"dialect": "squid"}
        assert result is not None
        assert [m["mech_type"] for m in result] == [
            "Fixed Price Token USDC",
            "Fixed Price Native",
        ]


class TestUnmappedMechFactory:
    """Tests for a mech whose factory isn't in the chain's mapping."""

    @patch("mech_client.infrastructure.subgraph.queries.logger")
    @patch("mech_client.infrastructure.subgraph.queries.SubgraphClient")
    def test_unmapped_factory_is_listed_as_unknown_and_logged(
        self,
        mock_client_class: MagicMock,
        mock_logger: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test an unmapped factory shows as Unknown and names itself in a warning."""
        monkeypatch.delenv("MECHX_SUBGRAPH_URL", raising=False)
        unmapped = "0x00000000000000000000000000000000000000ff"
        mock_client_class.return_value.query_mechs.return_value = {
            "meches": [
                {
                    "address": "0x00000000000000000000000000000000000000bb",
                    "mechFactory": unmapped,
                    "totalDeliveriesTransactions": "1",
                    "service": {"id": "9", "totalDeliveries": "1", "metadata": []},
                }
            ]
        }

        result = query_mm_mechs_info("robinhood")

        assert result is not None
        assert result[0]["mech_type"] == "Unknown"
        mock_logger.warning.assert_called_once()
        assert unmapped in mock_logger.warning.call_args[0]
        assert "robinhood" in mock_logger.warning.call_args[0]

