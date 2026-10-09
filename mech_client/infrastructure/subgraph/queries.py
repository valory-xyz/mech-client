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

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from mech_client.infrastructure.config.environment import EnvironmentConfig
from mech_client.infrastructure.config.loader import get_mech_config
from mech_client.infrastructure.subgraph.client import SubgraphClient
from mech_client.utils.errors import SubgraphError

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
    "robinhood": {
        "0x04b0007b2aFb398015B76e5f22993a1fddF83644": "Fixed Price Native",
        "0x7Fd1F4b764fA41d19fe3f63C85d12bf64d2bbf68": "Fixed Price Token USDC",
    },
}

RESULTS_LIMIT = 20
# Fields a mech record must carry, and the error raised when it does not.
RECORD_DECODE_ERRORS = (AttributeError, IndexError, KeyError, TypeError, ValueError)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MechRecord:
    """
    One mech's on-chain record, as the marketplace indexer counts it.

    The counters cover requests made on-chain and off-chain requests the mech
    settled on-chain; both paths increment the same counters, so the figures
    cannot be split by path, and an off-chain request that was never
    delivered appears nowhere here.
    """

    service_id: int
    received_requests: int
    self_delivered: int
    delivered_by_others: int
    created_at: datetime
    payment_type: str
    metadata_hash: Optional[str]


def _subgraph_client(chain_config: str) -> SubgraphClient:
    """
    Build the marketplace client for a chain.

    :param chain_config: Chain configuration name
    :return: A client on the chain's marketplace indexer
    :raises SubgraphError: If the chain has no subgraph URL
    """
    mech_config = get_mech_config(chain_config)
    if not mech_config.subgraph_url:
        raise SubgraphError(
            f"Subgraph URL not set for chain config: {chain_config}. "
            "mech list needs a subgraph, and this chain has none configured."
        )

    if (
        mech_config.subgraph_dialect == "squid"
        and EnvironmentConfig.load().mechx_subgraph_url
    ):
        logger.warning(
            "MECHX_SUBGRAPH_URL replaces the endpoint for %s but not its dialect: "
            "this query uses squid syntax",
            chain_config,
        )

    return SubgraphClient(
        mech_config.subgraph_url, dialect=mech_config.subgraph_dialect
    )


def query_mm_mechs_info(chain_config: str) -> List:
    """
    Query marketplace mechs and related info from subgraph.

    Queries the subgraph for mech information, filtering by mechs with
    total deliveries > 0 and enriching with mech type from factory address.

    :param chain_config: Chain configuration name (gnosis, base, polygon, optimism, robinhood)
    :return: List of mech data dicts, empty if the chain has no delivering mechs
    :raises SubgraphError: If the chain has no subgraph URL, or the response is malformed
    """
    response = _subgraph_client(chain_config).query_mechs()

    # Map factory addresses to mech types (case-insensitive)
    mech_factory_to_mech_type = {
        k.lower(): v
        for k, v in CHAIN_TO_MECH_FACTORY_TO_MECH_TYPE.get(chain_config, {}).items()
    }

    # Filter mechs with deliveries > 0 and add mech type
    filtered_mechs_data = []
    try:
        for item in response["meches"]:  # pylint: disable=unsubscriptable-object
            if int(item["totalDeliveriesTransactions"]) > 0:
                factory = item["mechFactory"].lower()
                if factory not in mech_factory_to_mech_type:
                    logger.warning(
                        "Mech factory %s on %s is not in "
                        "CHAIN_TO_MECH_FACTORY_TO_MECH_TYPE; listing its mechs as Unknown",
                        factory,
                        chain_config,
                    )
                item["mech_type"] = mech_factory_to_mech_type.get(factory, "Unknown")
                filtered_mechs_data.append(item)
    except (AttributeError, KeyError, TypeError, ValueError) as error:
        raise SubgraphError(
            f"Malformed mech record from the {chain_config} subgraph: {error}"
        ) from error

    return filtered_mechs_data[:RESULTS_LIMIT]


