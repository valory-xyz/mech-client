# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2025 Valory AG
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

"""Gnosis Safe multisig client for agent mode transactions."""

from typing import Optional

from hexbytes import HexBytes
from mech_client.domain.signing import Signer
from safe_eth.eth import EthereumClient  # pylint:disable=import-error
from safe_eth.safe import Safe  # pylint:disable=import-error
from web3.constants import ADDRESS_ZERO

# Headroom applied on top of the inner-call gas estimate when sizing the outer
# execTransaction: the multiplier absorbs estimation variance, and the
# overhead covers Safe plumbing (signature checks, events) plus the EIP-150
# rule capping what the inner call can receive at 63/64 of the remaining gas.
# The overhead scales with the estimate (5%, floored at 250k) so it stays
# proportionate for inner calls approaching the block gas limit.
OUTER_TX_GAS_MULTIPLIER = 1.1
OUTER_TX_GAS_OVERHEAD_FLOOR = 250_000
OUTER_TX_GAS_OVERHEAD_SHARE = 0.05


class SafeClient:
    """Client for interacting with Gnosis Safe multisig wallets.

    Provides methods for building, signing, and executing Safe transactions
    in agent mode. Uses safe-eth-py library for Safe interactions.
    """

    def __init__(self, ethereum_client: EthereumClient, safe_address: str):
        """
        Initialize Safe client.

        :param ethereum_client: Ethereum client instance
        :param safe_address: Address of the Safe multisig wallet
        """
        self.ethereum_client = ethereum_client
        self.safe_address = safe_address
        self._safe: Optional[Safe] = None

    @property
    def safe(self) -> Safe:
        """Get Safe instance (lazy-loaded).

        :return: Safe instance
        """
        if self._safe is None:
            self._safe = Safe(  # pylint:disable=abstract-class-instantiated
                self.safe_address, self.ethereum_client
            )
        return self._safe

    @staticmethod
    def build_pre_validated_signature(owner: str) -> bytes:
        """
        Encode a pre-validated Safe owner signature.

        Format (Safe contracts): ``r`` = owner address left-padded to 32
        bytes, ``s`` = 0, ``v`` = 1. The Safe accepts it whenever the outer
        ``execTransaction`` sender is that owner — no ECDSA over the SafeTx
        hash is needed, so the private key never has to be in-process.

        :param owner: Safe owner address (0x-prefixed) sending the outer tx
        :return: 65-byte pre-validated signature
        :raises ValueError: If ``owner`` is not a valid 20-byte hex address
        """
        try:
            owner_bytes = bytes.fromhex(owner.removeprefix("0x"))
        except ValueError as e:
            raise ValueError(
                f"Invalid Safe owner address from signer: {owner!r} (not hex)"
            ) from e
        if len(owner_bytes) != 20:
            raise ValueError(
                f"Invalid Safe owner address from signer: {owner!r} "
                f"(expected 20 bytes, got {len(owner_bytes)})"
            )
        return b"\x00" * 12 + owner_bytes + b"\x00" * 32 + b"\x01"

    def send_transaction(
        self,
        to_address: str,
        tx_data: str,
        signer: Signer,
        value: int = 0,
    ) -> HexBytes:
        """
        Build and execute a Safe multisig transaction via the signer.

        The SafeTx carries a pre-validated signature for the signer's address
        (which must be a Safe owner), and the outer ``execTransaction`` is
        built unsigned and submitted through ``signer.send_transaction`` —
        signing happens wherever the signer keeps its key.

        Exceptions from building, signing, or executing the transaction
        propagate to the caller instead of being swallowed.

        :param to_address: Destination contract/address
        :param tx_data: Transaction data (hex string starting with 0x)
        :param signer: Signer for the Safe owner EOA sending the outer tx
        :param value: ETH/native token value to send (in wei)
        :return: Transaction hash
        """
        # Estimate the inner call's gas to size the outer execTransaction
        estimated_gas = self.safe.estimate_tx_gas_with_safe(
            to=to_address,
            value=value,
            data=bytes.fromhex(tx_data[2:]),
            operation=0,
        )

        # safe_tx_gas=0 forwards all available gas to the inner call.
        # A non-zero safe_tx_gas makes the outer eth_estimateGas revert
        # for gas-heavy inner calls (EIP-150 63/64 rule).
        safe_tx = self.safe.build_multisig_tx(
            to=to_address,
            value=value,
            data=bytes.fromhex(tx_data[2:]),
            operation=0,
            safe_tx_gas=0,
            base_gas=0,
            gas_price=0,
            gas_token=ADDRESS_ZERO,
            refund_receiver=ADDRESS_ZERO,
        )

        # Pre-validated signature: valid because the outer tx sender is
        # the owner encoded in it.
        safe_tx.signatures = self.build_pre_validated_signature(signer.address)

        # Size the outer gas from the inner estimate; the explicit gas limit
        # skips the outer eth_estimateGas, which fails for gas-heavy inner
        # calls for the same 63/64 reason. The nonce is left for the signer
        # to fill.
        overhead = max(
            OUTER_TX_GAS_OVERHEAD_FLOOR,
            int(estimated_gas * OUTER_TX_GAS_OVERHEAD_SHARE),
        )
        tx_gas = int(estimated_gas * OUTER_TX_GAS_MULTIPLIER) + overhead
        outer_tx = safe_tx.w3_tx.build_transaction(
            {
                "from": signer.address,
                "gas": tx_gas,
                "gasPrice": self.ethereum_client.w3.eth.gas_price,
            }
        )

        tx_hash = signer.send_transaction(outer_tx)
        return HexBytes(tx_hash)

    def get_nonce(self) -> int:
        """
        Get the current nonce for the Safe.

        :return: Current Safe nonce
        """
        return self.safe.retrieve_nonce()

    def estimate_gas(
        self,
        to_address: str,
        tx_data: str,
        value: int = 0,
    ) -> int:
        """
        Estimate gas for a Safe transaction.

        :param to_address: Destination contract/address
        :param tx_data: Transaction data (hex string starting with 0x)
        :param value: ETH/native token value to send (in wei)
        :return: Estimated gas amount
        """
        return self.safe.estimate_tx_gas_with_safe(
            to=to_address,
            value=value,
            data=bytes.fromhex(tx_data[2:]),
            operation=0,
        )
