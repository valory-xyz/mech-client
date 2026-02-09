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

"""Base transaction executor interface."""

from abc import ABC, abstractmethod
from typing import Any, Dict

from aea_ledger_ethereum import EthereumApi
from web3.contract import Contract as Web3Contract


class TransactionExecutor(ABC):
    """Abstract base class for transaction execution strategies.

    Defines the interface for executing transactions in different modes
    (client mode with EOA, agent mode with Safe multisig).
    """

    def __init__(
        self,
        ledger_api: EthereumApi,
        private_key: str,
    ):
        """
        Initialize transaction executor.

        :param ledger_api: Ethereum API for blockchain interactions
        :param private_key: Private key for signing transactions
        """
        self.ledger_api = ledger_api
        self.private_key = private_key

    @abstractmethod
    def execute_transaction(
        self,
        contract: Web3Contract,
        method_name: str,
        method_args: Dict[str, Any],
        tx_args: Dict[str, Any],
    ) -> str:
        """
        Execute a contract transaction.

        :param contract: Contract instance to call
        :param method_name: Name of the contract method
        :param method_args: Arguments for the contract method
        :param tx_args: Transaction arguments (sender, value, gas, etc.)
        :return: Transaction hash
        :raises Exception: If transaction fails
        """

    @abstractmethod
    def execute_transfer(
        self,
        to_address: str,
        amount: int,
        gas: int,
    ) -> str:
        """
        Execute a plain native token transfer.

        :param to_address: Destination address
        :param amount: Amount to transfer in wei
        :param gas: Gas limit for the transaction
        :return: Transaction hash
        :raises Exception: If transaction fails
        """

    @abstractmethod
    def get_sender_address(self) -> str:
        """
        Get the address that will send transactions.

        :return: Sender address (EOA for client mode, Safe for agent mode)
        """

    @abstractmethod
    def get_nonce(self) -> int:
        """
        Get the nonce for the next transaction.

        :return: Transaction nonce
        """
