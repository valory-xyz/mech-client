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

"""Common helper functions for CLI commands."""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, TypeVar

import click
from aea_ledger_ethereum import EthereumCrypto
from click import ClickException
from safe_eth.eth import EthereumClient

from mech_client.cli.validators import validate_ethereum_address
from mech_client.infrastructure.config import get_mech_config
from mech_client.infrastructure.operate.key_manager import fetch_agent_mode_keys
from mech_client.utils.constants import DEFAULT_PRIVATE_KEY_FILE


@dataclass
class WalletCommandContext:
    """Context object containing wallet command setup results."""

    crypto: EthereumCrypto
    agent_mode: bool
    safe_address: Optional[str]
    ethereum_client: Optional[EthereumClient]


def load_crypto_with_error_handling(
    key_path: str, key_password: Optional[str] = None
) -> EthereumCrypto:
    """
    Load Ethereum crypto object with standardized error handling.

    :param key_path: Path to private key file
    :param key_password: Optional password for encrypted key
    :return: Initialized EthereumCrypto object
    :raises ClickException: On permission errors, decryption errors, or invalid key format
    """
    try:
        return EthereumCrypto(private_key_path=key_path, password=key_password)
    except PermissionError as e:
        raise ClickException(
            f"Cannot read private key file: {key_path}\n"
            f"Permission denied. Check file permissions:\n"
            f"  chmod 600 {key_path}"
        ) from e
    except (ValueError, Exception) as e:
        error_msg = str(e).lower()
        if "password" in error_msg or "decrypt" in error_msg or "mac" in error_msg:
            raise ClickException(
                f"Failed to decrypt private key: {e}\n\n"
                f"Possible causes:\n"
                f"  • Incorrect password\n"
                f"  • Corrupted keyfile\n"
                f"  • Invalid keyfile format\n\n"
                f"Please verify your private key file and password."
            ) from e
        raise ClickException(f"Error loading private key: {e}") from e


def setup_wallet_command(
    ctx: click.Context, chain_config: str, key: Optional[str] = None
) -> WalletCommandContext:
    """
    Common setup for all wallet commands (request, deposit, subscription).

    Handles:
    - Agent mode detection from context
    - Key path resolution (agent mode vs client mode)
    - Safe address and Ethereum client creation for agent mode
    - Private key loading with error handling

    :param ctx: Click context object
    :param chain_config: Validated chain configuration name
    :param key: Optional path to private key file (client mode only)
    :return: WalletCommandContext with crypto, agent_mode, safe_address, ethereum_client
    :raises ClickException: On configuration errors, missing keys, or validation failures
    """
    # Extract agent mode from context
    agent_mode = not ctx.obj.get("client_mode", False)
    click.echo(f"Running command with agent_mode={agent_mode}")

    # Initialize variables
    key_path: Optional[str] = key
    key_password: Optional[str] = None
    safe: Optional[str] = None
    ethereum_client: Optional[EthereumClient] = None

    if agent_mode:
        # Agent mode: fetch safe address, key path, and password from operate
        safe, key_path, key_password = fetch_agent_mode_keys(chain_config)
        if not safe or not key_path:
            raise ClickException("Cannot fetch safe or key data for agent mode.")
        validate_ethereum_address(safe, "Safe address")

        # Create Ethereum client for agent mode
        mech_config = get_mech_config(chain_config)
        ethereum_client = EthereumClient(mech_config.ledger_config.address)
    else:
        # Client mode: use provided key path or default
        key_path = key or DEFAULT_PRIVATE_KEY_FILE
        if not Path(key_path).exists():
            raise ClickException(
                f"Private key file `{key_path}` does not exist!\n"
                f"Specify a valid key file with --key option."
            )

    # Load private key with error handling
    crypto = load_crypto_with_error_handling(key_path, key_password)

    return WalletCommandContext(
        crypto=crypto,
        agent_mode=agent_mode,
        safe_address=safe,
        ethereum_client=ethereum_client,
    )


F = TypeVar("F", bound=Callable)


def common_wallet_options(func: F) -> F:
    """
    Decorator that adds common wallet command options.

    Adds --chain-config and --key options to CLI commands that need wallet access.
    Use this decorator on wallet commands (request, deposit, subscription).

    :param func: The command function to decorate
    :return: Decorated function with wallet options
    """
    func = click.option(
        "--key",
        type=click.Path(exists=True, file_okay=True, dir_okay=False),
        help="Path to private key file (client mode only).",
    )(func)
    func = click.option(
        "--chain-config",
        type=str,
        required=True,
        help="Chain configuration name (gnosis, base, polygon, optimism).",
    )(func)
    return func
