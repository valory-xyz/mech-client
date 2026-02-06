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

"""Request command for sending AI task requests to mechs."""

import os
from typing import Any, Dict, List, Optional

import click
import requests
from click import ClickException
from web3.exceptions import ContractLogicError, Web3ValidationError

from mech_client.cli.validators import validate_chain_config, validate_ethereum_address
from mech_client.marketplace_interact import (
    marketplace_interact as marketplace_interact_,
)


def fetch_agent_mode_data(chain_config: str) -> tuple:
    """
    Fetch agent mode data (safe address, key path, key password).

    :param chain_config: Chain configuration name
    :return: Tuple of (safe_address, key_path, key_password)
    :raises ClickException: If agent mode data cannot be fetched
    """
    # Import here to avoid circular imports
    # pylint: disable=import-outside-toplevel
    from pathlib import Path

    from dotenv import load_dotenv
    from operate.cli import OperateApp

    operate_folder_name = ".operate_mech_client"
    env_path = Path.home() / operate_folder_name / ".env"
    load_dotenv(dotenv_path=env_path, override=False)

    operate = OperateApp()
    operate.setup()

    # Get password
    env_password = os.getenv("OPERATE_PASSWORD")
    if not env_password:
        raise ClickException(
            "OPERATE_PASSWORD not found in environment.\n"
            "Please run setup command first or set OPERATE_PASSWORD in .env"
        )
    operate.password = env_password

    # Load service
    services = operate.service_manager().load_or_create()
    if not services:
        raise ClickException(
            "No services found in agent mode.\n" "Please run setup command first."
        )

    service = services[0]
    if service.chain_configs.get(chain_config) is None:
        raise ClickException(
            f"Service not configured for chain: {chain_config}\n"
            f"Please run setup command for this chain."
        )

    # Get safe address
    safe_address = service.chain_configs[chain_config].chain_data.multisig

    # Get key path
    keys_manager = operate.service_manager().get_keys_manager_for_service(service)
    key_path = keys_manager.ledger_key_path

    key_password = operate.password

    return safe_address, str(key_path), key_password


