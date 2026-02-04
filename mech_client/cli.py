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
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import click
import requests
from click import ClickException
from dotenv import load_dotenv, set_key
from operate.cli import OperateApp
from operate.cli import logger as operate_logger
from operate.constants import NO_STAKING_PROGRAM_ID
from operate.operate_types import ServiceTemplate
from operate.quickstart.run_service import (
    QuickstartConfig,
    ask_password_if_needed,
    load_local_config,
    run_service,
)
from operate.services.manage import KeysManager
from tabulate import tabulate  # type: ignore

from mech_client import __version__
from mech_client.interact import ConfirmationType, get_mech_config
from mech_client.interact import interact as interact_
from mech_client.marketplace_interact import IPFS_URL_TEMPLATE
from mech_client.marketplace_interact import (
    marketplace_interact as marketplace_interact_,
)
from mech_client.mech_marketplace_subgraph import query_mm_mechs_info
from mech_client.mech_marketplace_tool_management import (
    extract_input_schema,
    extract_output_schema,
)
from mech_client.mech_marketplace_tool_management import (
    get_tool_description as get_tool_description_for_marketplace_mech,
)
from mech_client.mech_marketplace_tool_management import (
    get_tool_io_schema as get_tool_io_schema_for_marketplace_mech,
)
from mech_client.mech_marketplace_tool_management import get_tools_for_marketplace_mech
from mech_client.mech_tool_management import (
    get_tool_description,
    get_tool_io_schema,
    get_tools_for_agents,
)
from mech_client.prompt_to_ipfs import main as prompt_to_ipfs_main
from mech_client.push_to_ipfs import main as push_to_ipfs_main
from mech_client.to_png import main as to_png_main
from scripts.deposit_native import main as deposit_native_main
from scripts.deposit_token import main as deposit_token_main
from scripts.nvm_subscribe import main as nvm_subscribe_main


CURR_DIR = Path(__file__).resolve().parent
BASE_DIR = CURR_DIR.parent
OPERATE_FOLDER_NAME = ".operate_mech_client"
SETUP_MODE_COMMAND = "setup-agent-mode"
DEFAULT_NETWORK = "gnosis"

CHAIN_TO_TEMPLATE = {
    "gnosis": CURR_DIR / "config" / "mech_client_gnosis.json",
    "base": CURR_DIR / "config" / "mech_client_base.json",
    "polygon": CURR_DIR / "config" / "mech_client_polygon.json",
}

ENV_PATH = BASE_DIR / ".env"


def get_operate_path() -> Path:
    """Fetches the operate path for the mech client service"""
    home = Path.home()
    operate_path = home.joinpath(OPERATE_FOLDER_NAME)
    return operate_path


def is_agent_mode(ctx: click.Context) -> bool:
    """Fetches whether agent mode is on or not"""
    client_mode = ctx.obj.get("client_mode", False)
    agent_mode = not client_mode
    return agent_mode


def get_password(operate: OperateApp) -> str:
    """Load password from env/.env if present, otherwise prompt once and persist."""
    load_dotenv(dotenv_path=ENV_PATH, override=False)
    env_password = os.getenv("OPERATE_PASSWORD")
    if env_password:
        os.environ["OPERATE_PASSWORD"] = env_password
        os.environ["ATTENDED"] = "false"
        return os.environ["OPERATE_PASSWORD"]

    ask_password_if_needed(operate)
    if not operate.password:
        raise ClickException("Password could not be set for Operate.")

    os.environ["OPERATE_PASSWORD"] = operate.password
    set_key(str(ENV_PATH), "OPERATE_PASSWORD", os.environ["OPERATE_PASSWORD"])
    os.environ["ATTENDED"] = "false"
    return os.environ["OPERATE_PASSWORD"]


