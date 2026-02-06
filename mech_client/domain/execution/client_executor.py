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

"""Client mode transaction executor (EOA-based)."""

from typing import Any, Dict

from aea.crypto.base import Crypto as EthereumCrypto
from aea_ledger_ethereum import EthereumApi
from web3.contract import Contract as Web3Contract

from mech_client.domain.execution.base import TransactionExecutor


class ClientExecutor(TransactionExecutor):
    """Transaction executor for client mode (EOA-based signing).

    In client mode, transactions are signed directly by the user's private key
    and sent to the network without multisig.
    """

    def __init__(self, ledger_api: EthereumApi, private_key: str):
        """
        Initialize client executor.

        :param ledger_api: Ethereum API for blockchain interactions
        :param private_key: Private key for signing transactions
        """
        super().__init__(ledger_api, private_key)
        # pylint: disable=abstract-class-instantiated
        self.crypto = EthereumCrypto(private_key)

    def execute_transaction(
        self,
        contract: Web3Contract,
        method_name: str,
        method_args: Dict[str, Any],
        tx_args: Dict[str, Any],
    ) -> str:
        """
        Execute a contract transaction in client mode.

        Builds, signs, and sends a transaction using the private key.

        :param contract: Contract instance to call
        :param method_name: Name of the contract method
        :param method_args: Arguments for the contract method
        :param tx_args: Transaction arguments (sender, value, gas, etc.)
        :return: Transaction hash
        :raises Exception: If transaction fails
        """
        raw_transaction = self.ledger_api.build_transaction(
            contract_instance=contract,
            method_name=method_name,
            method_args=method_args,
            tx_args=tx_args,
            raise_on_try=True,
        )
        signed_transaction = self.crypto.sign_transaction(raw_transaction)
        transaction_digest = self.ledger_api.send_signed_transaction(
            signed_transaction,
            raise_on_try=True,
        )
        return transaction_digest

    def get_sender_address(self) -> str:
        """
        Get the EOA address that will send transactions.

        :return: EOA address
        """
        return self.crypto.address

    def get_nonce(self) -> int:
        """
        Get the nonce for the next transaction from the network.

        :return: Transaction nonce
        """
        return self.ledger_api.api.eth.get_transaction_count(self.crypto.address)
