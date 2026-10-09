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

import re
from typing import Any, Dict, List

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from mech_client.infrastructure.config.chain_config import (
    SubgraphDialect,
    validate_subgraph_dialect,
)

DEFAULT_TIMEOUT = 600.0
ORDER_DIRECTIONS = ("asc", "desc")
_GRAPHQL_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_ADDRESS = re.compile(r"0x[0-9a-fA-F]{40}")


class SubgraphClient:
    """Client for querying mech marketplace subgraph via GraphQL.

    Provides methods for executing GraphQL queries against the marketplace
    subgraph to retrieve mech metadata, delivery counts, and other on-chain data.
    """

    def __init__(
        self,
        subgraph_url: str,
        dialect: SubgraphDialect,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        """
        Initialize subgraph client.

        :param subgraph_url: GraphQL endpoint URL for the subgraph
        :param dialect: "graph" for The Graph, "squid" for an SQD squid (OpenReader)
        :param timeout: Request timeout in seconds (default: 600)
        """
        validate_subgraph_dialect(dialect, "SubgraphClient")
        self.subgraph_url = subgraph_url
        self.timeout = timeout
        self.dialect = dialect
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

        Any underlying error from the gql client (transport / parse /
        server) propagates to the caller unchanged.

        :param query: GraphQL query string
        :return: Query response data
        """
        return self.client.execute(gql(request_string=query))

    def query_mechs(
        self,
        order_by: str = "totalDeliveriesTransactions",
        order_direction: str = "desc",
    ) -> Dict[str, Any]:
        """
        Query mechs ordered by specified field.

        :param order_by: Field to order by (default: totalDeliveriesTransactions)
        :param order_direction: Sort direction "asc" or "desc" (default: desc)
        :return: Query response with mech data
        :raises ValueError: If order_by is not a field name or order_direction is not asc/desc
        """
        if not _GRAPHQL_NAME.fullmatch(order_by):
            raise ValueError(f"order_by must be a GraphQL field name, got {order_by!r}")
        if order_direction not in ORDER_DIRECTIONS:
            raise ValueError(
                f"order_direction must be one of {ORDER_DIRECTIONS}, got {order_direction!r}"
            )
        if self.dialect == "squid":
            order = f"orderBy: [{order_by}_{order_direction.upper()}]"
        else:
            order = f"orderBy: {order_by}, orderDirection: {order_direction}"
        query = f"""
        query MechsOrderedByServiceDeliveries {{
          meches({order}) {{
            id
            address
            mechFactory
            totalDeliveriesTransactions
            receivedRequests
            selfDeliveredFromReceived
            deliveredByOthersFromReceived
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

    def query_mech(self, address: str) -> Dict[str, Any]:
        """
        Query one mech by address, with its delivery record and creation row.

        :param address: The mech contract address
        :return: Query response with ``meches`` and ``createMeches`` lists
        :raises ValueError: If address is not a 0x-prefixed 40-hex-digit address
        """
        if not _ADDRESS.fullmatch(address):
            raise ValueError(f"address must be a 0x hex address, got {address!r}")
        address = address.lower()
        if self.dialect == "squid":
            by_address = f'where: {{address_eq: "{address}"}}'
            by_mech = f'where: {{mech_eq: "{address}"}}'
        else:
            by_address = f'where: {{address: "{address}"}}'
            by_mech = f'where: {{mech: "{address}"}}'
        query = f"""
        query MechRecord {{
          meches({by_address}) {{
            id
            address
            receivedRequests
            selfDeliveredFromReceived
            deliveredByOthersFromReceived
            paymentType
            service {{
              id
              metadata {{
                metadata
              }}
            }}
          }}
          createMeches({by_mech}) {{
            blockTimestamp
          }}
        }}
        """
        return self.execute(query)

    def query_mech_creations(self, addresses: List[str]) -> Dict[str, Any]:
        """
        Query the creation rows of several mechs in one request.

        :param addresses: The mech contract addresses
        :return: Query response with a ``createMeches`` list
        :raises ValueError: If any address is not a 0x-prefixed 40-hex-digit address
        """
        for address in addresses:
            if not _ADDRESS.fullmatch(address):
                raise ValueError(f"address must be a 0x hex address, got {address!r}")
        listed = ", ".join(f'"{address.lower()}"' for address in addresses)
        query = f"""
        query MechCreations {{
          createMeches(where: {{mech_in: [{listed}]}}) {{
            mech
            blockTimestamp
          }}
        }}
        """
        return self.execute(query)

    def query_service_agent_id(self, service_id: int) -> Dict[str, Any]:
        """
        Query a service's ERC-8004 agent id from a service registry indexer.

        :param service_id: The Olas service id
        :return: Query response with ``service`` (graph) or ``serviceById`` (squid)
        :raises ValueError: If service_id is not a non-negative integer
        """
        if (
            isinstance(service_id, bool)
            or not isinstance(service_id, int)
            or service_id < 0
        ):
            raise ValueError(
                f"service_id must be a non-negative integer, got {service_id!r}"
            )
        lookup = "serviceById" if self.dialect == "squid" else "service"
        query = f"""
        query ServiceAgentId {{
          {lookup}(id: "{service_id}") {{
            id
            erc8004Agent {{
              id
            }}
          }}
        }}
        """
        return self.execute(query)
