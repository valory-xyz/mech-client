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

"""Deposit command for managing prepaid balance deposits."""

import os
from typing import Optional

import click
import requests
from click import ClickException
from web3.constants import ADDRESS_ZERO
from web3.exceptions import ContractLogicError, Web3ValidationError

from mech_client.cli.commands.request_cmd import fetch_agent_mode_data
from mech_client.cli.validators import validate_amount, validate_chain_config
from mech_client.deposits import deposit_native_main, deposit_token_main
from mech_client.interact import get_mech_config


@click.group()
def deposit() -> None:
    """Manage prepaid balance deposits.

    Commands for depositing native tokens or ERC20 tokens into your prepaid
    balance on the marketplace. Prepaid balances can be used for marketplace
    requests without per-request approval transactions.
    """


@deposit.command(name="native")
@click.argument("amount_to_deposit", metavar="<amount>")
@click.option(
    "--chain-config",
    type=str,
    required=True,
    help="Chain configuration name (gnosis, base, polygon, optimism).",
)
@click.option(
    "--key",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    help="Path to private key file (client mode only).",
)
@click.pass_context
def deposit_native(
    ctx: click.Context,
    amount_to_deposit: str,
    chain_config: str,
    key: Optional[str] = None,
) -> None:
    """Deposit native tokens into prepaid balance.

    Deposits native blockchain tokens (xDAI on Gnosis, ETH on Base, MATIC on
    Polygon, etc.) into your prepaid balance on the marketplace. Amount must
    be specified in wei (smallest unit, 18 decimals for most chains).

    Example: mechx deposit native 1000000000000000000 --chain-config gnosis
    (deposits 1.0 xDAI)
    """
    try:
        # Validate chain config
        validated_chain = validate_chain_config(chain_config)

        # Validate amount
        validate_amount(amount_to_deposit, "Amount")

        # Validate chain supports marketplace deposits
        mech_config = get_mech_config(validated_chain)
        if mech_config.mech_marketplace_contract == ADDRESS_ZERO:
            raise ClickException(
                f"Chain {validated_chain!r} does not support marketplace "
                f"deposits.\n\n"
                f"Marketplace contract is not deployed on this chain.\n\n"
                f"Supported chains: gnosis, base, polygon, optimism"
            )

        # Extract agent mode
        agent_mode = not ctx.obj.get("client_mode", False)
        click.echo(f"Running deposit native with agent_mode={agent_mode}")

        # Fetch agent mode data if needed
        key_path: Optional[str] = key
        key_password: Optional[str] = None
        safe: Optional[str] = None

        if agent_mode:
            safe, key_path, key_password = fetch_agent_mode_data(validated_chain)
            if not safe or not key_path:
                raise ClickException("Cannot fetch safe or key data for agent mode.")

        # Execute deposit
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
            f"  1. Check if the RPC endpoint is available\n"
            f"  2. Set a different RPC: "
            f"export MECHX_CHAIN_RPC='https://your-rpc-url'"
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


@deposit.command(name="token")
@click.argument("amount_to_deposit", metavar="<amount>")
@click.option(
    "--chain-config",
    type=str,
    required=True,
    help="Chain configuration name (gnosis, base, polygon, optimism).",
)
@click.option(
    "--key",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    help="Path to private key file (client mode only).",
)
@click.pass_context
def deposit_token(
    ctx: click.Context,
    amount_to_deposit: str,
    chain_config: str,
    key: Optional[str] = None,
) -> None:
    """Deposit ERC20 tokens into prepaid balance.

    Deposits ERC20 tokens (OLAS, USDC) into your prepaid balance on the
    marketplace. Amount must be specified in the token's smallest unit
    (e.g., 18 decimals for OLAS, 6 decimals for USDC).

    Example: mechx deposit token 1000000000000000000 --chain-config gnosis
    (deposits 1.0 OLAS)
    """
    try:
        # Validate chain config
        validated_chain = validate_chain_config(chain_config)

        # Validate amount
        validate_amount(amount_to_deposit, "Amount")

        # Validate chain supports marketplace deposits
        mech_config = get_mech_config(validated_chain)
        if mech_config.mech_marketplace_contract == ADDRESS_ZERO:
            raise ClickException(
                f"Chain {validated_chain!r} does not support marketplace "
                f"deposits.\n\n"
                f"Marketplace contract is not deployed on this chain.\n\n"
                f"Supported chains: gnosis, base, polygon, optimism"
            )

        # Extract agent mode
        agent_mode = not ctx.obj.get("client_mode", False)
        click.echo(f"Running deposit token with agent_mode={agent_mode}")

        # Fetch agent mode data if needed
        key_path: Optional[str] = key
        key_password: Optional[str] = None
        safe: Optional[str] = None

        if agent_mode:
            safe, key_path, key_password = fetch_agent_mode_data(validated_chain)
            if not safe or not key_path:
                raise ClickException("Cannot fetch safe or key data for agent mode.")

        # Execute deposit
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
            f"Please check your token balance, approve allowance, and "
            f"verify parameters."
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
            f"  1. Check if the RPC endpoint is available\n"
            f"  2. Set a different RPC: "
            f"export MECHX_CHAIN_RPC='https://your-rpc-url'"
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
