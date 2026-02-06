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
from eth_utils import is_address
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
from web3.constants import ADDRESS_ZERO
from web3.exceptions import ContractLogicError, Web3ValidationError

from mech_client import __version__
from mech_client.deposits import deposit_native_main, deposit_token_main
from mech_client.interact import get_mech_config
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
from mech_client.nvm_subscription import nvm_subscribe_main
from mech_client.prompt_to_ipfs import main as prompt_to_ipfs_main
from mech_client.push_to_ipfs import main as push_to_ipfs_main
from mech_client.to_png import main as to_png_main


CURR_DIR = Path(__file__).resolve().parent
OPERATE_FOLDER_NAME = ".operate_mech_client"
SETUP_MODE_COMMAND = "setup-agent-mode"
DEFAULT_NETWORK = "gnosis"

CHAIN_TO_TEMPLATE = {
    "gnosis": CURR_DIR / "config" / "mech_client_gnosis.json",
    "base": CURR_DIR / "config" / "mech_client_base.json",
    "polygon": CURR_DIR / "config" / "mech_client_polygon.json",
    "optimism": CURR_DIR / "config" / "mech_client_optimism.json",
}

ENV_PATH = Path.home() / OPERATE_FOLDER_NAME / ".env"
MECHX_CHAIN_CONFIGS = Path(__file__).parent / "configs" / "mechs.json"


def validate_chain_config(chain_config: Optional[str]) -> str:
    """
    Validate that the chain config exists in mechs.json.

    :param chain_config: Chain configuration name
    :return: Validated chain config name
    :raises ClickException: If chain config is invalid or not found
    """
    if not chain_config:
        raise ClickException(
            "Chain configuration is required.\n"
            "Use --chain-config flag with one of: gnosis, base, polygon, optimism, arbitrum, celo"
        )

    try:
        with open(MECHX_CHAIN_CONFIGS, encoding="utf-8") as f:
            configs = json.load(f)
        if chain_config not in configs:
            available_chains = ", ".join(configs.keys())
            raise ClickException(
                f"Invalid chain configuration: {chain_config!r}\n\n"
                f"Available chains: {available_chains}\n\n"
                f"Example: --chain-config gnosis"
            )
        return chain_config
    except (FileNotFoundError, json.JSONDecodeError) as e:
        raise ClickException(
            f"Error loading chain configurations from {MECHX_CHAIN_CONFIGS}: {e}\n"
            "The mechs.json configuration file may be missing or corrupted."
        ) from e


def validate_ethereum_address(address: str, name: str = "Address") -> str:
    """
    Validate an Ethereum address format.

    :param address: Address to validate
    :param name: Name of the address for error messages
    :return: Validated address
    :raises ClickException: If address is invalid
    """
    if not address or address == ADDRESS_ZERO:
        raise ClickException(
            f"{name} is not set or is zero address.\n"
            f"Please provide a valid Ethereum address."
        )

    if not is_address(address):
        raise ClickException(
            f"Invalid {name}: {address!r}\n"
            f"Please provide a valid Ethereum address (0x...)"
        )

    return address


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
    load_dotenv(dotenv_path=ENV_PATH, override=False)
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


def print_wallet_info_box(
    chain_config: str,
    master_eoa: str,
    master_safe: str,
    agent_eoa: str,
    agent_safe: str,
) -> None:
    """Print wallet information in a nice box format."""
    title = f" Agent Mode Setup Complete ({chain_config.upper()}) "
    wallet_info = [
        ("Master EOA", master_eoa),
        ("Master Safe", master_safe),
        ("Agent EOA", agent_eoa),
        ("Agent Safe", agent_safe),
    ]

    # Calculate dimensions
    label_width = max(len(label) for label, _ in wallet_info)
    box_width = (
        max(label_width + 46, len(title)) + 4
    )  # 46 = addr(42) + ": "(2) + pad(2)
    title_pad = (box_width - len(title) - 2) // 2

    # Build lines
    lines = [
        f"╔{'═' * title_pad}{title}{'═' * (box_width - title_pad - len(title) - 2)}╗"
    ]
    lines.append(f"║{' ' * (box_width - 2)}║")

    for label, address in wallet_info:
        content = f"  {label:<{label_width}} : {address}"
        lines.append(f"║{content}{' ' * (box_width - len(content) - 2)}║")

    lines.append(f"║{' ' * (box_width - 2)}║")
    lines.append(f"╚{'═' * (box_width - 2)}╝")

    click.echo("\n" + "\n".join(lines) + "\n")


