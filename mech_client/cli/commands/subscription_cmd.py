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

"""Subscription command for managing Nevermined (NVM) subscriptions."""

from typing import Optional

import click
from click import ClickException

from mech_client.cli.common import common_wallet_options, setup_wallet_command
from mech_client.cli.validators import validate_chain_config
from mech_client.services.subscription_service import SubscriptionService
from mech_client.utils.errors.handlers import handle_cli_errors


@click.group()
def subscription() -> None:
    """Manage Nevermined (NVM) subscriptions.

    Commands for purchasing and managing NVM subscriptions for
    subscription-based mech access. NVM subscriptions provide access to mechs
    without per-request payments. Currently supported on Gnosis and Base
    chains.
    """


@subscription.command(name="purchase")
@common_wallet_options
@click.pass_context
@handle_cli_errors
def subscription_purchase(  # pylint: disable=too-many-statements,too-many-locals
    ctx: click.Context,
    chain_config: str,
    key: Optional[str] = None,
) -> None:
    """Purchase a Nevermined (NVM) subscription.

    Purchases an NVM subscription for access to subscription-based mechs.
    NVM subscriptions enable requests without per-transaction payments.
    Only available on Gnosis and Base chains.

    Example: mechx subscription purchase --chain-config gnosis
    """
    # Validate chain config
    validated_chain = validate_chain_config(chain_config)

    # Validate chain supports NVM subscriptions
    supported_chains = {"gnosis", "base"}
    if validated_chain not in supported_chains:
        available = ", ".join(sorted(supported_chains))
        raise ClickException(
            f"NVM subscriptions not available for chain: "
            f"{validated_chain!r}\n\n"
            f"Available chains: {available}\n\n"
            f"NVM (Nevermined) subscriptions are only supported on "
            f"select chains."
        )

    # Setup wallet command (agent mode detection, key loading, etc.)
    wallet_ctx = setup_wallet_command(ctx, validated_chain, key)

    # Create subscription service
    service = SubscriptionService(
        chain_config=validated_chain,
        crypto=wallet_ctx.crypto,
        agent_mode=wallet_ctx.agent_mode,
        ethereum_client=wallet_ctx.ethereum_client,
        safe_address=wallet_ctx.safe_address,
    )

    # Execute subscription purchase
    result = service.purchase_subscription()

    # Display result
    click.echo("\n" + "=" * 70)
    click.echo("✓ NVM Subscription Purchased Successfully")
    click.echo("=" * 70)
    click.echo(f"Agreement ID: {result['agreement_id']}")
    click.echo(f"Agreement Transaction: {result['agreement_tx_hash']}")
    click.echo(f"Fulfillment Transaction: {result['fulfillment_tx_hash']}")
    click.echo(f"Credits Before: {result['credits_before']}")
    click.echo(f"Credits After: {result['credits_after']}")
    click.echo(f"Credits Gained: {result['credits_after'] - result['credits_before']}")
    click.echo("=" * 70)
