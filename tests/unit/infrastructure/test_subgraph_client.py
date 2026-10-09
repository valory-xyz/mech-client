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

"""Tests for subgraph client."""

from unittest.mock import MagicMock, patch

import pytest

from mech_client.infrastructure.subgraph.client import SubgraphClient


class TestSubgraphClientInitialization:
    """Tests for SubgraphClient initialization."""

    def test_initialization_default_timeout(self) -> None:
        """Test client initialization with default timeout."""
        url = "https://subgraph.example.com/graphql"
        client = SubgraphClient(subgraph_url=url, dialect="graph")

        assert client.subgraph_url == url
        assert client.timeout == 600.0
        assert client._client is None  # Lazy loading

    def test_initialization_custom_timeout(self) -> None:
        """Test client initialization with custom timeout."""
        url = "https://subgraph.example.com/graphql"
        custom_timeout = 120.0
        client = SubgraphClient(subgraph_url=url, dialect="graph", timeout=custom_timeout)

        assert client.subgraph_url == url
        assert client.timeout == custom_timeout


class TestSubgraphClientProperty:
    """Tests for SubgraphClient lazy-loaded client property."""

    @patch("mech_client.infrastructure.subgraph.client.Client")
    @patch("mech_client.infrastructure.subgraph.client.AIOHTTPTransport")
    def test_client_property_lazy_loading(
        self, mock_transport: MagicMock, mock_client_class: MagicMock
    ) -> None:
        """Test that client is lazy-loaded on first access."""
        url = "https://subgraph.example.com/graphql"
        timeout = 300.0

        mock_transport_instance = MagicMock()
        mock_transport.return_value = mock_transport_instance

        mock_client_instance = MagicMock()
        mock_client_class.return_value = mock_client_instance

        client = SubgraphClient(subgraph_url=url, dialect="graph", timeout=timeout)

        # Initially, _client should be None
        assert client._client is None

        # Access client property
        result = client.client

        # Verify transport created with correct URL
        mock_transport.assert_called_once_with(url=url)

        # Verify Client created with correct parameters
        mock_client_class.assert_called_once_with(
            transport=mock_transport_instance,
            execute_timeout=timeout,
        )

        # Verify correct client returned
        assert result == mock_client_instance

    @patch("mech_client.infrastructure.subgraph.client.Client")
    @patch("mech_client.infrastructure.subgraph.client.AIOHTTPTransport")
    def test_client_property_cached(
        self, mock_transport: MagicMock, mock_client_class: MagicMock
    ) -> None:
        """Test that client property returns cached instance on subsequent calls."""
        url = "https://subgraph.example.com/graphql"

        mock_client_instance = MagicMock()
        mock_client_class.return_value = mock_client_instance

        client = SubgraphClient(subgraph_url=url, dialect="graph")

        # Access client property twice
        result1 = client.client
        result2 = client.client

        # Client should only be created once
        assert mock_client_class.call_count == 1

        # Both results should be the same instance
        assert result1 is result2
        assert result1 == mock_client_instance


class TestSubgraphClientExecute:
    """Tests for SubgraphClient execute method."""

    @patch("mech_client.infrastructure.subgraph.client.gql")
    def test_execute_success(self, mock_gql: MagicMock) -> None:
        """Test successful query execution."""
        url = "https://subgraph.example.com/graphql"
        query_string = "query { mechs { id } }"
        expected_result = {"mechs": [{"id": "1"}, {"id": "2"}]}

        # Mock gql document
        mock_document = MagicMock()
        mock_gql.return_value = mock_document

        # Create client with mocked underlying client
        client = SubgraphClient(subgraph_url=url, dialect="graph")
        mock_client = MagicMock()
        mock_client.execute.return_value = expected_result
        client._client = mock_client

        result = client.execute(query_string)

        # Verify gql was called with query string
        mock_gql.assert_called_once_with(request_string=query_string)

        # Verify execute was called with the gql document positionally
        mock_client.execute.assert_called_once_with(mock_document)

        # Verify result
        assert result == expected_result

    @patch("mech_client.infrastructure.subgraph.client.gql")
    def test_execute_query_error(self, mock_gql: MagicMock) -> None:
        """Test execute propagates query execution errors."""
        url = "https://subgraph.example.com/graphql"
        query_string = "invalid query"

        # Mock gql document
        mock_document = MagicMock()
        mock_gql.return_value = mock_document

        # Create client with mocked underlying client
        client = SubgraphClient(subgraph_url=url, dialect="graph")
        mock_client = MagicMock()
        mock_client.execute.side_effect = Exception("GraphQL query failed")
        client._client = mock_client

        with pytest.raises(Exception, match="GraphQL query failed"):
            client.execute(query_string)


