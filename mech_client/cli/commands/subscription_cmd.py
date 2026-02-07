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

import os
from typing import Optional

import click
import requests
from aea_ledger_ethereum import EthereumApi, EthereumCrypto
from click import ClickException
from safe_eth.eth import EthereumClient
from web3.exceptions import ContractLogicError, Web3ValidationError

from mech_client.cli.validators import validate_chain_config
from mech_client.infrastructure.config import get_mech_config
from mech_client.infrastructure.operate.key_manager import fetch_agent_mode_keys
from mech_client.services.subscription_service import SubscriptionService


@click.group()
def subscription() -> None:
    """Manage Nevermined (NVM) subscriptions.

    Commands for purchasing and managing NVM subscriptions for
    subscription-based mech access. NVM subscriptions provide access to mechs
    without per-request payments. Currently supported on Gnosis and Base
    chains.
    """


@subscription.command(name="purchase")
@click.option(
    "--chain-config",
    type=str,
    required=True,
    help="Chain configuration name (gnosis, base).",
)
@click.option(
    "--key",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    help="Path to private key file (client mode only).",
)
@click.pass_context
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
    try:
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

        # Extract agent mode
        agent_mode = not ctx.obj.get("client_mode", False)
        click.echo(f"Running purchase nvm subscription with agent_mode={agent_mode}")

        # Load configuration (for ledger API creation)
        mech_config = get_mech_config(validated_chain)

        # Fetch agent mode data if needed
        key_path: Optional[str] = key
        key_password: Optional[str] = None
        safe: Optional[str] = None

        if agent_mode:
            safe, key_path, key_password = fetch_agent_mode_keys(validated_chain)
            if not safe or not key_path:
                raise ClickException("Cannot fetch safe or key data for agent mode.")

        if not key_path:
            raise ClickException(
                "Private key path is required. Use --key option or set up "
                "agent mode."
            )

        # Create crypto object
        crypto = EthereumCrypto(
            private_key_path=key_path,
            password=key_password,
        )

        # Create ledger API
        from dataclasses import asdict  # pylint: disable=import-outside-toplevel

        ledger_api = EthereumApi(**asdict(mech_config.ledger_config))

        # Create Ethereum client for agent mode
        ethereum_client = None
        if agent_mode:
            ethereum_client = EthereumClient(mech_config.rpc_url)

        # Create subscription service
        service = SubscriptionService(
            chain_config=validated_chain,
            crypto=crypto,
            ledger_api=ledger_api,
            agent_mode=agent_mode,
            ethereum_client=ethereum_client,
            safe_address=safe,
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
        click.echo(
            f"Credits Gained: {result['credits_after'] - result['credits_before']}"
        )
        click.echo("=" * 70)

    except ValueError as e:
        # NVM config errors, balance check errors
        if "NVM subscriptions not supported" in str(e):
            raise ClickException(
                f"NVM subscription error: {e}\n\n"
                f"NVM subscriptions are only available on Gnosis and Base chains."
            ) from e
        if "Insufficient" in str(e):
            raise ClickException(
                f"Insufficient balance: {e}\n\n"
                f"Please ensure you have enough funds for the subscription fee."
            ) from e
        raise ClickException(
            f"Configuration error: {e}\n\n"
            f"Please check your chain configuration and try again."
        ) from e
    except RuntimeError as e:
        # Transaction execution errors
        raise ClickException(
            f"Transaction failed: {e}\n\n"
            f"The subscription transaction was rejected.\n\n"
            f"Please check the transaction details and try again."
        ) from e
    except FileNotFoundError as e:
        raise ClickException(
            f"Configuration file not found: {e}\n\n"
            f"NVM subscription requires configuration files.\n\n"
            f"Please ensure the NVM configuration is properly installed."
        ) from e
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
            f"NVM subscription requires environment variables from "
            f"chain-specific .env file.\n\n"
            f"Required variables: PLAN_DID, NETWORK_NAME, CHAIN_ID\n\n"
            f"Please ensure the .env file for {validated_chain} exists and "
            f"contains all required variables."
        ) from e
    except requests.exceptions.HTTPError as e:
        rpc_url = os.getenv("MECHX_CHAIN_RPC", mech_config.rpc_url)
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
        rpc_url = os.getenv("MECHX_CHAIN_RPC", mech_config.rpc_url)
        raise ClickException(
            f"Network error connecting to RPC: {e}\n\n"
            f"Current RPC: {rpc_url}\n\n"
            f"Possible solutions:\n"
            f"  1. Check your internet connection\n"
            f"  2. Verify the RPC URL is correct\n"
            f"  3. Try a different RPC provider: "
            f"export MECHX_CHAIN_RPC='https://your-rpc-url'"
        ) from e