def mech_client_configure_local_config(
    template: ServiceTemplate, operate: "OperateApp"
) -> QuickstartConfig:
    """Configure local quickstart configuration."""
    config = load_local_config(operate=operate, service_name=template["name"])

    if config.rpc is None:
        config.rpc = {}

    for chain in template["configurations"]:
        # Use environment variable if set, otherwise fall back to default from mechs.json
        env_rpc = os.getenv("MECHX_CHAIN_RPC")
        if env_rpc is None:
            mech_config = get_mech_config(chain)
            env_rpc = mech_config.rpc_url
        config.rpc[chain] = env_rpc

    config.principal_chain = template["home_chain"]

    # set chain configs in the service template
    for chain in template["configurations"]:
        template["configurations"][chain] |= {
            "staking_program_id": NO_STAKING_PROGRAM_ID,
            "rpc": config.rpc[chain],
            "cost_of_bond": 1,
        }

    if config.user_provided_args is None:
        config.user_provided_args = {}

    config.store()
    return config


def fetch_agent_mode_data(
    chain_config: Optional[str],
) -> Tuple[str, str, Optional[str]]:
    """Fetches the agent mode data of safe address and the keystore path plus password"""
    chain_config = chain_config or DEFAULT_NETWORK

    # This is acceptable way to as the main functionality
    # of keys manager is to allow access to the required data.
    operate_path = get_operate_path()
    operate = OperateApp(operate_path)
    # Ensure the password is loaded so keys can be decrypted.
    get_password(operate)
    keys_manager = KeysManager(
        path=operate._keys,  # pylint: disable=protected-access
        logger=operate_logger,
        password=operate.password,
    )
    service_manager = operate.service_manager()
    service_config_id = None
    for service in service_manager.json:
        if service["home_chain"] == chain_config:
            service_config_id = service["service_config_id"]
            break

    if not service_config_id:
        raise ClickException(
            f"""Cannot find deployed service id for chain {chain_config}. Setup agent mode for a chain using mechx setup-agent-mode cli command."""
        )

    service = operate.service_manager().load(service_config_id)

    key_path = keys_manager.get_private_key_file(service.agent_addresses[0])
    safe = service.chain_configs[chain_config].chain_data.multisig

    return safe, str(key_path), os.getenv("OPERATE_PASSWORD")


@click.group(name="mechx")  # type: ignore
@click.version_option(__version__, prog_name="mechx")
@click.option(
    "--client-mode",
    is_flag=True,
    help="Enables client mode",
)
@click.pass_context
def cli(ctx: click.Context, client_mode: bool) -> None:
    """Command-line tool for interacting with mechs."""
    ctx.ensure_object(dict)
    ctx.obj["client_mode"] = client_mode

    cli_command = ctx.invoked_subcommand if ctx.invoked_subcommand else None
    is_setup_called = cli_command == SETUP_MODE_COMMAND

    if not is_setup_called and not client_mode:
        click.echo("Agent mode enabled")
        operate_path = get_operate_path()
        if not operate_path.exists():
            raise ClickException(
                f"""Operate path does not exists at: {operate_path}. Setup agent mode for a chain using mechx setup-agent-mode cli command."""
            )


