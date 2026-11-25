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

# ``MechMarketplace.EXPLICIT_NONCE_TYPE_HASH``: explicit-nonce requests are
# standard EIP-712 typed data under the marketplace's second signing domain.
EXPLICIT_NONCE_TYPE_HASH = keccak(
    text=(
        "ExplicitNonceDelivery(address mech,address requester,bytes data,"
        "uint256 maxDeliveryRate,bytes32 paymentType,uint256 nonce,uint256 deadline)"
    )
)
EIP712_DOMAIN_TYPE_HASH = keccak(
    text=(
        "EIP712Domain(string name,string version,uint256 chainId,"
        "address verifyingContract)"
    )
)
EXPLICIT_NONCE_DOMAIN_NAME = "MechMarketplace"
EXPLICIT_NONCE_DOMAIN_VERSION = "2"

EXPLICIT_STRUCT_TYPES = [
    "bytes32",
    "address",
    "address",
    "bytes32",
    "uint256",
    "bytes32",
    "uint256",
    "uint256",
]

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
    data: bytes,
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
    :param data: The request's data, hashed here (for an off-chain request,
        the truncated IPFS hash of its metadata)
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
                keccak(data),
                delivery_rate,
                payment_type,
                nonce,
            ],
        )
    )
    return bytes(keccak(b"\x19\x01" + domain_separator + struct_hash))


def explicit_nonce_domain_separator(*, chain_id: int, marketplace: str) -> bytes:
    """
    Recompute ``MechMarketplace.getDomainSeparatorWithNonce`` locally.

    :param chain_id: The chain the marketplace is deployed on
    :param marketplace: The marketplace contract address
    :return: The 32-byte domain separator of the explicit-nonce path
    """
    return bytes(
        keccak(
            abi_encode(
                ["bytes32", "bytes32", "bytes32", "uint256", "address"],
                [
                    EIP712_DOMAIN_TYPE_HASH,
                    keccak(text=EXPLICIT_NONCE_DOMAIN_NAME),
                    keccak(text=EXPLICIT_NONCE_DOMAIN_VERSION),
                    chain_id,
                    marketplace,
                ],
            )
        )
    )


def explicit_request_digest(  # pylint: disable=too-many-arguments  # the id's preimage, kw-only
    *,
    chain_id: int,
    marketplace: str,
    mech: str,
    requester: str,
    data: bytes,
    delivery_rate: int,
    payment_type: bytes,
    nonce: int,
    deadline: int,
) -> bytes:
    r"""
    Recompute ``MechMarketplace.getRequestIdWithNonce`` locally.

    The id an explicit-nonce request signs is EIP-712 typed data::

        keccak256("\x19\x01" ‖ getDomainSeparatorWithNonce() ‖ keccak256(abi.encode(
            EXPLICIT_NONCE_TYPE_HASH, mech, requester, keccak256(data),
            maxDeliveryRate, paymentType, nonce, deadline)))

    The marketplace address enters through the domain separator.

    :param chain_id: The chain the marketplace is deployed on
    :param marketplace: The marketplace contract address
    :param mech: The priority mech address
    :param requester: The requester of record (Safe in agent mode, else EOA)
    :param data: The request's data, hashed here
    :param delivery_rate: The signed cap
    :param payment_type: The 32-byte payment type
    :param nonce: The requester-chosen nonce
    :param deadline: The last timestamp at which the request settles
    :return: The 32-byte request id
    """
    struct_hash = keccak(
        abi_encode(
            EXPLICIT_STRUCT_TYPES,
            [
                EXPLICIT_NONCE_TYPE_HASH,
                mech,
                requester,
                keccak(data),
                delivery_rate,
                payment_type,
                nonce,
                deadline,
            ],
        )
    )
    domain_separator = explicit_nonce_domain_separator(
        chain_id=chain_id, marketplace=marketplace
    )
    return bytes(keccak(b"\x19\x01" + domain_separator + struct_hash))
