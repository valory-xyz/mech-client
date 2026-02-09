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

"""Business-level validators for mech client.

These validators contain business logic and are independent of the CLI layer.
They can be used by services, domain logic, or any other component.
"""

from typing import List, Optional

from eth_utils import is_address
from web3 import Web3
from web3.constants import ADDRESS_ZERO

from mech_client.infrastructure.config import PaymentType
from mech_client.utils.errors import ValidationError


def ensure_checksummed_address(address: str) -> str:
    """
    Ensure an address is in checksummed format.

    This is a lightweight helper that converts any valid Ethereum address
    to its checksummed form without performing validation. Use this when
    you already know the address is valid (e.g., from validated input or
    internal sources) but need to ensure it's checksummed for web3.py.

    :param address: Ethereum address (checksummed or not)
    :return: Checksummed address
    """
    return Web3.to_checksum_address(address)


def validate_ethereum_address(address: str, allow_zero: bool = False) -> str:
    """
    Validate Ethereum address format and return checksummed address.

    Accepts both checksummed and non-checksummed addresses, validates them,
    and returns the checksummed version. This ensures compatibility with
    web3.py which requires checksummed addresses.

    :param address: Address to validate (checksummed or not)
    :param allow_zero: Whether to allow zero address
    :return: Validated checksummed address
    :raises ValidationError: If address is invalid
    """
    if not address:
        raise ValidationError("Address cannot be empty")

    # Validate address format first (works with both checksummed and non-checksummed)
    if not is_address(address):
        raise ValidationError(
            f"Invalid Ethereum address format: {address!r}\n"
            f"Expected format: 0x followed by 40 hexadecimal characters"
        )

    # Convert to checksummed address
    checksummed_address = Web3.to_checksum_address(address)

    # Check zero address after checksumming
    if not allow_zero and checksummed_address == ADDRESS_ZERO:
        raise ValidationError(f"Address cannot be zero address: {ADDRESS_ZERO}")

    return checksummed_address


def validate_amount(amount: int, min_value: int = 1) -> int:
    """
    Validate amount is a positive integer.

    :param amount: Amount to validate
    :param min_value: Minimum allowed value (default: 1)
    :return: Validated amount
    :raises ValidationError: If amount is invalid
    """
    if not isinstance(amount, int):
        raise ValidationError(f"Amount must be an integer, got {type(amount).__name__}")

    if amount < min_value:
        raise ValidationError(f"Amount must be at least {min_value}, got {amount}")

    return amount


def validate_tool_id(tool_id: str) -> str:
    """
    Validate tool ID format (service_id-tool_name).

    :param tool_id: Tool ID to validate
    :return: Validated tool ID
    :raises ValidationError: If tool ID format is invalid
    """
    if not tool_id:
        raise ValidationError("Tool ID cannot be empty")

    if "-" not in tool_id:
        raise ValidationError(
            f"Invalid tool ID format: {tool_id!r}\n"
            f"Expected format: service_id-tool_name\n"
            f"Example: 1-openai-gpt-3.5-turbo"
        )

    parts = tool_id.split("-", 1)
    service_id_str = parts[0]

    try:
        service_id = int(service_id_str)
        if service_id < 0:
            raise ValueError
    except ValueError as e:
        raise ValidationError(
            f"Invalid service ID in tool ID: {service_id_str!r}\n"
            f"Service ID must be a non-negative integer"
        ) from e

    return tool_id


def validate_payment_type(payment_type: str) -> PaymentType:
    """
    Validate payment type string.

    :param payment_type: Payment type string to validate
    :return: Validated PaymentType enum
    :raises ValidationError: If payment type is invalid
    """
    try:
        return PaymentType[payment_type.upper()]
    except KeyError as e:
        valid_types = ", ".join([pt.name for pt in PaymentType])
        raise ValidationError(
            f"Invalid payment type: {payment_type!r}\n" f"Valid types: {valid_types}"
        ) from e


def validate_service_id(service_id: int) -> int:
    """
    Validate service ID (agent ID).

    :param service_id: Service ID to validate
    :return: Validated service ID
    :raises ValidationError: If service ID is invalid
    """
    if not isinstance(service_id, int):
        raise ValidationError(
            f"Service ID must be an integer, got {type(service_id).__name__}"
        )

    if service_id < 0:
        raise ValidationError(f"Service ID must be non-negative, got {service_id}")

    return service_id


def validate_ipfs_hash(ipfs_hash: str) -> str:
    """
    Validate IPFS hash (CID) format.

    :param ipfs_hash: IPFS hash to validate
    :return: Validated IPFS hash
    :raises ValidationError: If IPFS hash format is invalid
    """
    if not ipfs_hash:
        raise ValidationError("IPFS hash cannot be empty")

    # Basic validation - should start with common CID prefixes
    if not (
        ipfs_hash.startswith("Qm")
        or ipfs_hash.startswith("bafy")
        or ipfs_hash.startswith("f01")
    ):
        raise ValidationError(
            f"Invalid IPFS hash format: {ipfs_hash!r}\n"
            f"Expected CIDv0 (Qm...) or CIDv1 (bafy.../f01...)"
        )

    return ipfs_hash


def validate_chain_support(
    chain: str, supported_chains: List[str], feature: str
) -> None:
    """
    Validate that chain supports a specific feature.

    :param chain: Chain to validate
    :param supported_chains: List of supported chains
    :param feature: Feature name (for error message)
    :raises ValidationError: If chain doesn't support feature
    """
    if chain not in supported_chains:
        supported = ", ".join(supported_chains)
        raise ValidationError(
            f"Chain {chain!r} does not support {feature}.\n"
            f"Supported chains: {supported}"
        )


def validate_batch_sizes_match(prompts: List[str], tools: List[str]) -> None:
    """
    Validate that batch request sizes match.

    :param prompts: List of prompts
    :param tools: List of tools
    :raises ValidationError: If sizes don't match
    """
    if len(prompts) != len(tools):
        raise ValidationError(
            f"Number of prompts ({len(prompts)}) must match "
            f"number of tools ({len(tools)})"
        )


def validate_timeout(timeout: Optional[float]) -> float:
    """
    Validate timeout value.

    :param timeout: Timeout in seconds (None for default)
    :return: Validated timeout value
    :raises ValidationError: If timeout is invalid
    """
    if timeout is None:
        return 900.0  # Default 15 minutes

    if not isinstance(timeout, (int, float)):
        raise ValidationError(f"Timeout must be a number, got {type(timeout).__name__}")

    if timeout <= 0:
        raise ValidationError(f"Timeout must be positive, got {timeout}")

    return float(timeout)


def validate_extra_attributes(extra_attributes: dict) -> dict:
    """
    Validate extra attributes dictionary.

    :param extra_attributes: Dictionary of extra attributes
    :return: Validated extra attributes
    :raises ValidationError: If attributes are invalid
    """
    if not isinstance(extra_attributes, dict):
        raise ValidationError(
            f"Extra attributes must be a dictionary, "
            f"got {type(extra_attributes).__name__}"
        )

    # Ensure all keys and values are strings
    for key, value in extra_attributes.items():
        if not isinstance(key, str):
            raise ValidationError(
                f"Extra attribute key must be a string, "
                f"got {type(key).__name__}: {key!r}"
            )
        if not isinstance(value, (str, int, float, bool)):
            raise ValidationError(
                f"Extra attribute value must be a primitive type, "
                f"got {type(value).__name__} for key {key!r}"
            )

    return extra_attributes
