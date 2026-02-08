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

"""Tool command for managing and querying mech tools."""

from typing import List, Tuple

import click
from tabulate import tabulate  # type: ignore

from mech_client.cli.validators import validate_chain_config, validate_tool_id
from mech_client.services.tool_service import ToolService
from mech_client.utils.errors.handlers import handle_cli_errors
from mech_client.utils.validators import validate_service_id


@click.group()
def tool() -> None:
    """Manage and query mech tools.

    Commands for discovering available tools, their descriptions, and I/O
    schemas for marketplace mechs. Tools define what AI capabilities a mech
    provides.
    """


@tool.command(name="list")
@click.argument("agent_id", type=int, metavar="<agent-id>")
@click.option(
    "--chain-config",
    required=True,
    help="Chain configuration name (gnosis, base, polygon, optimism).",
)
@handle_cli_errors
def tool_list(agent_id: int, chain_config: str) -> None:
    """List all available tools for a mech.

    Retrieves and displays all tools provided by a specific marketplace mech,
    including tool names and unique identifiers. The agent ID is the service
    ID of the mech on the Olas service registry.

    Example: mechx tool list 1 --chain-config gnosis
    """
    # Validate chain config
    validated_chain = validate_chain_config(chain_config)

    # Validate agent ID (service ID)
    agent_id = validate_service_id(agent_id)

    # Fetch tools
    tool_service = ToolService(validated_chain)
    result = tool_service.get_tools_info(agent_id)

    # Format and display
    headers = ["Tool Name", "Unique Identifier"]
    data: List[Tuple[str, ...]] = [
        (str(tool.tool_name), str(tool.unique_identifier)) for tool in result.tools
    ]

    click.echo(tabulate(data, headers=headers, tablefmt="grid"))


@tool.command(name="describe")
@click.argument("tool_id", metavar="<tool-id>")
@click.option(
    "--chain-config",
    required=True,
    help="Chain configuration name (gnosis, base, polygon, optimism).",
)
@handle_cli_errors
def tool_describe(tool_id: str, chain_config: str) -> None:
    """Get detailed description of a specific tool.

    Retrieves the description for a tool. Tool ID format is
    "service_id-tool_name" (e.g., "1-openai-gpt-4"). Use 'mechx tool list'
    to discover available tools.

    Example: mechx tool describe 1-openai-gpt-4 --chain-config gnosis
    """
    # Validate inputs
    validated_chain = validate_chain_config(chain_config)
    validated_tool_id = validate_tool_id(tool_id)

    # Fetch description
    tool_service = ToolService(validated_chain)
    description = tool_service.get_description(validated_tool_id)
    click.echo(f"Description for tool {tool_id}: {description}")


@tool.command(name="schema")
@click.argument("tool_id", metavar="<tool-id>")
@click.option(
    "--chain-config",
    required=True,
    help="Chain configuration name (gnosis, base, polygon, optimism).",
)
@handle_cli_errors
def tool_schema(tool_id: str, chain_config: str) -> None:
    """Get input/output schema for a specific tool.

    Retrieves the complete I/O schema including tool name, description, input
    fields, and output structure. Tool ID format is "service_id-tool_name"
    (e.g., "1-openai-gpt-4").

    Example: mechx tool schema 1-openai-gpt-4 --chain-config gnosis
    """
    # Validate inputs
    validated_chain = validate_chain_config(chain_config)
    validated_tool_id = validate_tool_id(tool_id)

    # Fetch schema
    tool_service = ToolService(validated_chain)
    result = tool_service.get_schema(validated_tool_id)

    name = result["name"]
    description = result["description"]
    input_schema = tool_service.format_input_schema(result["input"])
    output_schema = tool_service.format_output_schema(result["output"])

    # Display results
    click.echo("Tool Details:")
    click.echo(
        tabulate(
            [[name, description]],
            headers=["Tool Name", "Tool Description"],
            tablefmt="grid",
        )
    )

    click.echo("Input Schema:")
    click.echo(tabulate(input_schema, headers=["Field", "Value"], tablefmt="grid"))

    click.echo("Output Schema:")
    click.echo(
        tabulate(
            output_schema,
            headers=["Field", "Type", "Description"],
            tablefmt="grid",
        )
    )