@click.command()
@click.option(
    "--chain-config",
    type=str,
    help="Id of the mech's chain configuration (stored configs/mechs.json)",
)
def setup_agent_mode(
    chain_config: str,
) -> None:
    """Sets up the agent mode for users"""
    template = CHAIN_TO_TEMPLATE.get(chain_config)
    if template is None:
        supported_chains = list(CHAIN_TO_TEMPLATE.keys())
        raise ClickException(
            f"""{chain_config} chain not supported for agent mode. Supported chains are: {supported_chains}"""
        )

    operate_path = get_operate_path()
    operate = OperateApp(operate_path)
    operate.setup()
    get_password(operate)

    sys.modules[
        "operate.quickstart.run_service"
    ].configure_local_config = mech_client_configure_local_config  # type: ignore

    print(f"Setting up agent mode using config at {template}...")
    try:
        run_service(
            operate=operate,
            config_path=template,
            build_only=True,
            use_binary=True,
            skip_dependency_check=False,
        )
    except requests.exceptions.HTTPError as e:
        rpc_url = os.getenv("MECHX_CHAIN_RPC", "default")
        raise ClickException(
            f"RPC endpoint error: {e}\n\n"
            f"Current RPC: {rpc_url}\n\n"
            f"Possible solutions:\n"
            f"  1. Check if the RPC endpoint is available and accessible\n"
            f"  2. Set a different RPC endpoint: export MECHX_CHAIN_RPC='https://your-rpc-url'\n"
            f"  3. Check your network connection"
        ) from e
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
        rpc_url = os.getenv("MECHX_CHAIN_RPC", "default")
        raise ClickException(
            f"Network error connecting to RPC endpoint: {e}\n\n"
            f"Current RPC: {rpc_url}\n\n"
            f"Possible solutions:\n"
            f"  1. Check your internet connection\n"
            f"  2. Verify the RPC URL is correct\n"
            f"  3. Try a different RPC provider: export MECHX_CHAIN_RPC='https://your-rpc-url'"
        ) from e


