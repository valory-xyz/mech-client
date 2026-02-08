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
from safe_eth.eth import EthereumClient  # pylint:disable=import-error
from safe_eth.safe import Safe  # pylint:disable=import-error
from web3.constants import ADDRESS_ZERO


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

    def send_transaction(  # pylint: disable=too-many-arguments
        self,
        to_address: str,
        tx_data: str,
        signer_private_key: str,
        value: int = 0,
    ) -> Optional[HexBytes]:
        """
        Build, sign, and execute a Safe multisig transaction.

        :param to_address: Destination contract/address
        :param tx_data: Transaction data (hex string starting with 0x)
        :param signer_private_key: Private key for signing
        :param value: ETH/native token value to send (in wei)
        :return: Transaction hash if successful, None otherwise
        """
        try:
            # Estimate gas for the Safe transaction
            estimated_gas = self.safe.estimate_tx_gas_with_safe(
                to=to_address,
                value=value,
                data=bytes.fromhex(tx_data[2:]),
                operation=0,
            )

            # Build Safe multisig transaction
            safe_tx = self.safe.build_multisig_tx(
                to=to_address,
                value=value,
                data=bytes.fromhex(tx_data[2:]),
                operation=0,
                safe_tx_gas=estimated_gas,
                base_gas=0,
                gas_price=0,
                gas_token=ADDRESS_ZERO,
                refund_receiver=ADDRESS_ZERO,
            )

            # Sign and execute
            safe_tx.sign(signer_private_key)
            tx_hash, _ = safe_tx.execute(signer_private_key)
            return tx_hash

        except Exception as e:  # pylint: disable=broad-except
            print(f"Exception while sending Safe transaction: {e}")
            return None

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
