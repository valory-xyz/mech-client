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

import click
from click import ClickException
from tabulate import tabulate  # type: ignore

from mech_client.cli.validators import validate_chain_config
from mech_client.infrastructure.config import IPFS_URL_TEMPLATE
from mech_client.infrastructure.config.environment import EnvironmentConfig
from mech_client.infrastructure.subgraph.queries import query_mm_mechs_info
from mech_client.utils.errors.handlers import handle_cli_errors


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
@handle_cli_errors
def mech_list(chain_config: str) -> None:
    """List available mechs on the marketplace.

    Fetches information about all mechs from the marketplace subgraph,
    including service IDs, addresses, delivery counts, and metadata links.
    Requires MECHX_SUBGRAPH_URL environment variable to be set.

    Example: mechx mech list --chain-config gnosis
    """
    # Validate chain config
    validated_chain = validate_chain_config(chain_config)

    # Load environment configuration
    env_config = EnvironmentConfig.load()

    # Validate MECHX_SUBGRAPH_URL is set
    if not env_config.mechx_subgraph_url:
        raise ClickException(
            "Environment variable MECHX_SUBGRAPH_URL is required for this command.\n\n"
            f"This command queries blockchain data via a subgraph API.\n"
            f"Current chain: {validated_chain}\n\n"
            f"Please set the subgraph URL:\n"
            f"  export MECHX_SUBGRAPH_URL='https://your-subgraph-url'\n\n"
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
                    items["service"]["metadata"][0]["metadata"][2:]
                )
                if items["service"].get("metadata") and items["service"]["metadata"]
                else None
            ),
        )
        for items in mech_list_data
    ]

    click.echo(tabulate(data, headers=headers, tablefmt="grid"))
