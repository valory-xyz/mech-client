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

"""Setup command for agent mode configuration."""

from pathlib import Path

import click
from click import ClickException

from mech_client.cli.validators import validate_chain_config
from mech_client.services.setup_service import SetupService


CURR_DIR = Path(__file__).resolve().parent.parent.parent
CHAIN_TO_TEMPLATE = {
    "gnosis": CURR_DIR / "config" / "mech_client_gnosis.json",
    "base": CURR_DIR / "config" / "mech_client_base.json",
    "polygon": CURR_DIR / "config" / "mech_client_polygon.json",
    "optimism": CURR_DIR / "config" / "mech_client_optimism.json",
}


@click.command()
@click.option(
    "--chain-config",
    type=str,
    required=True,
    help="Chain configuration name (gnosis, base, polygon, optimism).",
)
def setup(chain_config: str) -> None:
    """Setup agent mode for on-chain interactions via Safe multisig.

    Agent mode registers your interactions as an Olas protocol agent and uses
    a Safe multisig wallet for enhanced security. This is the recommended mode
    for all chains.

    Example: mechx setup --chain-config gnosis
    """
    # Validate chain config
    validated_chain = validate_chain_config(chain_config)

    # Get template path
    template = CHAIN_TO_TEMPLATE.get(validated_chain)
    if template is None:
        supported_chains = ", ".join(CHAIN_TO_TEMPLATE.keys())
        raise ClickException(
            f"Agent mode not supported for chain: {validated_chain!r}\n\n"
            f"Supported chains: {supported_chains}"
        )

    # Create setup service and run setup
    setup_service = SetupService(validated_chain, template)

    try:
        click.echo(f"Setting up agent mode for {validated_chain}...")
        setup_service.setup()

        # Display wallet information
        setup_service.display_wallets()

    except Exception as e:
        raise ClickException(
            f"Failed to setup agent mode: {e}\n\n"
            f"Please check the error message above for details."
        ) from e