def display_setup_wallets(operate: OperateApp, validated_chain: str) -> None:
    """Extract and display wallet information after setup."""
    try:
        # Load master wallet using wallet_manager abstraction
        master_wallet = operate.wallet_manager.load("ethereum")
        master_safe = master_wallet.safes.get(validated_chain, "N/A")
        if master_safe != "N/A":
            master_safe = str(master_safe)

        # Load service using service_manager abstraction
        service_manager = operate.service_manager()
        service_config_id = None
        for service in service_manager.json:
            if service["home_chain"] == validated_chain:
                service_config_id = service["service_config_id"]
                break

        if service_config_id:
            service = service_manager.load(service_config_id)
            agent_eoa = service.agent_addresses[0] if service.agent_addresses else "N/A"
            agent_safe = (
                service.chain_configs[validated_chain].chain_data.multisig
                if validated_chain in service.chain_configs
                else "N/A"
            )

            print_wallet_info_box(
                chain_config=validated_chain,
                master_eoa=master_wallet.address,
                master_safe=master_safe,
                agent_eoa=agent_eoa,
                agent_safe=agent_safe,
            )
        else:
            click.echo("Agent mode setup completed successfully!")
    except Exception as e:  # pylint: disable=broad-except
        click.echo(
            f"Agent mode setup completed successfully! (Could not display wallet info: {e})"
        )


