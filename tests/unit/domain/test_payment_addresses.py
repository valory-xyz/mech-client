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

"""Tests for the payment token and balance tracker lookups."""

from typing import Optional

import pytest
from mech_client.domain.payment.addresses import balance_tracker, payment_token
from mech_client.infrastructure.config import (
    CHAIN_TO_NATIVE_BALANCE_TRACKER,
    CHAIN_TO_PRICE_TOKEN_OLAS,
    CHAIN_TO_PRICE_TOKEN_USDC,
    CHAIN_TO_TOKEN_BALANCE_TRACKER_OLAS,
    CHAIN_TO_TOKEN_BALANCE_TRACKER_USDC,
    PaymentType,
)
from mech_client.infrastructure.config.loader import get_chain_id


@pytest.mark.parametrize(
    ("payment_type", "chain", "expected"),
    [
        (PaymentType.NATIVE, "gnosis", None),
        (PaymentType.NATIVE_NVM, "gnosis", None),
        (PaymentType.OLAS_TOKEN, "gnosis", CHAIN_TO_PRICE_TOKEN_OLAS[100]),
        (PaymentType.USDC_TOKEN, "base", CHAIN_TO_PRICE_TOKEN_USDC[8453]),
        (PaymentType.TOKEN_NVM_USDC, "base", CHAIN_TO_PRICE_TOKEN_USDC[8453]),
    ],
)
def test_payment_token_names_the_token_or_none_for_native(
    payment_type: PaymentType, chain: str, expected: Optional[str]
) -> None:
    """Native mechs have no token; token mechs name it from mech-client's table."""
    assert payment_token(payment_type, chain) == expected


@pytest.mark.parametrize(
    ("payment_type", "chain", "match"),
    [
        (PaymentType.USDC_TOKEN, "gnosis", "not available on gnosis"),
        (PaymentType.OLAS_TOKEN, "nowhere", "Unknown chain"),
    ],
)
def test_payment_token_refuses_a_token_it_cannot_name(
    payment_type: PaymentType, chain: str, match: str
) -> None:
    """None means native, so a missing token or chain is an error, not None."""
    with pytest.raises(ValueError, match=match):
        payment_token(payment_type, chain)


@pytest.mark.parametrize(
    ("chain", "payment_type", "expected"),
    [
        ("gnosis", PaymentType.NATIVE, CHAIN_TO_NATIVE_BALANCE_TRACKER[100]),
        ("gnosis", PaymentType.OLAS_TOKEN, CHAIN_TO_TOKEN_BALANCE_TRACKER_OLAS[100]),
        ("polygon", PaymentType.USDC_TOKEN, CHAIN_TO_TOKEN_BALANCE_TRACKER_USDC[137]),
        ("gnosis", PaymentType.USDC_TOKEN, None),  # no tracker deployed
        ("gnosis", PaymentType.NATIVE_NVM, None),  # paid by subscription
        ("base", PaymentType.TOKEN_NVM_USDC, None),
    ],
)
def test_balance_tracker_names_the_tracker_a_top_up_pays(
    chain: str, payment_type: PaymentType, expected: Optional[str]
) -> None:
    """The tracker the auto-deposit pays, or None where no deposit applies."""
    assert balance_tracker(chain, payment_type) == expected


def test_balance_tracker_refuses_an_unknown_chain() -> None:
    """An unknown chain is an error rather than "no tracker"."""
    with pytest.raises(ValueError, match="Unknown chain"):
        balance_tracker("nowhere", PaymentType.NATIVE)


def test_get_chain_id_reads_mechs_json() -> None:
    """The chain id comes from the packaged configuration."""
    assert get_chain_id("robinhood") == 4663
