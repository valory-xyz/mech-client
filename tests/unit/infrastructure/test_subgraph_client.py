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

"""Tests for subgraph client."""

from unittest.mock import MagicMock, patch

import pytest

from mech_client.infrastructure.subgraph.client import SubgraphClient


class TestSubgraphClientInitialization:
    """Tests for SubgraphClient initialization."""

    def test_initialization_default_timeout(self) -> None:
        """Test client initialization with default timeout."""
        url = "https://subgraph.example.com/graphql"
        client = SubgraphClient(subgraph_url=url)

        assert client.subgraph_url == url
        assert client.timeout == 600.0
        assert client._client is None  # Lazy loading

    def test_initialization_custom_timeout(self) -> None:
        """Test client initialization with custom timeout."""
        url = "https://subgraph.example.com/graphql"
        custom_timeout = 120.0
        client = SubgraphClient(subgraph_url=url, timeout=custom_timeout)

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

        client = SubgraphClient(subgraph_url=url, timeout=timeout)

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

        client = SubgraphClient(subgraph_url=url)

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
        client = SubgraphClient(subgraph_url=url)
        mock_client = MagicMock()
        mock_client.execute.return_value = expected_result
        client._client = mock_client

        result = client.execute(query_string)

        # Verify gql was called with query string
        mock_gql.assert_called_once_with(request_string=query_string)

        # Verify execute was called with gql document
        mock_client.execute.assert_called_once_with(document=mock_document)

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
        client = SubgraphClient(subgraph_url=url)
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
        client = SubgraphClient(subgraph_url=url)
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
        client = SubgraphClient(subgraph_url=url)
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
        client = SubgraphClient(subgraph_url=url)
        mock_client = MagicMock()
        mock_client.execute.side_effect = Exception("Subgraph unreachable")
        client._client = mock_client

        with pytest.raises(Exception, match="Subgraph unreachable"):
            client.query_mechs()