@click.command()
@click.option(
    "--chain-config",
    type=str,
    help="Id of the mech's chain configuration.",
)
def setup_agent_mode(
    chain_config: str,
) -> None:
    """Sets up the agent mode for users"""
    # Validate chain config
    validated_chain = validate_chain_config(chain_config)

    template = CHAIN_TO_TEMPLATE.get(validated_chain)
    if template is None:
        supported_chains = ", ".join(CHAIN_TO_TEMPLATE.keys())
        raise ClickException(
            f"Agent mode not supported for chain: {validated_chain!r}\n\n"
            f"Supported chains: {supported_chains}"
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
    except Exception as e:
        raise ClickException(
            f"Failed to setup agent mode: {e}\n\n"
            f"The service setup process encountered an error.\n\n"
            f"Possible causes:\n"
            f"  • Missing dependencies (Docker, Poetry)\n"
            f"  • Invalid service configuration\n"
            f"  • Permission issues\n"
            f"  • Corrupted operate directory\n\n"
            f"Please check the error message above for details."
        ) from e

    # Extract and display wallet information
    display_setup_wallets(operate, validated_chain)


@click.command()
@click.option(
    "--prompts",
    type=str,
    multiple=True,
    required=True,
    help="One or more prompts to send as a request. Can be repeated.",
)
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
def interact(  # pylint: disable=too-many-arguments,too-many-locals,too-many-statements
    ctx: click.Context,
    prompts: tuple,
    priority_mech: str,
    use_prepaid: bool,
    use_offchain: bool,
    key: Optional[str],
    tools: Optional[tuple],
    safe: Optional[str] = None,
    extra_attribute: Optional[List[str]] = None,
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

        # Validate chain config
        if chain_config:
            chain_config = validate_chain_config(chain_config)

        extra_attributes_dict: Dict[str, Any] = {}
        if extra_attribute:
            for pair in extra_attribute:
                # Validate format before splitting
                if "=" not in pair:
                    raise ClickException(
                        f"Invalid extra attribute format: {pair!r}\n"
                        f"Expected format: key=value"
                    )
                k, v = pair.split("=", 1)  # Split only on first =
                extra_attributes_dict[k] = v

        use_offchain = use_offchain or False
        use_prepaid = use_prepaid or use_offchain

        mech_offchain_url = os.getenv("MECHX_MECH_OFFCHAIN_URL")
        if use_offchain and not mech_offchain_url:
            raise ClickException(
                "Environment variable MECHX_MECH_OFFCHAIN_URL is required when using --use-offchain.\n"
                "Please set it to your offchain mech HTTP endpoint:\n"
                "  export MECHX_MECH_OFFCHAIN_URL='https://your-offchain-mech-url'"
            )

        # Marketplace path - validate inputs
        if not tools:
            raise ClickException(
                "Tools are required. Use --tools flag to specify one or more tools."
            )

        if len(prompts) != len(tools):
            raise ClickException(
                f"The number of prompts ({len(prompts)}) must match the number of tools ({len(tools)})"
            )

        # Validate priority_mech address
        if priority_mech:
            validate_ethereum_address(priority_mech, "Priority mech address")

        if agent_mode:
            safe, key_path, key_password = fetch_agent_mode_data(chain_config)
            if not safe or not key_path:
                raise ClickException(
                    "Cannot fetch safe or key data for the agent mode."
                )
            # Validate safe address
            validate_ethereum_address(safe, "Safe address")

        # safe and mech_offchain_url are guaranteed to be set at this point if needed
        marketplace_interact_(
            prompts=prompts,
            priority_mech=priority_mech,
            agent_mode=agent_mode,
            safe_address=safe or "",  # Will be set if agent_mode is True
            use_prepaid=use_prepaid,
            use_offchain=use_offchain,
            mech_offchain_url=mech_offchain_url or "",  # Checked above if use_offchain
            private_key_path=key_path,
            private_key_password=key_password,
            tools=tools,
            extra_attributes=extra_attributes_dict,
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
    except TimeoutError as e:
        rpc_url_env = os.getenv("MECHX_CHAIN_RPC")
        error_details = str(e)

        msg = (
            "Timeout while waiting for transaction receipt via HTTP RPC endpoint.\n\n"
            f"Error details: {error_details}\n\n"
        )

        if rpc_url_env:
            msg += f"Current MECHX_CHAIN_RPC: {rpc_url_env}\n\n"
        else:
            msg += (
                "Using default RPC endpoint from config (MECHX_CHAIN_RPC not set)\n\n"
            )

        msg += (
            "Possible causes:\n"
            "  • RPC endpoint is slow, rate-limiting, or unavailable\n"
            "  • Network connectivity issues\n"
            "  • RPC endpoint doesn't support the required methods\n\n"
            "Recommended actions:\n"
            "  1. Check if your transaction succeeded on a block explorer\n"
            "  2. Try a reliable RPC provider (e.g., Alchemy, Infura, Ankr, or public RPCs)\n"
            "  3. Set a different HTTP RPC endpoint:\n"
            "     export MECHX_CHAIN_RPC='https://your-http-rpc-url'\n\n"
            "Note: MECHX_CHAIN_RPC is for HTTP RPC endpoints (https://...).\n"
            "      WSS endpoints are configured separately via MECHX_WSS_ENDPOINT (wss://...)."
        )

        raise ClickException(msg) from e
    except (ContractLogicError, Web3ValidationError) as e:
        raise ClickException(
            f"Smart contract error: {e}\n\n"
            f"This may indicate:\n"
            f"  • Invalid contract address or ABI mismatch\n"
            f"  • Insufficient balance or missing approvals\n"
            f"  • Invalid parameters passed to contract function\n"
            f"  • Contract requirements not met (e.g., mech not registered)\n\n"
            f"Please verify your addresses and balances."
        ) from e
    except (ValueError, FileNotFoundError) as e:
        raise ClickException(str(e)) from e
    except Exception as e:
        # Catch-all for unexpected errors - still show full context
        raise ClickException(
            f"Unexpected error: {e}\n\n"
            f"If this persists, please report it as an issue."
        ) from e


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


@click.command(name="tools-for-marketplace-mech")
@click.argument(
    "agent-id",
    type=int,
)
@click.option("--chain-config", default="gnosis", help="Chain configuration to use.")
def tools_for_marketplace_mech(agent_id: int, chain_config: str) -> None:
    """Fetch and display tools for marketplace mechs."""
    try:
        # Validate chain config
        validated_chain = validate_chain_config(chain_config)

        # Validate agent ID (service ID)
        if agent_id < 0:
            raise ClickException(
                f"Invalid service ID: {agent_id}\n"
                f"Service ID must be a non-negative integer."
            )

        result = get_tools_for_marketplace_mech(agent_id, validated_chain)

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
        raise ClickException(
            f"Error processing tool data: {e}\n\n"
            f"Possible causes:\n"
            f"  • Service ID {agent_id} does not exist\n"
            f"  • Metadata structure is invalid or incomplete\n"
            f"  • Complementary metadata hash contract may not be accessible\n\n"
            f"Please verify the service ID."
        ) from e
    except IOError as e:
        raise ClickException(
            f"I/O error accessing tool metadata: {e}\n\n"
            f"This may indicate:\n"
            f"  • IPFS gateway is unavailable\n"
            f"  • Network connectivity issues"
        ) from e
    except (ContractLogicError, Web3ValidationError) as e:
        raise ClickException(
            f"Smart contract error: {e}\n\n"
            f"This may indicate:\n"
            f"  • Complementary metadata hash contract address is invalid\n"
            f"  • Contract ABI mismatch\n"
            f"  • Service ID out of range\n\n"
            f"Please verify your chain configuration."
        ) from e


@click.command(name="tool-description-for-marketplace-mech")
@click.argument("tool_id")
@click.option("--chain-config", default="gnosis", help="Chain configuration to use.")
def tool_description_for_marketplace_mech(tool_id: str, chain_config: str) -> None:
    """Fetch and display the description of a specific tool for marketplace mechs."""
    try:
        # Validate chain config
        validated_chain = validate_chain_config(chain_config)

        # Validate tool_id format
        if "-" not in tool_id:
            raise ClickException(
                f"Invalid tool ID format: {tool_id!r}\n\n"
                f"Expected format: service_id-tool_name\n"
                f"Example: 1-openai-gpt-3.5-turbo"
            )

        description = get_tool_description_for_marketplace_mech(
            tool_id, validated_chain
        )
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
        raise ClickException(
            f"Tool not found or missing description: {e}\n\n"
            f"The tool {tool_id!r} may not exist or its metadata may be incomplete.\n\n"
            f"Possible causes:\n"
            f"  • Tool ID is incorrect\n"
            f"  • Service does not have this tool\n"
            f"  • Tool metadata is missing description field\n\n"
            f"Use 'mechx tools-for-marketplace-mech --agent-id <service_id>' to see available tools."
        ) from e
    except IOError as e:
        raise ClickException(
            f"Network or I/O error: {e}\n\n"
            f"Failed to fetch tool data from IPFS or contract.\n\n"
            f"Possible solutions:\n"
            f"  1. Check your internet connection\n"
            f"  2. Verify the RPC endpoint is accessible\n"
            f"  3. Try again in a few moments"
        ) from e


@click.command(name="tool-io-schema-for-marketplace-mech")
@click.argument("tool_id")
@click.option("--chain-config", default="gnosis", help="Chain configuration to use.")
def tool_io_schema_for_marketplace_mech(tool_id: str, chain_config: str) -> None:
    """Fetch and display the tool's name and description along with the input/output schema for a specific tool for marketplace mechs."""
    try:
        # Validate chain config
        validated_chain = validate_chain_config(chain_config)

        # Validate tool_id format
        if "-" not in tool_id:
            raise ClickException(
                f"Invalid tool ID format: {tool_id!r}\n\n"
                f"Expected format: service_id-tool_name\n"
                f"Example: 1-openai-gpt-3.5-turbo"
            )

        result = get_tool_io_schema_for_marketplace_mech(tool_id, validated_chain)

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
        raise ClickException(
            f"Error accessing schema data: {e}\n\n"
            f"The tool {tool_id!r} may not exist or its schema may be incomplete.\n\n"
            f"Possible causes:\n"
            f"  • Tool ID is incorrect\n"
            f"  • Service does not have this tool\n"
            f"  • Tool metadata is missing input/output schema fields\n\n"
            f"Use 'mechx tools-for-marketplace-mech --agent-id <service_id>' to see available tools."
        ) from e
    except IOError as e:
        raise ClickException(
            f"Network or I/O error: {e}\n\n"
            f"Failed to fetch tool data from IPFS or contract.\n\n"
            f"Possible solutions:\n"
            f"  1. Check your internet connection\n"
            f"  2. Verify the RPC endpoint is accessible\n"
            f"  3. Try again in a few moments"
        ) from e


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
        # Validate chain config
        validated_chain = validate_chain_config(chain_config)

        # Validate amount
        try:
            amount_wei = int(amount_to_deposit)
            if amount_wei <= 0:
                raise ValueError
        except (ValueError, TypeError) as e:
            raise ClickException(
                f"Invalid amount: {amount_to_deposit!r}\n\n"
                f"Amount must be a positive integer in wei.\n\n"
                f"Example: 1000000000000000000 (1 token with 18 decimals)"
            ) from e

        # Validate chain supports marketplace deposits
        mech_config = get_mech_config(validated_chain)
        if mech_config.mech_marketplace_contract == ADDRESS_ZERO:
            raise ClickException(
                f"Chain {validated_chain!r} does not support marketplace deposits.\n\n"
                f"Marketplace contract is not deployed on this chain.\n\n"
                f"Supported chains: gnosis, base, polygon, optimism"
            )

        agent_mode = is_agent_mode(ctx)
        click.echo(f"Running deposit native with agent_mode={agent_mode}")

        key_path: Optional[str] = key
        key_password: Optional[str] = None
        if agent_mode:
            safe, key_path, key_password = fetch_agent_mode_data(validated_chain)
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
            chain_config=validated_chain,
        )
    except ContractLogicError as e:
        raise ClickException(
            f"Smart contract error during deposit: {e}\n\n"
            f"Possible causes:\n"
            f"  • Insufficient balance in your account\n"
            f"  • Transaction parameters are invalid\n"
            f"  • Contract may be paused or unavailable\n\n"
            f"Please check your balance and transaction parameters."
        ) from e
    except Web3ValidationError as e:
        raise ClickException(
            f"Transaction validation error: {e}\n\n"
            f"The transaction failed validation before being sent.\n\n"
            f"Possible causes:\n"
            f"  • Invalid amount or address format\n"
            f"  • Gas estimation failed\n"
            f"  • Nonce issues\n\n"
            f"Please verify your inputs and try again."
        ) from e
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
        # Validate chain config
        validated_chain = validate_chain_config(chain_config)

        # Validate amount
        try:
            amount_wei = int(amount_to_deposit)
            if amount_wei <= 0:
                raise ValueError
        except (ValueError, TypeError) as e:
            raise ClickException(
                f"Invalid amount: {amount_to_deposit!r}\n\n"
                f"Amount must be a positive integer in token's smallest unit.\n\n"
                f"Example: 1000000 (1 USDC with 6 decimals)"
            ) from e

        # Validate chain supports marketplace deposits
        mech_config = get_mech_config(validated_chain)
        if mech_config.mech_marketplace_contract == ADDRESS_ZERO:
            raise ClickException(
                f"Chain {validated_chain!r} does not support marketplace deposits.\n\n"
                f"Marketplace contract is not deployed on this chain.\n\n"
                f"Supported chains: gnosis, base, polygon, optimism"
            )

        agent_mode = is_agent_mode(ctx)
        click.echo(f"Running deposit token with agent_mode={agent_mode}")

        key_path: Optional[str] = key
        key_password: Optional[str] = None
        if agent_mode:
            safe, key_path, key_password = fetch_agent_mode_data(validated_chain)
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
            chain_config=validated_chain,
        )
    except ContractLogicError as e:
        raise ClickException(
            f"Smart contract error during token deposit: {e}\n\n"
            f"Possible causes:\n"
            f"  • Insufficient token balance in your account\n"
            f"  • Token allowance not approved\n"
            f"  • Transaction parameters are invalid\n"
            f"  • Contract may be paused or unavailable\n\n"
            f"Please check your token balance, approve allowance, and verify parameters."
        ) from e
    except Web3ValidationError as e:
        raise ClickException(
            f"Transaction validation error: {e}\n\n"
            f"The transaction failed validation before being sent.\n\n"
            f"Possible causes:\n"
            f"  • Invalid amount or address format\n"
            f"  • Gas estimation failed\n"
            f"  • Nonce issues\n\n"
            f"Please verify your inputs and try again."
        ) from e
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
        # Validate chain config
        validated_chain = validate_chain_config(chain_config)

        # Validate chain supports NVM subscriptions
        # Import here to avoid circular import and get the actual dict
        from mech_client.nvm_subscription import (  # pylint: disable=import-outside-toplevel
            CHAIN_TO_ENVS,
        )

        if validated_chain not in CHAIN_TO_ENVS:
            available_chains = ", ".join(CHAIN_TO_ENVS.keys())
            raise ClickException(
                f"NVM subscriptions not available for chain: {validated_chain!r}\n\n"
                f"Available chains: {available_chains}\n\n"
                f"NVM (Nevermined) subscriptions are only supported on select chains."
            )

        agent_mode = is_agent_mode(ctx)
        click.echo(f"Running purchase nvm subscription with agent_mode={agent_mode}")

        key_path: Optional[str] = key
        key_password: Optional[str] = None
        if agent_mode:
            safe, key_path, key_password = fetch_agent_mode_data(validated_chain)
            if not safe or not key_path:
                raise ClickException(
                    "Cannot fetch safe or key data for the agent mode."
                )

        if not key_path:
            raise ClickException(
                "Private key path is required. Use --key option or set up agent mode."
            )

        nvm_subscribe_main(
            agent_mode=agent_mode,
            safe_address=safe,
            private_key_path=key_path,
            private_key_password=key_password,
            chain_config=validated_chain,
        )
    except ContractLogicError as e:
        raise ClickException(
            f"Smart contract error during NVM subscription: {e}\n\n"
            f"Possible causes:\n"
            f"  • Insufficient balance for subscription fee\n"
            f"  • Invalid subscription plan DID\n"
            f"  • Subscription contract may be unavailable\n\n"
            f"Please check your balance and subscription plan configuration."
        ) from e
    except Web3ValidationError as e:
        raise ClickException(
            f"Transaction validation error: {e}\n\n"
            f"The subscription transaction failed validation.\n\n"
            f"Possible causes:\n"
            f"  • Invalid subscription parameters\n"
            f"  • Gas estimation failed\n"
            f"  • Nonce issues\n\n"
            f"Please verify your inputs and try again."
        ) from e
    except KeyError as e:
        raise ClickException(
            f"Missing required environment variable: {e}\n\n"
            f"NVM subscription requires environment variables from chain-specific .env file.\n\n"
            f"Required variables: PLAN_DID, NETWORK_NAME, CHAIN_ID\n\n"
            f"Please ensure the .env file for {validated_chain} exists and contains all required variables."
        ) from e
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
        # Validate chain config
        validated_chain = validate_chain_config(chain_config)

        # Validate MECHX_SUBGRAPH_URL is set before calling query function
        subgraph_url = os.getenv("MECHX_SUBGRAPH_URL")
        if not subgraph_url:
            raise ClickException(
                "Environment variable MECHX_SUBGRAPH_URL is required for this command.\n\n"
                f"This command queries blockchain data via a subgraph API.\n"
                f"Current chain: {validated_chain}\n\n"
                f"Please set the subgraph URL:\n"
                f"  export MECHX_SUBGRAPH_URL='https://your-subgraph-url'\n\n"
                f"Note: The subgraph URL must match your --chain-config."
            )

        mech_list = query_mm_mechs_info(chain_config=validated_chain)
        if mech_list is None:
            print("No mechs found")
            return None

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
        raise ClickException(
            f"Error querying subgraph: {e}\n\n"
            f"Please check your MECHX_SUBGRAPH_URL and network connection."
        ) from e


cli.add_command(setup_agent_mode)
cli.add_command(interact)
cli.add_command(prompt_to_ipfs)
cli.add_command(push_to_ipfs)
cli.add_command(to_png)
cli.add_command(tools_for_marketplace_mech)
cli.add_command(tool_io_schema_for_marketplace_mech)
cli.add_command(tool_description_for_marketplace_mech)
cli.add_command(deposit_native)
cli.add_command(deposit_token)
cli.add_command(nvm_subscribe)
cli.add_command(query_mm_mechs_info_cli)


if __name__ == "__main__":
    cli()  # pylint: disable=no-value-for-parameter
