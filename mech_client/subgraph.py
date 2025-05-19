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
CHAIN_TO_ADDRESSES = {
    "gnosis": {
        3: "0xFf82123dFB52ab75C417195c5fDB87630145ae81",
        6: "0x77af31De935740567Cf4fF1986D04B2c964A786a",
        9: "0x552cea7bc33cbbeb9f1d90c1d11d2c6daeffd053",
        11: "0x9aDe7A78A39B39a44b7a084923E93AA0B19Fd690",
        19: "0x45b73d649c7b982548d5a6dd3d35e1c5c48997d0",
    },
    "base": {
        1: "0x37C484cc34408d0F827DB4d7B6e54b8837Bf8BDA",
        2: "0x111D7DB1B752AB4D2cC0286983D9bd73a49bac6c",
        3: "0x111D7DB1B752AB4D2cC0286983D9bd73a49bac6c",
    },
    "arbitrum": {2: "0x1FDAD3a5af5E96e5a64Fc0662B1814458F114597"},
    "polygon": {2: "0xbF92568718982bf65ee4af4F7020205dE2331a8a"},
    "celo": {2: "0x230eD015735c0D01EA0AaD2786Ed6Bd3C6e75912"},
    "optimism": {2: "0xDd40E7D93c37eFD860Bd53Ab90b2b0a8D05cf71a"},
}


def query_agent_address(  # pylint: disable=too-many-return-statements
    agent_id: int,
    chain_config: Optional[str] = None,
) -> Optional[str]:
    """
    Query agent address from subgraph.

    :param agent_id: The ID of the agent.
    :type agent_id: int
    :type chain_config: Optional[str]:
    :return: The agent address if found, None otherwise.
    :rtype: Optional[str]
    """
    # temporary hard coded until subgraph present
    if not chain_config:
        raise ValueError("Chain config not specified")
    return CHAIN_TO_ADDRESSES.get(chain_config, {}).get(agent_id, None)


async def query_deliver_hash(
    request_id: str, url: str, timeout: Optional[float] = None
) -> Optional[str]:
    """
    Query deliver IPFS hash from subgraph.

    :param request_id: The ID of the mech request.
    :type request_id: str
    :param url: Subgraph URL.
    :type url: str
    :param timeout: Timeout for the request.
    :type timeout: Optional[float]
    :return: The deliver IPFS hash if found, None otherwise.
    :rtype: Optional[str]
    """
    client = Client(
        transport=AIOHTTPTransport(url=url),
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
    request_id: str, url: str, timeout: Optional[float] = None
) -> Optional[str]:
    """
    Continuously query for data URL until it's available or timeout is reached.

    :param request_id: The ID of the mech request.
    :type request_id: str
    :param url: Subgraph URL.
    :type url: str
    :param timeout: Maximum time to wait for the data URL in seconds. Defaults to DEFAULT_TIMEOUT.
    :type timeout: Optional[float]
    :return: Data URL if available within timeout, otherwise None.
    :rtype: Optional[str]
    """
    timeout = timeout or DEFAULT_TIMEOUT
    start_time = asyncio.get_event_loop().time()
    while True:
        response = await query_deliver_hash(request_id=request_id, url=url)
        if response is not None:
            return f"https://gateway.autonolas.tech/ipfs/{response}"

        if asyncio.get_event_loop().time() - start_time >= timeout:
            print(f"Error: No response received after {timeout} seconds.")
            break

        await asyncio.sleep(5)

    return None
