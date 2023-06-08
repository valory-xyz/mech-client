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

"""Mech client CLI module."""

from typing import Optional

import click

from mech_client import __version__
from mech_client.interact import interact as interact
from mech_client.prompt_to_ipfs import main as prompt_to_ipfs_main
from mech_client.push_to_ipfs import main as push_to_ipfs_main
from mech_client.to_png import main as to_png_main


@click.group(name="mechx")
@click.version_option(__version__, prog_name="mechx")
def cli() -> None:
    """Command-line tool for interacting with mechs."""


@click.command(name="interact")
@click.argument("prompt")
@click.argument("agent_id", type=int)
@click.option(
    "--tool",
    type=str,
)
@click.option(
    "--key",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
)
def _interact(
    prompt: str, agent_id: int, tool: Optional[str], key: Optional[str]
) -> None:
    """Interact with a mech specifying a prompt and tool."""
    try:
        interact(prompt=prompt, agent_id=agent_id, private_key_path=key, tool=tool)
    except (ValueError, FileNotFoundError) as e:
        raise click.ClickException(str(e)) from e


@click.command()
@click.argument("prompt")
@click.argument("tool")
def _prompt_to_ipfs(prompt: str, tool: str) -> None:
    """Upload a prompt and tool to IPFS as metadata."""
    prompt_to_ipfs_main(prompt=prompt, tool=tool)


@click.command()
@click.argument("file_path")
def _push_to_ipfs(file_path: str) -> None:
    """Upload a file to IPFS."""
    push_to_ipfs_main(file_path=file_path)


@click.command()
@click.argument("ipfs_hash")
@click.argument("path")
@click.argument("request_id")
def _to_png(ipfs_hash: str, path: str, request_id: str) -> None:
    """Convert a stability AI API's diffusion model output into a PNG format."""
    to_png_main(ipfs_hash, path, request_id)


cli.add_command(_interact)
cli.add_command(_prompt_to_ipfs)
cli.add_command(_push_to_ipfs)
cli.add_command(_to_png)


if __name__ == "__main__":
    cli()