@click.command()
@click.option(
    "--prompts",
    type=str,
    multiple=True,
    required=True,
    help="One or more prompts to send as a request. Can be repeated.",
)
@click.option("--agent_id", type=int, help="Id of the agent to be used")
@click.option(
    "--priority-mech",
    type=str,
    help="Priority Mech to be used for Marketplace Requests",
)
@click.option(
    "--use-prepaid",
    type=bool,
    help="Uses the prepaid model for marketplace requests",
)
@click.option(
    "--use-offchain",
    type=bool,
    help="Uses the offchain model for marketplace requests",
)
@click.option(
    "--key",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    help="Path to private key to use for request minting",
)
@click.option(
    "--tools",
    type=str,
    multiple=True,
    help="One or more tools to be used. Can be repeated.",
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
@click.pass_context
def interact(  # pylint: disable=too-many-arguments,too-many-locals
    ctx: click.Context,
    prompts: tuple,
    agent_id: int,
    priority_mech: str,
    use_prepaid: bool,
    use_offchain: bool,
    key: Optional[str],
    tools: Optional[tuple],
    safe: Optional[str] = None,
    extra_attribute: Optional[List[str]] = None,
    confirm: Optional[str] = None,
    retries: Optional[int] = None,
    timeout: Optional[float] = None,
    sleep: Optional[float] = None,
    chain_config: Optional[str] = None,
) -> None:
    """Interact with a mech specifying a prompt and tool."""
    try:
        agent_mode = is_agent_mode(ctx)
        click.echo(f"Running interact with agent_mode={agent_mode}")
        key_path: Optional[str] = key
        key_password: Optional[str] = None

        extra_attributes_dict: Dict[str, Any] = {}
        if extra_attribute:
            for pair in extra_attribute:
                k, v = pair.split("=")
                extra_attributes_dict[k] = v

        use_offchain = use_offchain or False
        use_prepaid = use_prepaid or use_offchain

        mech_offchain_url = os.getenv("MECHX_MECH_OFFCHAIN_URL")
        if use_offchain and not mech_offchain_url:
            raise Exception(
                "To use offchain requests, please set MECHX_MECH_OFFCHAIN_URL"
            )

        if agent_id is None:
            if len(prompts) != len(tools):
                raise ClickException(
                    f"The number of prompts ({len(prompts)}) must match the number of tools ({len(tools)})"
                )

            if agent_mode:
                safe, key_path, key_password = fetch_agent_mode_data(chain_config)
                if not safe or not key_path:
                    raise ClickException(
                        "Cannot fetch safe or key data for the agent mode."
                    )

            marketplace_interact_(
                prompts=prompts,
                priority_mech=priority_mech,
                agent_mode=agent_mode,
                safe_address=safe,
                use_prepaid=use_prepaid,
                use_offchain=use_offchain,
                mech_offchain_url=mech_offchain_url,
                private_key_path=key_path,
                private_key_password=key_password,
                tools=tools,
                extra_attributes=extra_attributes_dict,
                retries=retries,
                timeout=timeout,
                sleep=sleep,
                chain_config=chain_config,
            )

        else:
            if use_prepaid:
                raise Exception(
                    "Prepaid model can only be used for marketplace requests"
                )

            if use_offchain:
                raise Exception(
                    "Offchain model can only be used for marketplace requests"
                )

            if len(prompts) > 1:
                raise ClickException(
                    f"Error: Batch prompts ({len(prompts)}) not supported for legacy mechs"
                )

            interact_(
                prompt=prompts[0],
                agent_id=agent_id,
                private_key_path=key_path,
                private_key_password=key_password,
                tool=tools[0] if tools else None,
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
    except requests.exceptions.HTTPError as e:
        rpc_url = os.getenv("MECHX_CHAIN_RPC", "default")
        raise ClickException(
            f"RPC endpoint error: {e}\n\n"
            f"Current RPC: {rpc_url}\n\n"
            f"Possible solutions:\n"
            f"  1. Check if the RPC endpoint is available and accessible\n"
            f"  2. Set a different RPC endpoint: export MECHX_CHAIN_RPC='https://your-rpc-url'\n"
            f"  3. Check your network connection"
        ) from e
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
        rpc_url = os.getenv("MECHX_CHAIN_RPC", "default")
        raise ClickException(
            f"Network error connecting to RPC endpoint: {e}\n\n"
            f"Current RPC: {rpc_url}\n\n"
            f"Possible solutions:\n"
            f"  1. Check your internet connection\n"
            f"  2. Verify the RPC URL is correct\n"
            f"  3. Try a different RPC provider: export MECHX_CHAIN_RPC='https://your-rpc-url'"
        ) from e
    except (ValueError, FileNotFoundError, Exception) as e:
        raise ClickException(str(e)) from e


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
    except requests.exceptions.HTTPError as e:
        rpc_url = os.getenv("MECHX_CHAIN_RPC", "default")
        raise ClickException(
            f"RPC endpoint error: {e}\n\n"
            f"Current RPC: {rpc_url}\n\n"
            f"Possible solutions:\n"
            f"  1. Check if the RPC endpoint is available and accessible\n"
            f"  2. Set a different RPC endpoint: export MECHX_CHAIN_RPC='https://your-rpc-url'\n"
            f"  3. Check your network connection"
        ) from e
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
        rpc_url = os.getenv("MECHX_CHAIN_RPC", "default")
        raise ClickException(
            f"Network error connecting to RPC endpoint: {e}\n\n"
            f"Current RPC: {rpc_url}\n\n"
            f"Possible solutions:\n"
            f"  1. Check your internet connection\n"
            f"  2. Verify the RPC URL is correct\n"
            f"  3. Try a different RPC provider: export MECHX_CHAIN_RPC='https://your-rpc-url'"
        ) from e
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
    except requests.exceptions.HTTPError as e:
        rpc_url = os.getenv("MECHX_CHAIN_RPC", "default")
        raise ClickException(
            f"RPC endpoint error: {e}\n\n"
            f"Current RPC: {rpc_url}\n\n"
            f"Possible solutions:\n"
            f"  1. Check if the RPC endpoint is available and accessible\n"
            f"  2. Set a different RPC endpoint: export MECHX_CHAIN_RPC='https://your-rpc-url'\n"
            f"  3. Check your network connection"
        ) from e
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
        rpc_url = os.getenv("MECHX_CHAIN_RPC", "default")
        raise ClickException(
            f"Network error connecting to RPC endpoint: {e}\n\n"
            f"Current RPC: {rpc_url}\n\n"
            f"Possible solutions:\n"
            f"  1. Check your internet connection\n"
            f"  2. Verify the RPC URL is correct\n"
            f"  3. Try a different RPC provider: export MECHX_CHAIN_RPC='https://your-rpc-url'"
        ) from e
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
    except requests.exceptions.HTTPError as e:
        rpc_url = os.getenv("MECHX_CHAIN_RPC", "default")
        raise ClickException(
            f"RPC endpoint error: {e}\n\n"
            f"Current RPC: {rpc_url}\n\n"
            f"Possible solutions:\n"
            f"  1. Check if the RPC endpoint is available and accessible\n"
            f"  2. Set a different RPC endpoint: export MECHX_CHAIN_RPC='https://your-rpc-url'\n"
            f"  3. Check your network connection"
        ) from e
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
        rpc_url = os.getenv("MECHX_CHAIN_RPC", "default")
        raise ClickException(
            f"Network error connecting to RPC endpoint: {e}\n\n"
            f"Current RPC: {rpc_url}\n\n"
            f"Possible solutions:\n"
            f"  1. Check your internet connection\n"
            f"  2. Verify the RPC URL is correct\n"
            f"  3. Try a different RPC provider: export MECHX_CHAIN_RPC='https://your-rpc-url'"
        ) from e
    except KeyError as e:
        click.echo(f"Error accessing schema data: {str(e)}")
    except json.JSONDecodeError as e:
        click.echo(f"Error decoding JSON response: {str(e)}")
    except IOError as e:
        click.echo(f"Network or I/O error: {str(e)}")


@click.command(name="tools-for-marketplace-mech")
@click.argument(
    "service-id",
    type=int,
)
@click.option("--chain-config", default="gnosis", help="Chain configuration to use.")
def tools_for_marketplace_mech(service_id: int, chain_config: str) -> None:
    """Fetch and display tools for marketplace mechs."""
    try:
        result = get_tools_for_marketplace_mech(service_id, chain_config)

        headers = ["Tool Name", "Unique Identifier"]
        data: List[Tuple[str, ...]] = [
            (
                str(tool.tool_name),
                str(tool.unique_identifier),
            )
            for tool in result.tools
        ]

        click.echo(tabulate(data, headers=headers, tablefmt="grid"))

    except requests.exceptions.HTTPError as e:
        rpc_url = os.getenv("MECHX_CHAIN_RPC", "default")
        raise ClickException(
            f"RPC endpoint error: {e}\n\n"
            f"Current RPC: {rpc_url}\n\n"
            f"Possible solutions:\n"
            f"  1. Check if the RPC endpoint is available and accessible\n"
            f"  2. Set a different RPC endpoint: export MECHX_CHAIN_RPC='https://your-rpc-url'\n"
            f"  3. Check your network connection"
        ) from e
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
        rpc_url = os.getenv("MECHX_CHAIN_RPC", "default")
        raise ClickException(
            f"Network error connecting to RPC endpoint: {e}\n\n"
            f"Current RPC: {rpc_url}\n\n"
            f"Possible solutions:\n"
            f"  1. Check your internet connection\n"
            f"  2. Verify the RPC URL is correct\n"
            f"  3. Try a different RPC provider: export MECHX_CHAIN_RPC='https://your-rpc-url'"
        ) from e
    except (KeyError, TypeError) as e:
        click.echo(f"Error processing tool data: {str(e)}")
    except IOError as e:
        click.echo(f"Network or I/O error: {str(e)}")


@click.command(name="tool-description-for-marketplace-mech")
@click.argument("tool_id")
@click.option("--chain-config", default="gnosis", help="Chain configuration to use.")
def tool_description_for_marketplace_mech(tool_id: str, chain_config: str) -> None:
    """Fetch and display the description of a specific tool for marketplace mechs."""
    try:
        description = get_tool_description_for_marketplace_mech(tool_id, chain_config)
        click.echo(f"Description for tool {tool_id}: {description}")
    except requests.exceptions.HTTPError as e:
        rpc_url = os.getenv("MECHX_CHAIN_RPC", "default")
        raise ClickException(
            f"RPC endpoint error: {e}\n\n"
            f"Current RPC: {rpc_url}\n\n"
            f"Possible solutions:\n"
            f"  1. Check if the RPC endpoint is available and accessible\n"
            f"  2. Set a different RPC endpoint: export MECHX_CHAIN_RPC='https://your-rpc-url'\n"
            f"  3. Check your network connection"
        ) from e
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
        rpc_url = os.getenv("MECHX_CHAIN_RPC", "default")
        raise ClickException(
            f"Network error connecting to RPC endpoint: {e}\n\n"
            f"Current RPC: {rpc_url}\n\n"
            f"Possible solutions:\n"
            f"  1. Check your internet connection\n"
            f"  2. Verify the RPC URL is correct\n"
            f"  3. Try a different RPC provider: export MECHX_CHAIN_RPC='https://your-rpc-url'"
        ) from e
    except KeyError as e:
        click.echo(f"Tool not found or missing description: {str(e)}")
    except IOError as e:
        click.echo(f"Network or I/O error: {str(e)}")


@click.command(name="tool-io-schema-for-marketplace-mech")
@click.argument("tool_id")
@click.option("--chain-config", default="gnosis", help="Chain configuration to use.")
def tool_io_schema_for_marketplace_mech(tool_id: str, chain_config: str) -> None:
    """Fetch and display the tool's name and description along with the input/output schema for a specific tool for marketplace mechs."""
    try:
        result = get_tool_io_schema_for_marketplace_mech(tool_id, chain_config)

        name = result["name"]
        description = result["description"]
        input_schema = extract_input_schema(result["input"])
        output_schema = extract_output_schema(result["output"])

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
                output_schema, headers=["Field", "Type", "Description"], tablefmt="grid"
            )
        )
    except requests.exceptions.HTTPError as e:
        rpc_url = os.getenv("MECHX_CHAIN_RPC", "default")
        raise ClickException(
            f"RPC endpoint error: {e}\n\n"
            f"Current RPC: {rpc_url}\n\n"
            f"Possible solutions:\n"
            f"  1. Check if the RPC endpoint is available and accessible\n"
            f"  2. Set a different RPC endpoint: export MECHX_CHAIN_RPC='https://your-rpc-url'\n"
            f"  3. Check your network connection"
        ) from e
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
        rpc_url = os.getenv("MECHX_CHAIN_RPC", "default")
        raise ClickException(
            f"Network error connecting to RPC endpoint: {e}\n\n"
            f"Current RPC: {rpc_url}\n\n"
            f"Possible solutions:\n"
            f"  1. Check your internet connection\n"
            f"  2. Verify the RPC URL is correct\n"
            f"  3. Try a different RPC provider: export MECHX_CHAIN_RPC='https://your-rpc-url'"
        ) from e
    except KeyError as e:
        click.echo(f"Error accessing schema data: {str(e)}")
    except IOError as e:
        click.echo(f"Network or I/O error: {str(e)}")


