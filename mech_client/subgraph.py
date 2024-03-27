# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2023 Valory AG
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

"""Subgraph client for mech."""

import asyncio
from string import Template
from typing import Optional

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport


MECH_SUBGRAPH_URL = "https://api.studio.thegraph.com/query/57238/mech/version/latest"
AGENT_QUERY_TEMPLATE = Template(
    """{
    createMeches(where:{agentId:$agent_id}) {
        mech
    }
}
"""
)
DELIVER_QUERY_TEMPLATE = Template(
    """{
    delivers(
        orderBy: blockTimestamp
        where: {requestId:"$request_id"}
        orderDirection: desc
    ) {
        ipfsHash
  }
}
"""
)
DEFAULT_TIMEOUT = 600.0


def query_agent_address(
    agent_id: int, timeout: Optional[float] = None
) -> Optional[str]:
    """
    Query agent address from subgraph.

    :param agent_id: The ID of the agent.
    :param timeout: Timeout for the request.
    :type agent_id: int
    :return: The agent address if found, None otherwise.
    :rtype: Optional[str]
    """
    client = Client(
        transport=AIOHTTPTransport(url=MECH_SUBGRAPH_URL),
        execute_timeout=timeout or 30.0,
    )
    response = client.execute(
        document=gql(
            request_string=AGENT_QUERY_TEMPLATE.substitute({"agent_id": agent_id})
        )
    )
    mechs = response["createMeches"]  # pylint: disable=unsubscriptable-object
    if len(mechs) == 0:
        return None

    (record,) = mechs
    return record["mech"]


async def query_deliver_hash(
    request_id: str, timeout: Optional[float] = None
) -> Optional[str]:
    """
    Query deliver IPFS hash from subgraph.

    :param request_id: The ID of the mech request.
    :param timeout: Timeout for the request.
    :type request_id: str
    :return: The deliver IPFS hash if found, None otherwise.
    :rtype: Optional[str]
    """
    client = Client(
        transport=AIOHTTPTransport(url=MECH_SUBGRAPH_URL),
        execute_timeout=timeout or 30.0,
    )
    response = await client.execute_async(
        document=gql(
            request_string=DELIVER_QUERY_TEMPLATE.substitute({"request_id": request_id})
        )
    )
    delivers = response["delivers"]  # pylint: disable=unsubscriptable-object
    if len(delivers) == 0:
        return None

    (record,) = delivers
    return record["ipfsHash"]


async def watch_for_data_url_from_subgraph(
    request_id: str, timeout: Optional[float] = None
) -> Optional[str]:
    """
    Continuously query for data URL until it's available or timeout is reached.

    :param request_id: The ID of the mech request.
    :type request_id: str
    :param timeout: Maximum time to wait for the data URL in seconds. Defaults to DEFAULT_TIMEOUT.
    :type timeout: Optional[float]
    :return: Data URL if available within timeout, otherwise None.
    :rtype: Optional[str]
    """
    timeout = timeout or DEFAULT_TIMEOUT
    start_time = asyncio.get_event_loop().time()
    while True:
        response = await query_deliver_hash(request_id=request_id)
        if response is not None:
            return f"https://gateway.autonolas.tech/ipfs/{response}"

        if asyncio.get_event_loop().time() - start_time >= timeout:
            print(f"Error: No response received after {timeout} seconds.")
            break

        await asyncio.sleep(5)

    return None
