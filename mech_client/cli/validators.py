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

"""CLI input validators."""

import json
from pathlib import Path

from click import ClickException
from eth_utils import is_address
from web3.constants import ADDRESS_ZERO


MECHX_CHAIN_CONFIGS = Path(__file__).parent.parent / "configs" / "mechs.json"


def validate_chain_config(chain_config: str) -> str:
    """
    Validate that the chain config exists in mechs.json.

    :param chain_config: Chain configuration name
    :return: Validated chain config name
    :raises ClickException: If chain config is invalid or not found
    """
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


def validate_amount(amount: str, name: str = "Amount") -> int:
    """
    Validate amount is a positive integer.

    :param amount: Amount string to validate
    :param name: Name of the amount for error messages
    :return: Validated amount as integer
    :raises ClickException: If amount is invalid
    """
    try:
        amount_int = int(amount)
        if amount_int <= 0:
            raise ValueError
        return amount_int
    except (ValueError, TypeError) as e:
        raise ClickException(
            f"Invalid {name}: {amount!r}\n\n"
            f"{name} must be a positive integer.\n\n"
            f"Example: 1000000000000000000 (1 token with 18 decimals)"
        ) from e


def validate_tool_id(tool_id: str) -> str:
    """
    Validate tool ID format (service_id-tool_name).

    :param tool_id: Tool ID to validate
    :return: Validated tool ID
    :raises ClickException: If tool ID format is invalid
    """
    if "-" not in tool_id:
        raise ClickException(
            f"Invalid tool ID format: {tool_id!r}\n\n"
            f"Expected format: service_id-tool_name\n"
            f"Example: 1-openai-gpt-3.5-turbo"
        )
    return tool_id
