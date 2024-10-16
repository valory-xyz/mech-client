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
import json
from typing import Any, Dict, List, Optional, Tuple

import click
from tabulate import tabulate  # type: ignore

from mech_client import __version__
from mech_client.interact import ConfirmationType
from mech_client.interact import interact as interact_
from mech_client.mech_tool_management import (
    get_tool_description,
    get_tool_io_schema,
    get_tools_for_agents,
)
from mech_client.prompt_to_ipfs import main as prompt_to_ipfs_main
from mech_client.push_to_ipfs import main as push_to_ipfs_main
from mech_client.to_png import main as to_png_main


@click.group(name="mechx")  # type: ignore
@click.version_option(__version__, prog_name="mechx")
def cli() -> None:
    """Command-line tool for interacting with mechs."""


@click.command()
@click.argument("prompt")
@click.argument("agent_id", type=int)
@click.option(
    "--key",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    help="Path to private key to use for request minting",
)
@click.option(
    "--tool",
    type=str,
    help="Name of the tool to be used",
)
@click.option(
    "--extra-attribute",
    type=str,
    multiple=True,
    help="Extra attribute (key=value) to be included in the request metadata",
    metavar="KEY=VALUE",
)
@click.option(
    "--confirm",
    type=click.Choice(
        choices=(ConfirmationType.OFF_CHAIN.value, ConfirmationType.ON_CHAIN.value)
    ),
    help="Data verification method (on-chain/off-chain)",
)
@click.option(
    "--retries",
    type=int,
    help="Number of retries for sending a transaction",
)
@click.option(
    "--timeout",
    type=float,
    help="Timeout to wait for the transaction",
)
@click.option(
    "--sleep",
    type=float,
    help="Amount of sleep before retrying the transaction",
)
@click.option(
    "--chain-config",
    type=str,
    help="Id of the mech's chain configuration (stored configs/mechs.json)",
)
def interact(  # pylint: disable=too-many-arguments
    prompt: str,
    agent_id: int,
    key: Optional[str],
    tool: Optional[str],
    extra_attribute: Optional[List[str]] = None,
    confirm: Optional[str] = None,
    retries: Optional[int] = None,
    timeout: Optional[float] = None,
    sleep: Optional[float] = None,
    chain_config: Optional[str] = None,
) -> None:
    """Interact with a mech specifying a prompt and tool."""
    try:
        extra_attributes_dict: Dict[str, Any] = {}
        if extra_attribute:
            for pair in extra_attribute:
                k, v = pair.split("=")
                extra_attributes_dict[k] = v

        interact_(
            prompt=prompt,
            agent_id=agent_id,
            private_key_path=key,
            tool=tool,
            extra_attributes=extra_attributes_dict,
            confirmation_type=(
                ConfirmationType(confirm)
                if confirm is not None
                else ConfirmationType.WAIT_FOR_BOTH
            ),
            retries=retries,
            timeout=timeout,
            sleep=sleep,
            chain_config=chain_config,
        )
    except (ValueError, FileNotFoundError) as e:
        raise click.ClickException(str(e)) from e


@click.command()
@click.argument("prompt")
@click.argument("tool")
def prompt_to_ipfs(prompt: str, tool: str) -> None:
    """Upload a prompt and tool to IPFS as metadata."""
    prompt_to_ipfs_main(prompt=prompt, tool=tool)


@click.command()
@click.argument("file_path")
def push_to_ipfs(file_path: str) -> None:
    """Upload a file to IPFS."""
    push_to_ipfs_main(file_path=file_path)


@click.command()
@click.argument("ipfs_hash")
@click.argument("path")
@click.argument("request_id")
def to_png(ipfs_hash: str, path: str, request_id: str) -> None:
    """Convert a stability AI API's diffusion model output into a PNG format."""
    to_png_main(ipfs_hash, path, request_id)


