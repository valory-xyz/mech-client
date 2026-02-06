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

import os

import click
import requests
from click import ClickException
from tabulate import tabulate  # type: ignore

from mech_client.cli.validators import validate_chain_config
from mech_client.infrastructure.config import IPFS_URL_TEMPLATE
from mech_client.mech_marketplace_subgraph import query_mm_mechs_info


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
    help="Chain configuration name (gnosis, base, polygon, optimism).",
)
def mech_list(chain_config: str) -> None:
    """List available mechs on the marketplace.

    Fetches information about all mechs from the marketplace subgraph,
    including service IDs, addresses, delivery counts, and metadata links.
    Requires MECHX_SUBGRAPH_URL environment variable to be set.

    Example: mechx mech list --chain-config gnosis
    """
    try:
        # Validate chain config
        validated_chain = validate_chain_config(chain_config)

        # Validate MECHX_SUBGRAPH_URL is set
        subgraph_url = os.getenv("MECHX_SUBGRAPH_URL")
        if not subgraph_url:
            raise ClickException(
                "Environment variable MECHX_SUBGRAPH_URL is required for "
                "this command.\n\n"
                f"This command queries blockchain data via a subgraph API.\n"
                f"Current chain: {validated_chain}\n\n"
                f"Please set the subgraph URL:\n"
                f"  export MECHX_SUBGRAPH_URL='https://your-subgraph-url'"
                f"\n\n"
                f"Note: The subgraph URL must match your --chain-config."
            )

        # Query subgraph for mechs
        mech_list_data = query_mm_mechs_info(chain_config=validated_chain)
        if mech_list_data is None:
            click.echo("No mechs found")
            return

        # Format and display results
        headers = [
            "AI Agent Id",
            "Mech Type",
            "Mech Address",
            "Total Deliveries",
            "Metadata Link",
        ]

        data = [
            (
                items["service"]["id"],
                items["mech_type"],
                items["address"],
                items["service"]["totalDeliveries"],
                (
                    IPFS_URL_TEMPLATE.format(
                        items["service"]["metadata"]["metadata"][2:]
                    )
                    if items["service"].get("metadata") is not None
                    else None
                ),
            )
            for items in mech_list_data
        ]

        click.echo(tabulate(data, headers=headers, tablefmt="grid"))

    except requests.exceptions.HTTPError as e:
        subgraph_url = os.getenv("MECHX_SUBGRAPH_URL", "default")
        raise ClickException(
            f"Subgraph endpoint error: {e}\n\n"
            f"Current subgraph URL: {subgraph_url}\n\n"
            f"Possible solutions:\n"
            f"  1. Check if the subgraph endpoint is available\n"
            f"  2. Set a different subgraph URL: "
            f"export MECHX_SUBGRAPH_URL='https://your-subgraph-url'\n"
            f"  3. Check your network connection"
        ) from e
    except (
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
    ) as e:
        subgraph_url = os.getenv("MECHX_SUBGRAPH_URL", "default")
        raise ClickException(
            f"Network error connecting to subgraph: {e}\n\n"
            f"Current subgraph URL: {subgraph_url}\n\n"
            f"Possible solutions:\n"
            f"  1. Check your internet connection\n"
            f"  2. Verify the subgraph URL is correct\n"
            f"  3. Try a different subgraph provider: "
            f"export MECHX_SUBGRAPH_URL='https://your-subgraph-url'"
        ) from e
    except Exception as e:
        raise ClickException(
            f"Error querying subgraph: {e}\n\n"
            f"Please check your MECHX_SUBGRAPH_URL and network connection."
        ) from e
