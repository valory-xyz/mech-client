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

"""GraphQL subgraph client."""

from typing import Any, Dict

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport


DEFAULT_TIMEOUT = 600.0


class SubgraphClient:
    """Client for querying mech marketplace subgraph via GraphQL.

    Provides methods for executing GraphQL queries against the marketplace
    subgraph to retrieve mech metadata, delivery counts, and other on-chain data.
    """

    def __init__(self, subgraph_url: str, timeout: float = DEFAULT_TIMEOUT):
        """
        Initialize subgraph client.

        :param subgraph_url: GraphQL endpoint URL for the subgraph
        :param timeout: Request timeout in seconds (default: 600)
        """
        self.subgraph_url = subgraph_url
        self.timeout = timeout
        self._client: Client = None  # type: ignore

    @property
    def client(self) -> Client:
        """Lazy-loaded GraphQL client instance.

        :return: GQL client instance
        """
        if self._client is None:
            transport = AIOHTTPTransport(url=self.subgraph_url)
            self._client = Client(
                transport=transport,
                execute_timeout=self.timeout,
            )
        return self._client

    def execute(self, query: str) -> Dict[str, Any]:
        """
        Execute a GraphQL query.

        :param query: GraphQL query string
        :return: Query response data
        :raises Exception: If query execution fails
        """
        return self.client.execute(document=gql(request_string=query))

    def query_mechs(
        self,
        order_by: str = "service__totalDeliveries",
        order_direction: str = "desc",
    ) -> Dict[str, Any]:
        """
        Query mechs ordered by specified field.

        :param order_by: Field to order by (default: service__totalDeliveries)
        :param order_direction: Sort direction "asc" or "desc" (default: desc)
        :return: Query response with mech data
        """
        query = f"""
        query MechsOrderedByServiceDeliveries {{
          meches(orderBy: {order_by}, orderDirection: {order_direction}) {{
            address
            mechFactory
            service {{
              id
              totalDeliveries
              metadata {{
                metadata
              }}
            }}
          }}
        }}
        """
        return self.execute(query)
