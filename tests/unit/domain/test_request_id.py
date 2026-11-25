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

"""Tests for the locally derived marketplace request id."""

from typing import Any, Dict

import pytest

from mech_client.domain.request_id import explicit_request_digest, request_digest

GOLDEN_INPUTS: Dict[str, Any] = {
    "domain_separator": bytes.fromhex(
        "58fbb2508b962bcf6e2708fdfc23222115504128df851ae75ef8c66f2e0bdade"
    ),
    "marketplace": "0x735FAAb1c4Ec41128c367AFb5c3baC73509f70bB",
    "mech": "0x" + "11" * 20,
    "requester": "0x" + "22" * 20,
    "data": bytes.fromhex("33" * 32),
    "delivery_rate": 7,
    "payment_type": bytes.fromhex("44" * 32),
    "nonce": 9,
}


def test_request_digest_matches_the_deployed_marketplace() -> None:
    """Golden vector recorded from the deployed gnosis marketplace.

    domainSeparator() and getRequestId(...) were called on
    0x735FAAb1c4Ec41128c367AFb5c3baC73509f70bB (2026-07-23) with these
    synthetic inputs; the local derivation must reproduce the contract's
    answer byte for byte, or every off-chain request is refused.
    """
    assert (
        request_digest(**GOLDEN_INPUTS).hex()
        == "512e9b1dd2d2d253ba226f6d47af046720b1d97a09ae71e4ecc3f640f33bf36b"
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("domain_separator", bytes.fromhex("00" * 32)),
        ("marketplace", "0x" + "55" * 20),
        ("mech", "0x" + "12" * 20),
        ("requester", "0x" + "23" * 20),
        ("data", bytes.fromhex("34" * 32)),
        ("delivery_rate", 8),
        ("payment_type", bytes.fromhex("45" * 32)),
        ("nonce", 10),
    ],
)
def test_every_input_changes_the_id(field: str, value: Any) -> None:
    """The id commits to each of its inputs."""
    assert request_digest(**{**GOLDEN_INPUTS, field: value}) != request_digest(
        **GOLDEN_INPUTS
    )


EXPLICIT_INPUTS: Dict[str, Any] = {
    "mech": "0x" + "11" * 20,
    "requester": "0x" + "22" * 20,
    "data": bytes.fromhex("33" * 32),
    "delivery_rate": 7,
    "payment_type": bytes.fromhex("44" * 32),
    "nonce": 9,
    "deadline": 1_900_000_000,
}


@pytest.mark.parametrize(
    ("chain_id", "marketplace", "expected"),
    [
        (
            100,
            "0x735FAAb1c4Ec41128c367AFb5c3baC73509f70bB",
            "0a88545ee8084de72517271130ed61d031c1b1cf48766d523f74a7df2b564b96",
        ),
        (
            137,
            "0x343F2B005cF6D70bA610CD9F1F1927049414B582",
            "cc69de6a75318009b6513d0a69f8f7fe753d9979e76ee68a0c8910be4c14f4e5",
        ),
        (
            4663,
            "0xa45E64d13A30a51b91ae0eb182e88a40e9b18eD8",
            "f9ce4425ad1e9ea12ae8c0e21e927c86a55432ef897f084cf9e8c17433c04d3f",
        ),
    ],
)
def test_explicit_request_digest_matches_the_deployed_marketplaces(
    chain_id: int, marketplace: str, expected: str
) -> None:
    """Golden vectors recorded from the deployed gnosis, polygon and robinhood marketplaces.

    getRequestIdWithNonce(...) was called on each (2026-11-25) with these
    synthetic inputs; the local derivation must reproduce the contract's
    answer byte for byte, or every explicit-nonce request is refused.
    """
    assert (
        explicit_request_digest(
            chain_id=chain_id, marketplace=marketplace, **EXPLICIT_INPUTS
        ).hex()
        == expected
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("chain_id", 101),
        ("marketplace", "0x" + "55" * 20),
        ("mech", "0x" + "12" * 20),
        ("requester", "0x" + "23" * 20),
        ("data", bytes.fromhex("34" * 32)),
        ("delivery_rate", 8),
        ("payment_type", bytes.fromhex("45" * 32)),
        ("nonce", 10),
        ("deadline", 1_900_000_001),
    ],
)
def test_every_input_changes_the_explicit_id(field: str, value: Any) -> None:
    """The explicit id commits to each of its inputs, the domain included."""
    base = {
        "chain_id": 100,
        "marketplace": "0x735FAAb1c4Ec41128c367AFb5c3baC73509f70bB",
        **EXPLICIT_INPUTS,
    }
    assert explicit_request_digest(**{**base, field: value}) != explicit_request_digest(
        **base
    )
