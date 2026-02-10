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

"""Main CLI entry point."""

from pathlib import Path

import click
from click import ClickException
from dotenv import load_dotenv

from mech_client import __version__

# Import command groups
from mech_client.cli.commands import (
    deposit,
    ipfs,
    mech,
    request,
    setup,
    subscription,
    tool,
)
from mech_client.utils.logger import setup_logger


# Initialize logging before any commands run
setup_logger()

OPERATE_FOLDER_NAME = ".operate_mech_client"
ENV_PATH = Path.home() / OPERATE_FOLDER_NAME / ".env"
SETUP_MODE_COMMAND = "setup"

# Commands that require wallet operations (agent mode or client mode)
WALLET_COMMANDS = {"request", "deposit", "subscription"}


@click.group(name="mechx")
@click.version_option(__version__, prog_name="mechx")
@click.option(
    "--client-mode",
    is_flag=True,
    help="Enables client mode (EOA-based). Default is agent mode (Safe-based).",
)
@click.pass_context
def cli(ctx: click.Context, client_mode: bool) -> None:
    """Command-line tool for interacting with AI Mechs on-chain.

    Mech Client enables you to send AI task requests to on-chain AI agents (mechs)
    via the Olas (Mech) Marketplace. Supports multiple payment methods,
    tool discovery, and both agent mode (Safe multisig) and client mode (EOA).
    """
    load_dotenv(dotenv_path=ENV_PATH, override=False)
    ctx.ensure_object(dict)
    ctx.obj["client_mode"] = client_mode

    cli_command = ctx.invoked_subcommand if ctx.invoked_subcommand else None
    is_setup_called = cli_command == SETUP_MODE_COMMAND
    is_wallet_command = cli_command in WALLET_COMMANDS

    # Only check agent mode for wallet-based commands
    if is_wallet_command and not is_setup_called and not client_mode:
        click.echo("Agent mode enabled")
        operate_path = Path.home() / OPERATE_FOLDER_NAME
        if not operate_path.exists():
            raise ClickException(
                f"Operate path does not exist at: {operate_path}. "
                f"Setup agent mode using 'mechx setup' command."
            )


# Register command groups
cli.add_command(setup)
cli.add_command(request)
cli.add_command(mech)
cli.add_command(tool)
cli.add_command(deposit)
cli.add_command(subscription)
cli.add_command(ipfs)


if __name__ == "__main__":
    cli()  # pylint: disable=no-value-for-parameter
