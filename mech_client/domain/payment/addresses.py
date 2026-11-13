# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2026 Valory AG
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

"""Which token a mech is paid in, and which balance tracker a top-up pays."""

from typing import Dict, FrozenSet, Optional, Tuple

from mech_client.infrastructure.config.contract_addresses import (
    CHAIN_TO_NATIVE_BALANCE_TRACKER,
    CHAIN_TO_PRICE_TOKEN_OLAS,
    CHAIN_TO_PRICE_TOKEN_USDC,
    CHAIN_TO_TOKEN_BALANCE_TRACKER_OLAS,
    CHAIN_TO_TOKEN_BALANCE_TRACKER_USDC,
)
from mech_client.infrastructure.config.loader import get_chain_id
from mech_client.infrastructure.config.payment_config import PaymentType

# Each table is keyed by chain id, with the label its errors name. Native
# payment types have no token. These are the only mappings from payment type
# to address: the payment strategies read them too.
PAYMENT_TOKENS: Dict[PaymentType, Tuple[Dict[int, str], str]] = {
    PaymentType.OLAS_TOKEN: (CHAIN_TO_PRICE_TOKEN_OLAS, "OLAS"),
    PaymentType.USDC_TOKEN: (CHAIN_TO_PRICE_TOKEN_USDC, "USDC"),
    PaymentType.TOKEN_NVM_USDC: (CHAIN_TO_PRICE_TOKEN_USDC, "USDC"),
}
BALANCE_TRACKERS: Dict[PaymentType, Tuple[Dict[int, str], str]] = {
    PaymentType.NATIVE: (CHAIN_TO_NATIVE_BALANCE_TRACKER, "Native"),
    PaymentType.OLAS_TOKEN: (CHAIN_TO_TOKEN_BALANCE_TRACKER_OLAS, "OLAS"),
    PaymentType.USDC_TOKEN: (CHAIN_TO_TOKEN_BALANCE_TRACKER_USDC, "USDC"),
    PaymentType.NATIVE_NVM: (CHAIN_TO_NATIVE_BALANCE_TRACKER, "NVM native"),
    PaymentType.TOKEN_NVM_USDC: (CHAIN_TO_TOKEN_BALANCE_TRACKER_USDC, "NVM USDC"),
}
# The payment types whose prepaid balance is topped up by a plain deposit into
# their balance tracker. NVM subscription types are paid via subscription.
DEPOSIT_PAYMENT_TYPES: FrozenSet[PaymentType] = frozenset(
    {PaymentType.NATIVE, PaymentType.OLAS_TOKEN, PaymentType.USDC_TOKEN}
)


def _lookup(entry: Tuple[Dict[int, str], str], chain_id: int, kind: str) -> str:
    """Return a table's address for a chain.

    :param entry: The table and the label its errors name
    :param chain_id: The chain id
    :param kind: What the address is, for the error
    :return: The address
    :raises ValueError: If the table has none for the chain
    """
    table, label = entry
    address = table.get(chain_id)
    if not address:
        raise ValueError(f"{label} {kind} not available for chain {chain_id}")
    return address


def token_address(payment_type: PaymentType, chain_id: int) -> Optional[str]:
    """
    Return the token a payment type pays in on a chain, by chain id.

    :param payment_type: The payment type
    :param chain_id: The chain id
    :return: The token address, or None for a native payment type
    :raises ValueError: If the token is not deployed on the chain
    """
    entry = PAYMENT_TOKENS.get(payment_type)
    if entry is None:
        return None
    return _lookup(entry, chain_id, "token")


def tracker_address(payment_type: PaymentType, chain_id: int) -> str:
    """
    Return the balance tracker of a payment type on a chain, by chain id.

    :param payment_type: The payment type
    :param chain_id: The chain id
    :return: The tracker address
    :raises ValueError: If no tracker is deployed for it on the chain
    """
    return _lookup(BALANCE_TRACKERS[payment_type], chain_id, "balance tracker")


def payment_token(payment_type: PaymentType, chain: str) -> Optional[str]:
    """
    Name the token a mech with this payment type is paid in on a chain.

    An unknown chain propagates ``get_chain_id``'s ``ValueError``, and a token
    not deployed on the chain ``token_address``'s.

    :param payment_type: The mech's payment type
    :param chain: Chain name
    :return: The token address, or None when the mech is paid in the native asset
    """
    return token_address(payment_type, get_chain_id(chain))


def balance_tracker(chain: str, payment_type: PaymentType) -> Optional[str]:
    """
    Name the balance tracker a prepaid top-up for this payment type pays.

    It is the contract ``DepositService`` and the auto-deposit after an
    off-chain HTTP 402 send funds to. An unknown chain propagates
    ``get_chain_id``'s ``ValueError``.

    :param chain: Chain name
    :param payment_type: The mech's payment type
    :return: The tracker address, or None when this payment type is not topped
        up by a deposit on this chain (NVM subscriptions, or no tracker deployed)
    """
    chain_id = get_chain_id(chain)
    if payment_type not in DEPOSIT_PAYMENT_TYPES:
        return None
    table, _ = BALANCE_TRACKERS[payment_type]
    return table.get(chain_id) or None