@click.command()
@click.option(
    "--prompts",
    type=str,
    multiple=True,
    required=True,
    help="One or more prompts to send as AI task requests.",
)
@click.option(
    "--priority-mech",
    type=str,
    help="Priority mech address to use for the request (0x...).",
)
@click.option(
    "--use-prepaid",
    type=bool,
    help="Use prepaid balance instead of per-request payment.",
)
@click.option(
    "--use-offchain",
    type=bool,
    help="Use offchain mech (requires MECHX_MECH_OFFCHAIN_URL).",
)
@click.option(
    "--key",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    help="Path to private key file (client mode only).",
)
@click.option(
    "--tools",
    type=str,
    multiple=True,
    help="One or more tool identifiers (must match number of prompts).",
)
@click.option(
    "--extra-attribute",
    type=str,
    multiple=True,
    help="Extra attribute (key=value) to be included in request metadata.",
    metavar="KEY=VALUE",
)
@click.option(
    "--retries",
    type=int,
    help="Number of retries for sending a transaction.",
)
@click.option(
    "--timeout",
    type=float,
    help="Timeout in seconds to wait for the transaction.",
)
@click.option(
    "--sleep",
    type=float,
    help="Sleep duration in seconds before retrying the transaction.",
)
@click.option(
    "--chain-config",
    type=str,
    required=True,
    help="Chain configuration name (gnosis, base, polygon, optimism).",
)
@click.pass_context
def request(  # pylint: disable=too-many-arguments,too-many-locals
    ctx: click.Context,
    prompts: tuple,
    priority_mech: str,
    chain_config: str,
    use_prepaid: bool,
    use_offchain: bool,
    key: Optional[str],
    tools: Optional[tuple],
    extra_attribute: Optional[List[str]] = None,
    retries: Optional[int] = None,
    timeout: Optional[float] = None,
    sleep: Optional[float] = None,
) -> None:
    r"""Send an AI task request to a mech on-chain.

    Sends one or more prompts to AI mechs via the Mech Marketplace contract.
    Supports batch requests (multiple prompts/tools), various payment methods
    (native, token, prepaid, NVM subscription), and both on-chain and
    off-chain delivery.

    Examples:
      # Single request with native payment
      mechx request --prompts "Summarize this" --tools openai-gpt-4 \
        --chain-config gnosis

      # Batch request with prepaid balance
      mechx request --prompts "Prompt 1" --prompts "Prompt 2" \
        --tools tool1 --tools tool2 --use-prepaid --chain-config gnosis
    """
    try:
        # Extract agent mode from context
        agent_mode = not ctx.obj.get("client_mode", False)
        click.echo(f"Running request with agent_mode={agent_mode}")

        # Validate chain config
        validated_chain = validate_chain_config(chain_config)

        # Parse extra attributes
        extra_attributes_dict: Dict[str, Any] = {}
        if extra_attribute:
            for pair in extra_attribute:
                if "=" not in pair:
                    raise ClickException(
                        f"Invalid extra attribute format: {pair!r}\n"
                        f"Expected format: key=value"
                    )
                k, v = pair.split("=", 1)
                extra_attributes_dict[k] = v

        # Process flags
        use_offchain = use_offchain or False
        use_prepaid = use_prepaid or use_offchain

        # Validate offchain URL if needed
        mech_offchain_url = os.getenv("MECHX_MECH_OFFCHAIN_URL")
        if use_offchain and not mech_offchain_url:
            raise ClickException(
                "MECHX_MECH_OFFCHAIN_URL is required when using "
                "--use-offchain.\n"
                "Set it to your offchain mech HTTP endpoint:\n"
                "  export MECHX_MECH_OFFCHAIN_URL='https://your-url'"
            )

        # Validate tools
        if not tools:
            raise ClickException(
                "Tools are required. Use --tools flag to specify one or " "more tools."
            )

        if len(prompts) != len(tools):
            raise ClickException(
                f"The number of prompts ({len(prompts)}) must match the "
                f"number of tools ({len(tools)})"
            )

        # Validate priority_mech address
        if priority_mech:
            validate_ethereum_address(priority_mech, "Priority mech address")

        # Fetch agent mode data if needed
        key_path: Optional[str] = key
        key_password: Optional[str] = None
        safe: Optional[str] = None

        if agent_mode:
            safe, key_path, key_password = fetch_agent_mode_data(validated_chain)
            if not safe or not key_path:
                raise ClickException("Cannot fetch safe or key data for agent mode.")
            validate_ethereum_address(safe, "Safe address")

        # Call marketplace interact (using legacy function for now)
        marketplace_interact_(
            prompts=prompts,
            priority_mech=priority_mech,
            agent_mode=agent_mode,
            safe_address=safe or "",
            chain_config=validated_chain,
            use_prepaid=use_prepaid,
            use_offchain=use_offchain,
            mech_offchain_url=mech_offchain_url or "",
            private_key_path=key_path,
            private_key_password=key_password,
            tools=tools,
            extra_attributes=extra_attributes_dict,
            retries=retries,
            timeout=timeout,
            sleep=sleep,
        )

    except requests.exceptions.HTTPError as e:
        rpc_url = os.getenv("MECHX_CHAIN_RPC", "default")
        raise ClickException(
            f"RPC endpoint error: {e}\n\n"
            f"Current RPC: {rpc_url}\n\n"
            f"Possible solutions:\n"
            f"  1. Check if the RPC endpoint is available\n"
            f"  2. Set a different RPC: "
            f"export MECHX_CHAIN_RPC='https://your-rpc-url'\n"
            f"  3. Check your network connection"
        ) from e
    except (
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
    ) as e:
        rpc_url = os.getenv("MECHX_CHAIN_RPC", "default")
        raise ClickException(
            f"Network error connecting to RPC: {e}\n\n"
            f"Current RPC: {rpc_url}\n\n"
            f"Possible solutions:\n"
            f"  1. Check your internet connection\n"
            f"  2. Verify the RPC URL is correct\n"
            f"  3. Try a different RPC provider: "
            f"export MECHX_CHAIN_RPC='https://your-rpc-url'"
        ) from e
    except TimeoutError as e:
        rpc_url_env = os.getenv("MECHX_CHAIN_RPC")
        error_details = str(e)

        msg = (
            "Timeout while waiting for transaction receipt via HTTP RPC.\n\n"
            f"Error details: {error_details}\n\n"
        )

        if rpc_url_env:
            msg += f"Current MECHX_CHAIN_RPC: {rpc_url_env}\n\n"
        else:
            msg += "Using default RPC endpoint from config\n\n"

        msg += (
            "Possible causes:\n"
            "  • RPC endpoint is slow, rate-limiting, or unavailable\n"
            "  • Network connectivity issues\n\n"
            "Recommended actions:\n"
            "  1. Check if your transaction succeeded on a block explorer\n"
            "  2. Try a reliable RPC provider (Alchemy, Infura, Ankr)\n"
            "  3. Set a different HTTP RPC endpoint:\n"
            "     export MECHX_CHAIN_RPC='https://your-http-rpc-url'"
        )

        raise ClickException(msg) from e
    except (ContractLogicError, Web3ValidationError) as e:
        raise ClickException(
            f"Smart contract error: {e}\n\n"
            f"This may indicate:\n"
            f"  • Insufficient balance or missing approvals\n"
            f"  • Invalid parameters passed to contract\n"
            f"  • Contract requirements not met\n\n"
            f"Please verify your addresses and balances."
        ) from e
    except (ValueError, FileNotFoundError) as e:
        raise ClickException(str(e)) from e
    except Exception as e:
        raise ClickException(
            f"Unexpected error: {e}\n\n"
            f"If this persists, please report it as an issue."
        ) from e