@click.command(name="deposit-native")
@click.argument("amount_to_deposit")
@click.option(
    "--chain-config",
    type=str,
    help="Id of the mech's chain configuration (stored configs/mechs.json)",
)
@click.option(
    "--key",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    help="Path to private key to use for deposit",
)
@click.pass_context
def deposit_native(
    ctx: click.Context,
    amount_to_deposit: str,
    key: Optional[str] = None,
    safe: Optional[str] = None,
    chain_config: Optional[str] = None,
) -> None:
    """Deposits Native balance for prepaid requests."""
    try:
        agent_mode = is_agent_mode(ctx)
        click.echo(f"Running deposit native with agent_mode={agent_mode}")

        key_path: Optional[str] = key
        key_password: Optional[str] = None
        if agent_mode:
            safe, key_path, key_password = fetch_agent_mode_data(chain_config)
            if not safe or not key_path:
                raise ClickException(
                    "Cannot fetch safe or key data for the agent mode."
                )

        deposit_native_main(
            agent_mode=agent_mode,
            safe_address=safe,
            amount=amount_to_deposit,
            private_key_path=key_path,
            private_key_password=key_password,
            chain_config=chain_config,
        )
    except requests.exceptions.HTTPError as e:
        rpc_url = os.getenv("MECHX_CHAIN_RPC", "default")
        raise ClickException(
            f"RPC endpoint error: {e}\n\n"
            f"Current RPC: {rpc_url}\n\n"
            f"Possible solutions:\n"
            f"  1. Check if the RPC endpoint is available and accessible\n"
            f"  2. Set a different RPC endpoint: export MECHX_CHAIN_RPC='https://your-rpc-url'"
        ) from e
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
        rpc_url = os.getenv("MECHX_CHAIN_RPC", "default")
        raise ClickException(
            f"Network error connecting to RPC endpoint: {e}\n\n"
            f"Current RPC: {rpc_url}\n\n"
            f"Possible solutions:\n"
            f"  1. Check your internet connection\n"
            f"  2. Verify the RPC URL is correct\n"
            f"  3. Try a different RPC provider: export MECHX_CHAIN_RPC='https://your-rpc-url'"
        ) from e


