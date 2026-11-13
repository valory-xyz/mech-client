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

from typing import Dict, Optional

from mech_client.infrastructure.config.contract_addresses import (
    CHAIN_TO_NATIVE_BALANCE_TRACKER,
    CHAIN_TO_PRICE_TOKEN_OLAS,
    CHAIN_TO_PRICE_TOKEN_USDC,
    CHAIN_TO_TOKEN_BALANCE_TRACKER_OLAS,
    CHAIN_TO_TOKEN_BALANCE_TRACKER_USDC,
)
from mech_client.infrastructure.config.loader import get_chain_id
from mech_client.infrastructure.config.payment_config import PaymentType

PAYMENT_TOKENS: Dict[PaymentType, Dict[int, str]] = {
    PaymentType.OLAS_TOKEN: CHAIN_TO_PRICE_TOKEN_OLAS,
    PaymentType.USDC_TOKEN: CHAIN_TO_PRICE_TOKEN_USDC,
    PaymentType.TOKEN_NVM_USDC: CHAIN_TO_PRICE_TOKEN_USDC,
}
# The payment types the prepaid balance is topped up for by a plain deposit
# into a balance tracker. NVM subscription types are paid via subscription.
DEPOSIT_TRACKERS: Dict[PaymentType, Dict[int, str]] = {
    PaymentType.NATIVE: CHAIN_TO_NATIVE_BALANCE_TRACKER,
    PaymentType.OLAS_TOKEN: CHAIN_TO_TOKEN_BALANCE_TRACKER_OLAS,
    PaymentType.USDC_TOKEN: CHAIN_TO_TOKEN_BALANCE_TRACKER_USDC,
}


def payment_token(payment_type: PaymentType, chain: str) -> Optional[str]:
    """
    Name the token a mech with this payment type is paid in on a chain.

    :param payment_type: The mech's payment type
    :param chain: Chain name
    :return: The token address, or None when the mech is paid in the native asset
    :raises ValueError: If the chain is unknown, or the token is not deployed on it
    """
    tokens = PAYMENT_TOKENS.get(payment_type)
    if tokens is None:
        return None
    chain_id = get_chain_id(chain)
    token = tokens.get(chain_id)
    if not token:
        raise ValueError(f"{payment_type.name} is not available on {chain}")
    return token


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
    trackers = DEPOSIT_TRACKERS.get(payment_type)
    if trackers is None:
        return None
    return trackers.get(chain_id) or None