@click.command(name="tools-for-agents")
@click.option(
    "--agent-id",
    type=int,
    help="Agent ID to fetch tools for. If not provided, fetches for all agents.",
)
@click.option("--chain-config", default="gnosis", help="Chain configuration to use.")
def tools_for_agents(agent_id: Optional[int], chain_config: str) -> None:
    """Fetch and display tools for agents."""
    try:
        result = get_tools_for_agents(agent_id, chain_config)

        if agent_id is not None:
            headers = ["Tool Name", "Unique Identifier", "Mech Marketplace Support"]
            data: List[Tuple[str, ...]] = [
                (
                    str(tool["tool_name"]),
                    str(tool["unique_identifier"]),
                    "✓" if bool(tool["is_marketplace_supported"]) else "✗",
                )
                for tool in result["tools"]
            ]
        else:
            headers = [
                "Agent ID",
                "Tool Name",
                "Unique Identifier",
                "Mech Marketplace Support",
            ]

            data = [
                (
                    str(agent_id),
                    tool["tool_name"],
                    tool["unique_identifier"],
                    (
                        "✓"
                        if bool(
                            tool["is_marketplace_supported"],
                        )
                        else "✗"
                    ),
                )
                for agent_id, _ in result["agent_tools_map"].items()
                for tool in result["all_tools_with_identifiers"]
                if tool["unique_identifier"].startswith(f"{agent_id}-")
            ]

        click.echo(tabulate(data, headers=headers, tablefmt="grid"))
    except (KeyError, TypeError) as e:
        click.echo(f"Error processing tool data: {str(e)}")
    except json.JSONDecodeError as e:
        click.echo(f"Error decoding JSON response: {str(e)}")
    except IOError as e:
        click.echo(f"Network or I/O error: {str(e)}")


@click.command(name="tool-description")
@click.argument("tool_id")
@click.option("--chain-config", default="gnosis", help="Chain configuration to use.")
def tool_description(tool_id: str, chain_config: str) -> None:
    """Fetch and display the description of a specific tool."""
    try:
        description = get_tool_description(tool_id, chain_config)
        click.echo(f"Description for tool {tool_id}: {description}")
    except KeyError as e:
        click.echo(f"Tool not found or missing description: {str(e)}")
    except json.JSONDecodeError as e:
        click.echo(f"Error decoding JSON response: {str(e)}")
    except IOError as e:
        click.echo(f"Network or I/O error: {str(e)}")


@click.command(name="tool-io-schema")
@click.argument("tool_id")
@click.option("--chain-config", default="gnosis", help="Chain configuration to use.")
def tool_io_schema(tool_id: str, chain_config: str) -> None:
    """Fetch and display the tool's name and description along with the input/output schema for a specific tool."""
    try:
        result = get_tool_io_schema(tool_id, chain_config)

        name = result["name"]
        description = result["description"]
        # Prepare data for tabulation
        input_schema = [(key, result["input"][key]) for key in result["input"]]

        # Handling nested output schema
        output_schema = []
        if "properties" in result["output"]["schema"]:
            for key, value in result["output"]["schema"]["properties"].items():
                output_schema.append((key, value["type"], value.get("description", "")))

        # Display tool details in tabulated format
        click.echo("Tool Details:")
        click.echo(
            tabulate(
                [
                    [
                        name,
                        description,
                    ]
                ],
                headers=["Tool Name", "Tool Description"],
                tablefmt="grid",
            )
        )
        # Display schemas in tabulated format
        click.echo("Input Schema:")
        click.echo(tabulate(input_schema, headers=["Field", "Value"], tablefmt="grid"))
        click.echo("Output Schema:")
        click.echo(
            tabulate(
                output_schema, headers=["Field", "Type", "Description"], tablefmt="grid"
            )
        )
    except KeyError as e:
        click.echo(f"Error accessing schema data: {str(e)}")
    except json.JSONDecodeError as e:
        click.echo(f"Error decoding JSON response: {str(e)}")
    except IOError as e:
        click.echo(f"Network or I/O error: {str(e)}")


cli.add_command(interact)
cli.add_command(prompt_to_ipfs)
cli.add_command(push_to_ipfs)
cli.add_command(to_png)
cli.add_command(tools_for_agents)
cli.add_command(tool_io_schema)
cli.add_command(tool_description)


if __name__ == "__main__":
    cli()
