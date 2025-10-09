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

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests
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


def _get_client(subgraph_url: str) -> Client:
    """Return configured GraphQL client."""
    return Client(transport=AIOHTTPTransport(url=subgraph_url), execute_timeout=DEFAULT_TIMEOUT)


def _to_epoch(date_str: Optional[str]) -> Optional[int]:
    """Convert YYYY-MM-DD string to epoch seconds (UTC at 00:00)."""
    if not date_str:
        return None
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return int(dt.replace(tzinfo=None).timestamp())


def _to_epoch_end(date_str: Optional[str]) -> Optional[int]:
    """Convert YYYY-MM-DD string to epoch seconds at end of day (UTC 23:59:59)."""
    if not date_str:
        return None
    dt = datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1) - timedelta(seconds=1)
    return int(dt.replace(tzinfo=None).timestamp())


def _hex_to_cid_v1(hex_bytes: str) -> str:
    """Build CIDv1 (base16) from 0x-prefixed hex bytes using f01701220 prefix."""
    hex_clean = hex_bytes[2:] if hex_bytes.startswith("0x") else hex_bytes
    return f"f01701220{hex_clean}"


def _fetch_delivery_json(delivery_url: str, timeout: float = 10.0) -> Optional[Dict[str, Any]]:
    """Fetch JSON from delivery URL (IPFS + request ID)."""
    try:
        resp = requests.get(delivery_url, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception:  # pylint: disable=broad-except
        return None


def _fetch_ipfs_json(ipfs_hash_hex: str, timeout: float = 10.0) -> Optional[Dict[str, Any]]:
    """Fetch JSON from IPFS gateway using on-chain/subgraph hash bytes."""
    cid = _hex_to_cid_v1(ipfs_hash_hex)
    url = f"https://gateway.autonolas.tech/ipfs/{cid}"
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception:  # pylint: disable=broad-except
        return None


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


def query_mech_requests(  # pylint: disable=too-many-arguments, too-many-locals
    chain_config: str = "base",
    requester_address: Optional[str] = None,
    mech_address: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    include_request_data: bool = False,
    include_delivery_data: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """
    Query marketplace requests from the subgraph with optional IPFS data embedding.

    :param chain_config: Chain configuration to use (e.g. "base").
    :param requester_address: Filter by requester address.
    :param mech_address: Filter by priority mech address.
    :param from_date: Inclusive start date (YYYY-MM-DD) for results.
    :param to_date: Inclusive end date (YYYY-MM-DD) for results.
    :param include_request_data: Whether to fetch and embed request IPFS metadata.
    :param include_delivery_data: Whether to fetch and embed delivery IPFS payloads.
    :param limit: Max number of items to return.
    :param offset: Pagination offset.
    :return: List of enriched request dicts.
    """
    mech_config = get_mech_config(chain_config)
    if not mech_config.subgraph_url:
        raise Exception(f"Subgraph URL not set for chain config: {chain_config}")

    client = _get_client(mech_config.subgraph_url)

    where_parts: List[str] = []
    if requester_address:
        where_parts.append(f'requester: "{requester_address.lower()}"')
    if mech_address:
        where_parts.append(f'priorityMech: "{mech_address.lower()}"')
    from_ts = _to_epoch(from_date)
    to_ts = _to_epoch_end(to_date)
    if from_ts is not None:
        where_parts.append(f"blockTimestamp_gte: {from_ts}")
    if to_ts is not None:
        where_parts.append(f"blockTimestamp_lte: {to_ts}")

    where_clause = f"where: {{ {', '.join(where_parts)} }}" if where_parts else ""

    # 1) Base query: marketplaceRequests
    mr_query = f"""
    query {{
      marketplaceRequests({where_clause} orderBy: blockTimestamp, orderDirection: desc, first: {limit}, skip: {offset}) {{
        id
        requester
        priorityMech
        requestIds
        transactionHash
        blockNumber
        blockTimestamp
      }}
    }}
    """
    resp = client.execute(document=gql(mr_query))
    marketplace_requests: List[Dict[str, Any]] = resp.get("marketplaceRequests", [])
    if not marketplace_requests:
        return []

    # Collect requestIds
    request_ids: List[str] = []
    for item in marketplace_requests:
        for rid in item.get("requestIds", []) or []:
            if isinstance(rid, str):
                request_ids.append(rid)

    # Deduplicate
    request_ids = list(dict.fromkeys(request_ids))

    # 2) Correlate to requests for ipfsHash, mech, sender
    request_map: Dict[str, Dict[str, Any]] = {}
    if request_ids:
        ids_csv = ", ".join(f'"{rid}"' for rid in request_ids)
        req_query = f"""
        query {{
          requests(where: {{ requestId_in: [{ids_csv}] }}) {{
            requestId
            ipfsHash
            sender {{ id }}
            mech
            transactionHash
            blockNumber
            blockTimestamp
          }}
        }}
        """
        req_resp = client.execute(document=gql(req_query))
        for r in req_resp.get("requests", []) or []:
            request_map[(r.get("requestId") or "").lower()] = r

    # 3) Correlate deliveries (Deliver entity has ipfsHash per request)
    delivery_map: Dict[str, Dict[str, Any]] = {}
    if request_ids:
        ids_csv = ", ".join(f'"{rid}"' for rid in request_ids)
        del_query = f"""
        query {{
          delivers(where: {{ requestId_in: [{ids_csv}] }}) {{
            requestId
            ipfsHash
            mech
            transactionHash
            blockNumber
            blockTimestamp
          }}
        }}
        """
        del_resp = client.execute(document=gql(del_query))
        for d in del_resp.get("delivers", []) or []:
            delivery_map[(d.get("requestId") or "").lower()] = d

    # 4) Optional IPFS fetches
    # Build final results
    results: List[Dict[str, Any]] = []
    for mr in marketplace_requests:
        for rid in mr.get("requestIds", []) or []:
            rid_key = (rid or "").lower()
            req = request_map.get(rid_key)
            
            # Find delivery for this request ID (Deliver keyed by requestId)
            dev = delivery_map.get(rid_key)

            # Base
            ts = int(mr.get("blockTimestamp", 0))
            item: Dict[str, Any] = {
                "requestId": rid,
                "requester": mr.get("requester"),
                "mech": (req or {}).get("mech", mr.get("priorityMech")),
                "transactionHash": (req or {}).get("transactionHash", mr.get("transactionHash")),
                "timestamp": datetime.utcfromtimestamp(ts).isoformat() + "Z" if ts else None,
            }

            # Request metadata
            if include_request_data and req and req.get("ipfsHash"):
                ipfs_hex = req["ipfsHash"]
                cid = _hex_to_cid_v1(ipfs_hex)
                url = f"https://gateway.autonolas.tech/ipfs/{cid}"
                item["request_data"] = {
                    "url": url,
                    "json": _fetch_ipfs_json(ipfs_hex),
                }
            else:
                item["request_data"] = None

        # Delivery payload from Deliver.ipfsHash
        if include_delivery_data and dev and dev.get("ipfsHash"):
            data_hex = dev["ipfsHash"]
            cid = _hex_to_cid_v1(data_hex)
            base_url = f"https://gateway.autonolas.tech/ipfs/{cid}"
            # Use hex request ID directly (not integer)
            delivery_url = f"{base_url}/{rid}"
            item["delivery_data"] = {
                "url": delivery_url,
                "json": _fetch_delivery_json(delivery_url),
            }
        else:
            item["delivery_data"] = None

            results.append(item)

    return results
