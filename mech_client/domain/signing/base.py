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

        Used by the client-mode offchain marketplace flow: the EOA is the
        requester of record, and the marketplace verifier recovers with
        plain ``ecrecover(digest, v, r, s)`` — i.e. the digest must be
        signed directly (``eth_account``'s ``unsafe_sign_hash`` semantics),
        NOT wrapped in an EIP-191 personal-message prefix. ``v`` may be
        ``{0, 1}`` or ``{27, 28}``; the contract normalizes both.

        :param message: Message bytes to sign (32-byte digest for mech requests)
        """

    def sign_safe_message(
        self, safe_address: str, chain_id: int, message: bytes
    ) -> bytes:
        """Return a 65-byte ECDSA signature over the Safe-wrapped ``message``.

        Used by the agent-mode offchain marketplace flow, where the requester
        of record is a Safe multisig (not the signing EOA). The marketplace
        verifies via ``Safe.isValidSignature(digest, sig)``, which on Safe
        v1.3.0+ with the standard ``CompatibilityFallbackHandler`` rehashes
        the raw ``digest`` into an EIP-712 ``SafeMessage`` and checks that
        the sig recovers to an owner over the wrapped hash. A raw
        ``ecrecover`` signature over ``digest`` fails on-chain with
        ``GS026``; the signature MUST be produced over::

            wrappedHash = keccak256(
                0x1901
                || keccak256(abi.encode(DOMAIN_TYPEHASH, chainId, safe))
                || keccak256(abi.encode(SAFE_MSG_TYPEHASH, keccak256(abi.encode(message))))
            )

        Implementations MUST compute ``wrappedHash`` locally (no RPC call
        to ``Safe.getMessageHash``) and sign it raw (``v`` in ``{27, 28}``).
        The signer must be an owner of ``safe_address``.

        ``message`` MUST be exactly 32 bytes. Callers pass the request-id
        digest; the wrapping formula's shortcut ``keccak256(message)`` only
        equals ``keccak256(abi.encode(bytes32, message))`` at 32 bytes, so
        any other length silently signs a hash the fallback handler will
        not accept. Implementations MUST reject non-32-byte inputs.

        This is a required protocol member. Downstream implementers of
        :class:`Signer` (e.g. Pearl BYOA agents) must add this method to
        remain compatible with agent-mode offchain requests. Existing
        :meth:`sign_message` is unchanged and continues to serve client mode.

        Domain assumption: Safe v1.3.0+ (v1.3.0 and v1.4.1 share the
        ``EIP712Domain(uint256 chainId,address verifyingContract)``
        typehash and the same ``SafeMessage`` wrapping). ``mechx setup``
        deploys the canonical Safe v1.3.0 singleton, so this method
        targets that domain. Pre-v1.3.0 Safes (v1.2.0 and earlier) use a
        domain typehash without ``chainId`` and are not supported.

        The Safe's signature threshold must be 1 for this single-owner
        signature to validate. Safes with threshold > 1 will reject the
        signature via ``checkNSignatures`` (a distinct failure mode from
        ``GS026``).

        :param safe_address: Checksummed Safe address (verifyingContract in
            the EIP-712 domain)
        :param chain_id: Chain ID of the network the Safe is deployed on
        :param message: 32-byte digest to wrap and sign (the mech
            request-id digest)
        """
