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

from mech_client.domain.execution.base import TransactionExecutor
from web3.contract import Contract as Web3Contract


class ClientExecutor(TransactionExecutor):
    """Transaction executor for client mode (EOA-based signing).

    In client mode, transactions are built locally and handed to the signer,
    which signs them with the EOA key (locally or in an external signer
    service) and broadcasts them without multisig.
    """

    def execute_transaction(
        self,
        contract: Web3Contract,
        method_name: str,
        method_args: Dict[str, Any],
        tx_args: Dict[str, Any],
    ) -> str:
        """
        Execute a contract transaction in client mode.

        Builds an unsigned transaction and submits it through the signer.

        Propagates exceptions from ``ledger_api`` (``raise_on_try=True``)
        when build fails, and from the signer when sign or send fails.

        :param contract: Contract instance to call
        :param method_name: Name of the contract method
        :param method_args: Arguments for the contract method
        :param tx_args: Transaction arguments (sender, value, gas, etc.)
        :return: Transaction hash
        """
        raw_transaction = self.ledger_api.build_transaction(
            contract_instance=contract,
            method_name=method_name,
            method_args=method_args,
            tx_args=tx_args,
            raise_on_try=True,
        )
        return self.signer.send_transaction(raw_transaction)

    def execute_transfer(
        self,
        to_address: str,
        amount: int,
        gas: int,
    ) -> str:
        """
        Execute a plain native token transfer in client mode.

        Propagates exceptions from the signer when sign or send fails.

        :param to_address: Destination address
        :param amount: Amount to transfer in wei
        :param gas: Gas limit for the transaction
        :return: Transaction hash
        """
        raw_transaction = self.ledger_api.get_transfer_transaction(
            sender_address=self.signer.address,
            destination_address=to_address,
            amount=amount,
            tx_fee=gas,
            tx_nonce="0x",
        )
        return self.signer.send_transaction(raw_transaction)

    def get_sender_address(self) -> str:
        """
        Get the EOA address that will send transactions.

        :return: EOA address
        """
        return self.signer.address

    def get_nonce(self) -> int:
        """
        Get the nonce for the next transaction from the network.

        :return: Transaction nonce
        """
        return self.ledger_api.api.eth.get_transaction_count(self.signer.address)
