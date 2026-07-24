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

"""Local signer wrapping an in-process private key (default implementation)."""

from typing import Any, Dict

from aea_ledger_ethereum import EthereumApi, EthereumCrypto
from eth_abi import encode as abi_encode
from eth_account import Account
from eth_utils import keccak
from mech_client.utils.validators import ensure_checksummed_address

# EIP-712 typehash constants for Safe v1.4.1 SafeMessage wrapping.
# Recomputed as keccak of the type string below so a reader can diff them
# against the on-chain constants without decoding hex.
_EIP712_DOMAIN_TYPEHASH = keccak(
    text="EIP712Domain(uint256 chainId,address verifyingContract)"
)
_SAFE_MESSAGE_TYPEHASH = keccak(text="SafeMessage(bytes message)")


class LocalSigner:
    """Default :class:`Signer` implementation backed by a local private key.

    Wraps an ``EthereumCrypto`` (raw key in-process) and an ``EthereumApi``
    (for nonce/gas fill and broadcasting), preserving the historic signing
    behavior of mech-client.
    """

    def __init__(self, crypto: EthereumCrypto, ledger_api: EthereumApi):
        """
        Initialize local signer.

        :param crypto: Ethereum crypto object holding the private key
        :param ledger_api: Ethereum API used to fill tx defaults and broadcast
        """
        self.crypto = crypto
        self.ledger_api = ledger_api

    @property
    def address(self) -> str:
        """The EOA address of the wrapped key.

        :return: Signer's EOA address
        """
        return str(self.crypto.address)

    def send_transaction(self, unsigned_tx: Dict[str, Any]) -> str:
        """Sign an EOA transaction with the local key and broadcast it.

        Fills ``nonce``, gas price, and ``gas`` from the connected node when
        absent, then signs and sends via the ledger API (``raise_on_try=True``
        propagates build/sign/send failures).

        :param unsigned_tx: Unsigned transaction dict
        :return: Transaction hash (0x-prefixed hex string)
        """
        tx = dict(unsigned_tx)
        tx.setdefault("from", self.address)
        if tx.get("nonce") is None:
            tx["nonce"] = self.ledger_api.api.eth.get_transaction_count(self.address)
        if "gasPrice" not in tx and "maxFeePerGas" not in tx:
            tx["gasPrice"] = self.ledger_api.api.eth.gas_price
        if tx.get("gas") is None:
            tx["gas"] = self.ledger_api.api.eth.estimate_gas(tx)
        signed_transaction = self.crypto.sign_transaction(tx)
        transaction_digest = self.ledger_api.send_signed_transaction(
            signed_transaction,
            raise_on_try=True,
        )
        return str(transaction_digest)

    def sign_message(self, message: bytes) -> bytes:
        """Sign ``message`` with the local key.

        For 32-byte inputs (the mech request-id digest) this signs the digest
        directly (``unsafe_sign_hash``), matching the marketplace contract's
        plain ``ecrecover`` verification — see :class:`Signer.sign_message`.

        :param message: Message bytes to sign
        :return: 65-byte signature (r ‖ s ‖ v)
        """
        signature = self.crypto.sign_message(message, is_deprecated_mode=True)
        return bytes.fromhex(signature.removeprefix("0x"))

    def sign_safe_message(
        self, safe_address: str, chain_id: int, message: bytes
    ) -> bytes:
        """Sign the Safe-wrapped EIP-712 hash of ``message`` with the local key.

        Computes the SafeMessage wrapped hash locally (no RPC) and signs it
        raw so ``Safe.isValidSignature(message, sig)`` returns the ERC-1271
        magic value on-chain — see :meth:`Signer.sign_safe_message` for the
        formula and domain assumptions.

        :param safe_address: Safe (verifyingContract) address
        :param chain_id: Chain ID for the EIP-712 domain
        :param message: Message bytes to wrap and sign
        :return: 65-byte signature (r ‖ s ‖ v) over the wrapped hash
        """
        checksummed_safe = ensure_checksummed_address(safe_address)
        domain_separator = keccak(
            abi_encode(
                ["bytes32", "uint256", "address"],
                [_EIP712_DOMAIN_TYPEHASH, chain_id, checksummed_safe],
            )
        )
        # ``Safe.isValidSignature(bytes32 hash, bytes sig)`` on the
        # v1.4.1 CompatibilityFallbackHandler wraps ``hash`` as
        # ``keccak256(abi.encode(hash))`` before hashing into
        # ``SafeMessage``. For a 32-byte input, ``abi.encode(bytes32)``
        # yields the same 32 bytes, so ``keccak256(message)`` here is
        # exactly ``keccak256(<32 raw bytes>)`` — the same value the
        # handler computes on-chain.
        struct_hash = keccak(
            abi_encode(
                ["bytes32", "bytes32"],
                [_SAFE_MESSAGE_TYPEHASH, keccak(message)],
            )
        )
        wrapped_hash = keccak(b"\x19\x01" + domain_separator + struct_hash)
        # pylint: disable-next=no-value-for-parameter
        signed = Account.unsafe_sign_hash(
            wrapped_hash, private_key=self.crypto.private_key
        )
        return bytes(signed.signature)
