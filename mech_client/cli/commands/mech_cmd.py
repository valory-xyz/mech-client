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

"""Mech command for managing and querying AI mechs on the marketplace."""

from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

import click
import requests
from mech_client.cli.validators import validate_chain_config
from mech_client.domain.tools.manager import ToolManager
from mech_client.infrastructure.config import IPFS_URL_TEMPLATE
from mech_client.infrastructure.subgraph.queries import query_mm_mechs_info
from mech_client.utils.errors.handlers import handle_cli_errors
from tabulate import tabulate  # type: ignore

# Per-mech metadata fetch for the listing; short so one slow gateway read
# cannot stall the whole table, and fetched in parallel so N unreachable
# links cost about one timeout rather than N.
METADATA_FETCH_TIMEOUT = 10
METADATA_FETCH_WORKERS = 8


def _fetch_terms_url(metadata_link: Optional[str]) -> Optional[str]:
    """Read the ``termsUrl`` field from a mech's published metadata.

    :param metadata_link: gateway URL of the metadata document, or None
    :return: the terms URL, or None when there is no link, no field, or the
        fetch fails (the listing must not fail because one mech is unreachable)
    """
    if not metadata_link:
        return None
    try:
        metadata = requests.get(metadata_link, timeout=METADATA_FETCH_TIMEOUT).json()
    except (requests.RequestException, ValueError):
        return None
    return ToolManager.extract_terms_url(metadata)


def _fetch_terms_urls(metadata_links: List[Optional[str]]) -> List[Optional[str]]:
    """Fetch the terms link for every metadata link, in parallel, order kept.

    :param metadata_links: one gateway URL (or None) per mech, in table order
    :return: one terms URL (or None) per mech, in the same order
    """
    if not metadata_links:
        return []
    workers = min(METADATA_FETCH_WORKERS, len(metadata_links))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        return list(executor.map(_fetch_terms_url, metadata_links))


@click.group()
def mech() -> None:
    """Manage and query AI mechs on the marketplace.

    Commands for discovering and retrieving information about available
    AI mechs (on-chain AI agents) on the Mech Marketplace.
    """


@mech.command(name="list")
@click.option(
    "--chain-config",
    type=str,
    required=True,
    help="Chain configuration name (gnosis, base, polygon, optimism, robinhood).",
)
@handle_cli_errors
def mech_list(chain_config: str) -> None:
    """List available mechs on the marketplace.

    Fetches information about all mechs from the marketplace subgraph,
    including service IDs, addresses, delivery counts, and metadata links,
    and reads each mech's terms link from its published metadata.

    Uses default subgraph URL from configuration. Can be overridden with
    MECHX_SUBGRAPH_URL environment variable.

    Example: mechx mech list --chain-config gnosis

    :param chain_config: Chain configuration name (gnosis, base, polygon, optimism, robinhood).
    """
    # Validate chain config
    validated_chain = validate_chain_config(chain_config)

    # Query subgraph for mechs (uses default from config or MECHX_SUBGRAPH_URL override)
    mech_list_data = query_mm_mechs_info(chain_config=validated_chain)
    if not mech_list_data:
        click.echo("No mechs found")
        return

    # Format and display results
    headers = [
        "AI Agent Id",
        "Mech Type",
        "Mech Address",
        "Total Deliveries",
        "Metadata Link",
        "Terms",
    ]

    metadata_links = [
        (
            IPFS_URL_TEMPLATE.format(items["service"]["metadata"][0]["metadata"][2:])
            if items["service"].get("metadata") and items["service"]["metadata"]
            else None
        )
        for items in mech_list_data
    ]
    terms_urls = _fetch_terms_urls(metadata_links)
    data = [
        (
            items["service"]["id"],
            items["mech_type"],
            items["address"],
            items["service"]["totalDeliveries"],
            metadata_link,
            terms_url,
        )
        for items, metadata_link, terms_url in zip(
            mech_list_data, metadata_links, terms_urls
        )
    ]

    click.echo(tabulate(data, headers=headers, tablefmt="grid"))