def _metadata_hash(service: Dict[str, Any]) -> Optional[str]:
    """
    Read the manifest hash a service publishes, if any.

    :param service: The ``service`` object of a mech record
    :return: The hash as the indexer stores it, or None when none is published
    """
    metadata = service.get("metadata")
    if not metadata:
        return None
    value = metadata[0]["metadata"]
    return value if isinstance(value, str) and value else None


def query_mech_record(chain_config: str, mech_address: str) -> MechRecord:
    """
    Query one mech's on-chain record from the marketplace indexer.

    :param chain_config: Chain configuration name
    :param mech_address: The mech contract address
    :return: The mech's record
    :raises SubgraphError: If the chain has no subgraph URL, the mech is not
        indexed there, or the record cannot be read
    """
    response = _subgraph_client(chain_config).query_mech(mech_address)
    try:
        mechs = response["meches"]  # pylint: disable=unsubscriptable-object
        creations = response["createMeches"]  # pylint: disable=unsubscriptable-object
        if not isinstance(mechs, list) or not isinstance(creations, list):
            raise TypeError("meches and createMeches must be lists")
        if not mechs or not creations:
            raise SubgraphError(
                f"Mech {mech_address} is not indexed by the {chain_config} subgraph."
            )
        mech = mechs[0]
        return MechRecord(
            service_id=int(mech["service"]["id"]),
            received_requests=int(mech["receivedRequests"]),
            self_delivered=int(mech["selfDeliveredFromReceived"]),
            delivered_by_others=int(mech["deliveredByOthersFromReceived"]),
            created_at=datetime.fromtimestamp(
                int(creations[0]["blockTimestamp"]), tz=timezone.utc
            ),
            payment_type=str(mech["paymentType"]),
            metadata_hash=_metadata_hash(mech["service"]),
        )
    except RECORD_DECODE_ERRORS as error:
        raise SubgraphError(
            f"Malformed mech record from the {chain_config} subgraph: {error}"
        ) from error


def query_mech_creations(
    chain_config: str, mech_addresses: List[str]
) -> Dict[str, datetime]:
    """
    Query when several mechs were created, in one request.

    :param chain_config: Chain configuration name
    :param mech_addresses: The mech contract addresses
    :return: Creation time (UTC) by lowercase address; a mech the indexer has
        no creation row for is left out
    :raises SubgraphError: If the chain has no subgraph URL, or a row cannot be read
    """
    if not mech_addresses:
        return {}
    response = _subgraph_client(chain_config).query_mech_creations(mech_addresses)
    created_at: Dict[str, datetime] = {}
    try:
        for row in response["createMeches"]:  # pylint: disable=unsubscriptable-object
            created_at[str(row["mech"]).lower()] = datetime.fromtimestamp(
                int(row["blockTimestamp"]), tz=timezone.utc
            )
    except RECORD_DECODE_ERRORS as error:
        raise SubgraphError(
            f"Malformed mech creation row from the {chain_config} subgraph: {error}"
        ) from error
    return created_at


def query_erc8004_agent_id(chain_config: str, service_id: int) -> Optional[int]:
    """
    Query a service's ERC-8004 agent id from the chain's service registry indexer.

    The agent id is not the Olas service id, except by coincidence.

    :param chain_config: Chain configuration name
    :param service_id: The Olas service id
    :return: The agent id, or None when the service has no ERC-8004 identity
    :raises SubgraphError: If the chain has no registry subgraph URL, or the
        response cannot be read
    """
    mech_config = get_mech_config(chain_config)
    if not mech_config.registry_subgraph_url:
        raise SubgraphError(
            f"Registry subgraph URL not set for chain config: {chain_config}. "
            "Checking an operator's domain needs the service registry indexer."
        )
    client = SubgraphClient(
        mech_config.registry_subgraph_url, dialect=mech_config.subgraph_dialect
    )
    response = client.query_service_agent_id(service_id)
    lookup = "serviceById" if mech_config.subgraph_dialect == "squid" else "service"
    try:
        service = response[lookup]  # pylint: disable=unsubscriptable-object
        if service is None:
            return None
        agent = service["erc8004Agent"]
        if agent is None:
            return None
        return int(agent["id"])
    except RECORD_DECODE_ERRORS as error:
        raise SubgraphError(
            f"Malformed service record from the {chain_config} registry subgraph: "
            f"{error}"
        ) from error
