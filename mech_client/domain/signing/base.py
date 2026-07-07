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

"""Signer protocol for externalized transaction and message signing."""

from typing import Any, Dict, Protocol, runtime_checkable


@runtime_checkable
class Signer(Protocol):
    """Protocol for signing EOA transactions and messages.

    Implementations own the key material. mech-client never sees the raw
    private key: it hands over unsigned transactions (or digests) and gets
    back transaction hashes (or signatures). This enables setups where key
    custody lives in a separate signer service (e.g. Pearl BYOA agents) —
    implement this protocol against that service's API and pass the instance
    as ``signer=`` to ``MarketplaceService`` / ``DepositService``.

    The default implementation is
    :class:`~mech_client.domain.signing.LocalSigner`, which wraps a local
    private key (``EthereumCrypto``) and preserves the historic behavior.
    """

    @property
    def address(self) -> str:
        """The checksummed EOA address this signer signs for."""

    def send_transaction(self, unsigned_tx: Dict[str, Any]) -> str:
        """Sign and broadcast an EOA transaction; return the tx hash.

        ``unsigned_tx`` is a web3-style transaction dict (``chainId``, ``to``,
        ``value``, ``data``, and usually ``gas``/fee fields). The
        implementation must fill ``nonce`` — and any other missing fields such
        as ``gas`` or gas price — if absent. Returns the transaction hash as a
        0x-prefixed hex string.

        :param unsigned_tx: Unsigned transaction dict
        """

    def sign_message(self, message: bytes) -> bytes:
        """Return a 65-byte ECDSA signature (r ‖ s ‖ v) over ``message``.

        The mech marketplace flow passes the raw 32-byte request-id digest
        here, and the on-chain verifier recovers it with plain
        ``ecrecover(digest, v, r, s)`` — i.e. the digest must be signed
        directly (``eth_account``'s ``unsafe_sign_hash`` semantics), NOT
        wrapped in an EIP-191 personal-message prefix. ``v`` may be
        ``{0, 1}`` or ``{27, 28}``; the contract normalizes both.

        :param message: Message bytes to sign (32-byte digest for mech requests)
        """