@click.command(name="deposit-token")
@click.argument("amount_to_deposit")
@click.option(
    "--chain-config",
    type=str,
    help="Id of the mech's chain configuration (stored configs/mechs.json)",
)
@click.option(
    "--key",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    help="Path to private key to use for deposit",
)
@click.pass_context
def deposit_token(
    ctx: click.Context,
    amount_to_deposit: str,
    key: Optional[str] = None,
    safe: Optional[str] = None,
    chain_config: Optional[str] = None,
) -> None:
    """Deposits Token balance for prepaid requests."""
    try:
        agent_mode = is_agent_mode(ctx)
        click.echo(f"Running deposit token with agent_mode={agent_mode}")

        key_path: Optional[str] = key
        key_password: Optional[str] = None
        if agent_mode:
            safe, key_path, key_password = fetch_agent_mode_data(chain_config)
            if not safe or not key_path:
                raise ClickException(
                    "Cannot fetch safe or key data for the agent mode."
                )

        deposit_token_main(
            agent_mode=agent_mode,
            safe_address=safe,
            amount=amount_to_deposit,
            private_key_path=key_path,
            private_key_password=key_password,
            chain_config=chain_config,
        )
    except requests.exceptions.HTTPError as e:
        rpc_url = os.getenv("MECHX_CHAIN_RPC", "default")
        raise ClickException(
            f"RPC endpoint error: {e}\n\n"
            f"Current RPC: {rpc_url}\n\n"
            f"Possible solutions:\n"
            f"  1. Check if the RPC endpoint is available and accessible\n"
            f"  2. Set a different RPC endpoint: export MECHX_CHAIN_RPC='https://your-rpc-url'"
        ) from e
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
        rpc_url = os.getenv("MECHX_CHAIN_RPC", "default")
        raise ClickException(
            f"Network error connecting to RPC endpoint: {e}\n\n"
            f"Current RPC: {rpc_url}\n\n"
            f"Possible solutions:\n"
            f"  1. Check your internet connection\n"
            f"  2. Verify the RPC URL is correct\n"
            f"  3. Try a different RPC provider: export MECHX_CHAIN_RPC='https://your-rpc-url'"
        ) from e


