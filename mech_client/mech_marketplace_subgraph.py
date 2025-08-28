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

"""Subgraph client for mech."""

from typing import List, Optional

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport

from mech_client.interact import get_mech_config


RESULTS_LIMIT = 20
CHAIN_TO_MECH_FACTORY_TO_MECH_TYPE = {
    "gnosis": {
        "0x8b299c20F87e3fcBfF0e1B86dC0acC06AB6993EF": "Fixed Price Native",
        "0x31ffDC795FDF36696B8eDF7583A3D115995a45FA": "Fixed Price Token",
        "0x65fd74C29463afe08c879a3020323DD7DF02DA57": "NvmSubscription Native",
    },
    "base": {
        "0x2E008211f34b25A7d7c102403c6C2C3B665a1abe": "Fixed Price Native",
        "0x97371B1C0cDA1D04dFc43DFb50a04645b7Bc9BEe": "Fixed Price Token",
        "0x847bBE8b474e0820215f818858e23F5f5591855A": "NvmSubscription Native",
        "0x7beD01f8482fF686F025628e7780ca6C1f0559fc": "NvmSubscription Token USDC",
    },
}


MM_MECHS_INFO_QUERY = """
query MechsOrderedByServiceDeliveries {
  meches(orderBy: service__totalDeliveries, orderDirection: desc) {
    address
    mechFactory
    service {
      id
      totalDeliveries
      metadata {
        metadata
      }
    }
  }
}
"""

DEFAULT_TIMEOUT = 600.0


def query_mm_mechs_info(chain_config: str) -> Optional[List]:
    """
    Query MM mechs and related info from subgraph.

    :param chain_config: Id of the mech's chain configuration (stored configs/mechs.json)
    :type chain_config: str
    :return: The return list of data if found, None otherwise.
    :rtype: Optional[List]
    """
    mech_config = get_mech_config(chain_config)
    if not mech_config.subgraph_url:
        raise Exception(f"Subgraph URL not set for chain config: {chain_config}")

    client = Client(
        transport=AIOHTTPTransport(url=mech_config.subgraph_url),
        execute_timeout=DEFAULT_TIMEOUT,
    )
    response = client.execute(document=gql(request_string=MM_MECHS_INFO_QUERY))

    mech_factory_to_mech_type = {
        k.lower(): v
        for k, v in CHAIN_TO_MECH_FACTORY_TO_MECH_TYPE[chain_config].items()
    }
    filtered_mechs_data = []
    for item in response["meches"]:  # pylint: disable=unsubscriptable-object
        if item.get("service") and int(item["service"]["totalDeliveries"]) > 0:
            item["mech_type"] = mech_factory_to_mech_type[item["mechFactory"].lower()]
            filtered_mechs_data.append(item)

    return filtered_mechs_data[:RESULTS_LIMIT]
