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

from typing import Optional

import click
from click import ClickException
from web3.constants import ADDRESS_ZERO

from mech_client.cli.common import common_wallet_options, setup_wallet_command
from mech_client.cli.validators import validate_amount, validate_chain_config
from mech_client.infrastructure.config import get_mech_config
from mech_client.services.deposit_service import DepositService
from mech_client.utils.errors.handlers import handle_cli_errors


@click.group()
def deposit() -> None:
    """Manage prepaid balance deposits.

    Commands for depositing native tokens or ERC20 tokens into your prepaid
    balance on the marketplace. Prepaid balances can be used for marketplace
    requests without per-request approval transactions.
    """


@deposit.command(name="native")
@click.argument("amount_to_deposit", metavar="<amount>")
@common_wallet_options
@click.pass_context
@handle_cli_errors
# pylint: disable=too-many-locals,too-many-statements
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

    # Setup wallet command (agent mode detection, key loading, etc.)
    wallet_ctx = setup_wallet_command(ctx, validated_chain, key)

    # Create deposit service
    service = DepositService(
        chain_config=validated_chain,
        agent_mode=wallet_ctx.agent_mode,
        crypto=wallet_ctx.crypto,
        safe_address=wallet_ctx.safe_address,
        ethereum_client=wallet_ctx.ethereum_client,
    )

    # Execute deposit
    amount_int = int(amount_to_deposit)
    click.echo(f"\nDepositing {amount_int} wei of native tokens...")
    tx_hash = service.deposit_native(amount_int)
    click.echo(f"\n✓ Deposit transaction: {tx_hash}")


@deposit.command(name="token")
@click.argument("amount_to_deposit", metavar="<amount>")
@click.option(
    "--token-type",
    type=click.Choice(["olas", "usdc"], case_sensitive=False),
    default="olas",
    help="Token type to deposit (olas or usdc). Default: olas.",
)
@common_wallet_options
@click.pass_context
@handle_cli_errors
# pylint: disable=too-many-locals,too-many-statements
def deposit_token(
    ctx: click.Context,
    amount_to_deposit: str,
    chain_config: str,
    token_type: str,
    key: Optional[str] = None,
) -> None:
    """Deposit ERC20 tokens into prepaid balance.

    Deposits ERC20 tokens (OLAS, USDC) into your prepaid balance on the
    marketplace. Amount must be specified in the token's smallest unit
    (e.g., 18 decimals for OLAS, 6 decimals for USDC).

    Examples:
        mechx deposit token 1000000000000000000 --chain-config gnosis --token-type olas
        (deposits 1.0 OLAS)

        mechx deposit token 1000000 --chain-config base --token-type usdc
        (deposits 1.0 USDC)
    """
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

    # Setup wallet command (agent mode detection, key loading, etc.)
    wallet_ctx = setup_wallet_command(ctx, validated_chain, key)

    # Create deposit service
    service = DepositService(
        chain_config=validated_chain,
        agent_mode=wallet_ctx.agent_mode,
        crypto=wallet_ctx.crypto,
        safe_address=wallet_ctx.safe_address,
        ethereum_client=wallet_ctx.ethereum_client,
    )

    # Execute deposit
    amount_int = int(amount_to_deposit)
    click.echo(f"\nDepositing {amount_int} of {token_type.upper()} tokens...")
    tx_hash = service.deposit_token(amount_int, token_type=token_type.lower())
    click.echo(f"\n✓ Deposit transaction: {tx_hash}")