@click.command(name="purchase-nvm-subscription")
@click.option(
    "--chain-config",
    type=str,
    help="Id of the mech's chain configuration (stored configs/mechs.json)",
)
@click.option(
    "--key",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    help="Path to private key to use for deposit",
)
@click.pass_context
def nvm_subscribe(
    ctx: click.Context,
    chain_config: str,
    safe: Optional[str] = None,
    key: Optional[str] = None,
) -> None:
    """Allows to purchase nvm subscription for nvm mech requests."""
    try:
        agent_mode = is_agent_mode(ctx)
        click.echo(f"Running purchase nvm subscription with agent_mode={agent_mode}")

        key_path: Optional[str] = key
        key_password: Optional[str] = None
        if agent_mode:
            safe, key_path, key_password = fetch_agent_mode_data(chain_config)
            if not safe or not key_path:
                raise ClickException(
                    "Cannot fetch safe or key data for the agent mode."
                )

        nvm_subscribe_main(
            agent_mode=agent_mode,
            safe_address=safe,
            private_key_path=key_path,
            private_key_password=key_password,
            chain_config=chain_config,
        )
    except requests.exceptions.HTTPError as e:
        rpc_url = os.getenv("MECHX_CHAIN_RPC", "default")
        raise ClickException(
            f"RPC endpoint error: {e}\n\n"
            f"Current RPC: {rpc_url}\n\n"
            f"Possible solutions:\n"
            f"  1. Check if the RPC endpoint is available and accessible\n"
            f"  2. Set a different RPC endpoint: export MECHX_CHAIN_RPC='https://your-rpc-url'"
        ) from e
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
        rpc_url = os.getenv("MECHX_CHAIN_RPC", "default")
        raise ClickException(
            f"Network error connecting to RPC endpoint: {e}\n\n"
            f"Current RPC: {rpc_url}\n\n"
            f"Possible solutions:\n"
            f"  1. Check your internet connection\n"
            f"  2. Verify the RPC URL is correct\n"
            f"  3. Try a different RPC provider: export MECHX_CHAIN_RPC='https://your-rpc-url'"
        ) from e