class TestSubgraphClientQueryMechs:
    """Tests for SubgraphClient query_mechs method."""

    @patch("mech_client.infrastructure.subgraph.client.gql")
    def test_query_mechs_default_parameters(self, mock_gql: MagicMock) -> None:
        """Test query_mechs with default ordering parameters."""
        url = "https://subgraph.example.com/graphql"
        expected_result = {
            "meches": [
                {
                    "address": "0x1234",
                    "service": {"id": "1", "totalDeliveries": "10"},
                }
            ]
        }

        # Mock gql document
        mock_document = MagicMock()
        mock_gql.return_value = mock_document

        # Create client with mocked underlying client
        client = SubgraphClient(subgraph_url=url, dialect="graph")
        mock_client = MagicMock()
        mock_client.execute.return_value = expected_result
        client._client = mock_client

        result = client.query_mechs()

        # Verify query was constructed with default parameters
        call_args = mock_gql.call_args[1]
        query_str = call_args["request_string"]
        assert "orderBy: totalDeliveriesTransactions" in query_str
        assert "orderDirection: desc" in query_str

        # Verify result
        assert result == expected_result

    @patch("mech_client.infrastructure.subgraph.client.gql")
    def test_query_mechs_custom_parameters(self, mock_gql: MagicMock) -> None:
        """Test query_mechs with custom ordering parameters."""
        url = "https://subgraph.example.com/graphql"
        expected_result = {"meches": []}

        # Mock gql document
        mock_document = MagicMock()
        mock_gql.return_value = mock_document

        # Create client with mocked underlying client
        client = SubgraphClient(subgraph_url=url, dialect="graph")
        mock_client = MagicMock()
        mock_client.execute.return_value = expected_result
        client._client = mock_client

        result = client.query_mechs(
            order_by="service__id", order_direction="asc"
        )

        # Verify query was constructed with custom parameters
        call_args = mock_gql.call_args[1]
        query_str = call_args["request_string"]
        assert "orderBy: service__id" in query_str
        assert "orderDirection: asc" in query_str

        # Verify result
        assert result == expected_result

    @patch("mech_client.infrastructure.subgraph.client.gql")
    def test_query_mechs_execution_error(self, mock_gql: MagicMock) -> None:
        """Test query_mechs propagates execution errors."""
        url = "https://subgraph.example.com/graphql"

        # Mock gql document
        mock_document = MagicMock()
        mock_gql.return_value = mock_document

        # Create client with mocked underlying client
        client = SubgraphClient(subgraph_url=url, dialect="graph")
        mock_client = MagicMock()
        mock_client.execute.side_effect = Exception("Subgraph unreachable")
        client._client = mock_client

        with pytest.raises(Exception, match="Subgraph unreachable"):
            client.query_mechs()


class TestSubgraphClientSquidDialect:
    """Tests for query_mechs against an SQD squid (OpenReader)."""

    @pytest.mark.parametrize(
        ("order_direction", "order_clause"),
        [
            pytest.param("desc", "orderBy: [totalDeliveriesTransactions_DESC]", id="desc"),
            pytest.param("asc", "orderBy: [totalDeliveriesTransactions_ASC]", id="asc"),
        ],
    )
    @patch("mech_client.infrastructure.subgraph.client.gql")
    def test_squid_uses_openreader_sort_syntax(
        self, mock_gql: MagicMock, order_direction: str, order_clause: str
    ) -> None:
        """Test the squid dialect sends OpenReader's orderBy list, no orderDirection."""
        client = SubgraphClient(
            subgraph_url="https://squid.example.com/graphql", dialect="squid"
        )
        client._client = MagicMock()

        client.query_mechs(order_direction=order_direction)

        query_str = mock_gql.call_args[1]["request_string"]
        assert order_clause in query_str
        assert "orderDirection" not in query_str

    def test_unknown_dialect_is_rejected_when_built(self) -> None:
        """Test an unknown dialect fails at construction, not at the first query."""
        with pytest.raises(
            ValueError, match="Unknown subgraph_dialect 'hasura' for SubgraphClient"
        ):
            SubgraphClient(
                subgraph_url="https://example.com/graphql",
                dialect="hasura",  # type: ignore[arg-type]
            )

    def test_dialect_is_required(self) -> None:
        """Test a client can't be built without naming its dialect."""
        with pytest.raises(TypeError, match="dialect"):
            SubgraphClient(subgraph_url="https://example.com/graphql")  # type: ignore[call-arg]


class TestSubgraphClientSortArguments:
    """Tests for the sort arguments query_mechs interpolates into its query."""

    @pytest.mark.parametrize(
        ("order_by", "order_direction", "message"),
        [
            pytest.param("x) { id } #", "desc", "order_by must be a GraphQL field name", id="order-by-injection"),
            pytest.param("", "desc", "order_by must be a GraphQL field name", id="order-by-empty"),
            pytest.param("totalDeliveriesTransactions", "DESC", "order_direction must be one of", id="direction-uppercase"),
            pytest.param("totalDeliveriesTransactions", "desc, first: 1", "order_direction must be one of", id="direction-injection"),
        ],
    )
    def test_invalid_sort_arguments_are_rejected_before_querying(
        self, order_by: str, order_direction: str, message: str
    ) -> None:
        """Test sort arguments outside the allow-list never reach the query string."""
        client = SubgraphClient(subgraph_url="https://example.com/graphql", dialect="graph")
        client._client = MagicMock()

        with pytest.raises(ValueError, match=message):
            client.query_mechs(order_by=order_by, order_direction=order_direction)
        client._client.execute.assert_not_called()



