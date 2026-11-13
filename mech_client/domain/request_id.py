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

"""The marketplace request id, derived locally rather than read from an RPC."""

from eth_abi import encode as abi_encode
from eth_utils import keccak

REQUEST_STRUCT_TYPES = [
    "address",
    "address",
    "address",
    "bytes32",
    "uint256",
    "bytes32",
    "uint256",
]


def request_digest(  # pylint: disable=too-many-arguments  # the id's preimage, kw-only
    *,
    domain_separator: bytes,
    marketplace: str,
    mech: str,
    requester: str,
    data_hash: bytes,
    delivery_rate: int,
    payment_type: bytes,
    nonce: int,
) -> bytes:
    r"""
    Recompute ``MechMarketplace.getRequestId`` locally.

    The id an off-chain request signs is EIP-712 shaped::

        keccak256("\x19\x01" ‖ domainSeparator ‖ keccak256(abi.encode(
            marketplace, mech, requester, keccak256(data),
            deliveryRate, paymentType, nonce)))

    :param domain_separator: The marketplace's ``domainSeparator()``
    :param marketplace: The marketplace contract address
    :param mech: The priority mech address
    :param requester: The requester of record (Safe in agent mode, else EOA)
    :param data_hash: The request data bytes (the truncated IPFS hash)
    :param delivery_rate: The signed maximum delivery rate
    :param payment_type: The 32-byte payment type
    :param nonce: The marketplace nonce
    :return: The 32-byte request id
    """
    struct_hash = keccak(
        abi_encode(
            REQUEST_STRUCT_TYPES,
            [
                marketplace,
                mech,
                requester,
                keccak(data_hash),
                delivery_rate,
                payment_type,
                nonce,
            ],
        )
    )
    return bytes(keccak(b"\x19\x01" + domain_separator + struct_hash))