@click.command(name="fetch-mm-mechs-info")
@click.option(
    "--chain-config",
    type=str,
    help="Id of the mech's chain configuration (stored configs/mechs.json)",
)
def query_mm_mechs_info_cli(
    chain_config: str,
) -> None:
    """Fetches info of mm mechs"""
    try:
        mech_list = query_mm_mechs_info(chain_config=chain_config)
        if mech_list is None:
            print("No mechs found")
            return None

        headers = [
            "Service Id",
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
            for items in mech_list
        ]

        click.echo(tabulate(data, headers=headers, tablefmt="grid"))
        return None
    except requests.exceptions.HTTPError as e:
        subgraph_url = os.getenv("MECHX_SUBGRAPH_URL", "default")
        raise ClickException(
            f"Subgraph endpoint error: {e}\n\n"
            f"Current subgraph URL: {subgraph_url}\n\n"
            f"Possible solutions:\n"
            f"  1. Check if the subgraph endpoint is available and accessible\n"
            f"  2. Set a different subgraph URL: export MECHX_SUBGRAPH_URL='https://your-subgraph-url'\n"
            f"  3. Check your network connection"
        ) from e
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
        subgraph_url = os.getenv("MECHX_SUBGRAPH_URL", "default")
        raise ClickException(
            f"Network error connecting to subgraph endpoint: {e}\n\n"
            f"Current subgraph URL: {subgraph_url}\n\n"
            f"Possible solutions:\n"
            f"  1. Check your internet connection\n"
            f"  2. Verify the subgraph URL is correct\n"
            f"  3. Try a different subgraph provider: export MECHX_SUBGRAPH_URL='https://your-subgraph-url'"
        ) from e
    except Exception as e:  # pylint: disable=broad-except
        click.echo(f"Error: {str(e)}")
        return None


cli.add_command(setup_agent_mode)
cli.add_command(interact)
cli.add_command(prompt_to_ipfs)
cli.add_command(push_to_ipfs)
cli.add_command(to_png)
cli.add_command(tools_for_agents)
cli.add_command(tools_for_marketplace_mech)
cli.add_command(tool_io_schema)
cli.add_command(tool_io_schema_for_marketplace_mech)
cli.add_command(tool_description)
cli.add_command(tool_description_for_marketplace_mech)
cli.add_command(deposit_native)
cli.add_command(deposit_token)
cli.add_command(nvm_subscribe)
cli.add_command(query_mm_mechs_info_cli)


if __name__ == "__main__":
    cli()  # pylint: disable=no-value-for-parameter
