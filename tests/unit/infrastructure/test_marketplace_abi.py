# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2025-2026 Valory AG
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

"""Tests for ABI loader."""
"""The marketplace ABI carries the explicit-nonce path next to the sequential one."""

from typing import Any, Dict, List

import pytest
from web3 import Web3

from mech_client.infrastructure.blockchain.abi_loader import get_abi


def _functions(abi: List[Dict[str, Any]], name: str) -> List[Dict[str, Any]]:
    """Every function entry called ``name``.

    :param abi: the loaded ABI
    :param name: the function name
    :return: the matching entries, overloads included
    """
    return [entry for entry in abi if entry.get("type") == "function" and entry["name"] == name]


@pytest.fixture(name="abi")
def marketplace_abi() -> List[Dict[str, Any]]:
    """The shipped marketplace ABI.

    :return: the ABI as loaded for contract calls
    """
    return get_abi("MechMarketplace.json")


class TestMarketplaceAbi:
    """What the client relies on when it derives, signs and reads back a request."""

    def test_the_explicit_view_takes_the_sequential_arguments_plus_a_deadline(
        self, abi: List[Dict[str, Any]]
    ) -> None:
        """The explicit view is the sequential one with the signed cap and a deadline appended."""
        (sequential,) = _functions(abi, "getRequestId")
        (explicit,) = _functions(abi, "getRequestIdWithNonce")

        assert [i["type"] for i in sequential["inputs"]] == [
            "address", "address", "bytes", "uint256", "bytes32", "uint256"
        ]
        assert [i["type"] for i in explicit["inputs"]] == [
            "address", "address", "bytes", "uint256", "bytes32", "uint256", "uint256"
        ]
        assert [i["name"] for i in explicit["inputs"]][-2:] == ["nonce", "deadline"]
        assert explicit["outputs"] == sequential["outputs"]
        assert explicit["stateMutability"] == "view"

    def test_the_explicit_path_has_its_own_signing_domain(
        self, abi: List[Dict[str, Any]]
    ) -> None:
        """``getDomainSeparatorWithNonce`` is distinct from ``getDomainSeparator``."""
        (legacy,) = _functions(abi, "getDomainSeparator")
        (explicit,) = _functions(abi, "getDomainSeparatorWithNonce")
        (type_hash,) = _functions(abi, "EXPLICIT_NONCE_TYPE_HASH")
        assert legacy["inputs"] == explicit["inputs"] == []
        assert explicit["outputs"] == legacy["outputs"]
        assert type_hash["outputs"][0]["type"] == "bytes32"

    def test_the_marketplace_settles_a_cap_with_an_actual_and_an_explicit_nonce(
        self, abi: List[Dict[str, Any]]
    ) -> None:
        """The deliver overloads settle: cap only, cap and actual, cap and actual and nonce."""
        overloads = _functions(abi, "deliverMarketplaceWithSignatures")

        assert sorted(len(entry["inputs"]) for entry in overloads) == [4, 5, 7]
        (with_nonces,) = [entry for entry in overloads if len(entry["inputs"]) == 7]
        assert [i["name"] for i in with_nonces["inputs"]] == [
            "requester", "deliverWithSignatures", "deliveryRates", "maxRates", "nonces", "deadlines", "paymentData"
        ]

    def test_the_explicit_nonce_tag_is_readable(self, abi: List[Dict[str, Any]]) -> None:
        """The domain tag that separates the two request ids is exposed as a constant."""
        (tag,) = _functions(abi, "EXPLICIT_NONCE_TAG")

        assert tag["inputs"] == []
        assert [o["type"] for o in tag["outputs"]] == ["bytes32"]

    def test_web3_accepts_the_overloaded_abi(self, abi: List[Dict[str, Any]]) -> None:
        """Overloads must not stop the contract object, and so every call, from being built."""
        contract = Web3().eth.contract(address="0x" + "9" * 40, abi=abi)

        assert contract.functions.getRequestIdWithNonce is not None
        assert contract.functions.getRequestId is not None
