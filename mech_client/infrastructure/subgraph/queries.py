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

"""Subgraph query functions and mappings."""

from typing import List, Optional

from mech_client.infrastructure.config.loader import get_mech_config
from mech_client.infrastructure.subgraph.client import SubgraphClient


# Mapping of mech factory addresses to mech types per chain
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
    "optimism": {
        "0xf76953444C35F1FcE2F6CA1b167173357d3F5C17": "Fixed Price Native",
        "0x26Ea2dC7ce1b41d0AD0E0521535655d7a94b684c": "Fixed Price Token",
        "0x93111f6C267068A5d7356114D61d0f09bFD53a54": "Fixed Price Token USDC",
        "0x02C26437B292D86c5F4F21bbCcE0771948274f84": "NvmSubscription Token USDC",
    },
    "polygon": {
        "0x87f89F94033305791B6269AE2F9cF4e09983E56e": "Fixed Price Native",
        "0xa0DA53447C0f6C4987964d8463da7e6628B30f82": "Fixed Price Token",
        "0x85899f9d8C058A5BBBaF344ea0f0b63c0CcBe851": "Fixed Price Token USDC",
        "0x43fB32f25dce34EB76c78C7A42C8F40F84BCD237": "NvmSubscription Token USDC",
    },
}

RESULTS_LIMIT = 20


def query_mm_mechs_info(chain_config: str) -> Optional[List]:
    """
    Query marketplace mechs and related info from subgraph.

    Queries the subgraph for mech information, filtering by mechs with
    total deliveries > 0 and enriching with mech type from factory address.

    :param chain_config: Chain configuration name (gnosis, base, polygon, optimism)
    :return: List of mech data dicts, or None if no mechs found
    :raises Exception: If subgraph URL not set for chain
    """
    mech_config = get_mech_config(chain_config)
    if not mech_config.subgraph_url:
        raise Exception(f"Subgraph URL not set for chain config: {chain_config}")

    client = SubgraphClient(mech_config.subgraph_url)
    response = client.query_mechs()

    # Map factory addresses to mech types (case-insensitive)
    mech_factory_to_mech_type = {
        k.lower(): v
        for k, v in CHAIN_TO_MECH_FACTORY_TO_MECH_TYPE[chain_config].items()
    }

    # Filter mechs with deliveries > 0 and add mech type
    filtered_mechs_data = []
    for item in response["meches"]:  # pylint: disable=unsubscriptable-object
        if int(item["totalDeliveriesTransactions"]) > 0:
            factory = item["mechFactory"].lower()
            item["mech_type"] = mech_factory_to_mech_type.get(factory, "Unknown")
            filtered_mechs_data.append(item)

    return filtered_mechs_data[:RESULTS_LIMIT]