def _client_with(result: dict, dialect: str = "graph") -> SubgraphClient:
    """Build a client whose underlying gql client answers with ``result``."""
    client = SubgraphClient(
        subgraph_url="https://subgraph.example.com", dialect=dialect
    )
    client._client = MagicMock()  # pylint: disable=protected-access
    client._client.execute.return_value = result  # pylint: disable=protected-access
    return client


def _query_sent(mock_gql: MagicMock) -> str:
    """Return the query string the client handed to gql."""
    return mock_gql.call_args[1]["request_string"]


MECH_ADDRESS = "0xC05e7412439bD7e91730a6880E18d5D5873F632C"


class TestQueryMech:
    """One mech's record and creation row, filtered in the indexer's own dialect."""

    @patch("mech_client.infrastructure.subgraph.client.gql")
    def test_graph_filters_by_address_and_mech(self, mock_gql: MagicMock) -> None:
        """The Graph takes ``address:`` and ``mech:`` filters, lowercased."""
        result = {"meches": [{"id": "1"}], "createMeches": [{"blockTimestamp": "1"}]}
        assert _client_with(result).query_mech(MECH_ADDRESS) == result
        query = _query_sent(mock_gql)
        assert f'meches(where: {{address: "{MECH_ADDRESS.lower()}"}})' in query
        assert f'createMeches(where: {{mech: "{MECH_ADDRESS.lower()}"}})' in query
        for field in (
            "receivedRequests",
            "selfDeliveredFromReceived",
            "deliveredByOthersFromReceived",
            "paymentType",
            "blockTimestamp",
        ):
            assert field in query

    @patch("mech_client.infrastructure.subgraph.client.gql")
    def test_squid_filters_with_eq(self, mock_gql: MagicMock) -> None:
        """OpenReader takes ``address_eq:`` and ``mech_eq:`` filters."""
        _client_with({"meches": [], "createMeches": []}, "squid").query_mech(
            MECH_ADDRESS
        )
        query = _query_sent(mock_gql)
        assert f'meches(where: {{address_eq: "{MECH_ADDRESS.lower()}"}})' in query
        assert f'createMeches(where: {{mech_eq: "{MECH_ADDRESS.lower()}"}})' in query

    @pytest.mark.parametrize(
        "address",
        [
            "",
            "0x",
            "c05e7412439bd7e91730a6880e18d5d5873f632c",
            "0x" + "g" * 40,
            "0x" + "a" * 39,
            '0x" + "a" * 40 + "\\"}) { id }',
        ],
        ids=["empty", "prefix_only", "no_prefix", "non_hex", "short", "injection"],
    )
    def test_anything_but_an_address_is_rejected_before_querying(
        self, address: str
    ) -> None:
        """The address is interpolated into the query, so only a real one passes."""
        client = _client_with({})
        with pytest.raises(ValueError, match="0x hex address"):
            client.query_mech(address)
        client._client.execute.assert_not_called()  # pylint: disable=protected-access


class TestQueryServiceAgentId:
    """A service's ERC-8004 agent id, from either registry dialect."""

    @patch("mech_client.infrastructure.subgraph.client.gql")
    def test_graph_looks_the_service_up_by_id(self, mock_gql: MagicMock) -> None:
        """The Graph exposes ``service(id:)``."""
        result = {"service": {"id": "195", "erc8004Agent": {"id": "516"}}}
        assert _client_with(result).query_service_agent_id(195) == result
        query = _query_sent(mock_gql)
        assert 'service(id: "195")' in query
        assert "erc8004Agent" in query

    @patch("mech_client.infrastructure.subgraph.client.gql")
    def test_squid_looks_the_service_up_with_service_by_id(
        self, mock_gql: MagicMock
    ) -> None:
        """OpenReader exposes ``serviceById(id:)``."""
        _client_with({"serviceById": None}, "squid").query_service_agent_id(1)
        assert 'serviceById(id: "1")' in _query_sent(mock_gql)

    @pytest.mark.parametrize(
        "service_id",
        [-1, True, "1", 1.5, '1") { id } x("'],
        ids=["negative", "bool", "string", "float", "injection"],
    )
    def test_anything_but_a_whole_number_is_rejected_before_querying(
        self, service_id: object
    ) -> None:
        """The id is interpolated into the query, so only digits pass."""
        client = _client_with({})
        with pytest.raises(ValueError, match="non-negative integer"):
            client.query_service_agent_id(service_id)  # type: ignore[arg-type]
        client._client.execute.assert_not_called()  # pylint: disable=protected-access
