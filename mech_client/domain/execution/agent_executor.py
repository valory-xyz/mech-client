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

"""Agent mode transaction executor (Safe multisig)."""

from typing import Any, Dict

from aea_ledger_ethereum import EthereumApi, EthereumCrypto
from safe_eth.eth import EthereumClient
from web3.contract import Contract as Web3Contract

from mech_client.domain.execution.base import TransactionExecutor
from mech_client.infrastructure.blockchain.safe_client import SafeClient


class AgentExecutor(TransactionExecutor):
    """Transaction executor for agent mode (Safe multisig).

    In agent mode, transactions are executed through a Gnosis Safe multisig
    wallet. This provides enhanced security and enables agent registration
    in the Olas protocol.
    """

    def __init__(
        self,
        ledger_api: EthereumApi,
        crypto: EthereumCrypto,
        safe_address: str,
        ethereum_client: EthereumClient,
    ):
        """
        Initialize agent executor.

        :param ledger_api: Ethereum API for blockchain interactions
        :param crypto: Ethereum crypto object for signing
        :param safe_address: Address of the Safe multisig wallet
        :param ethereum_client: Ethereum client for Safe operations
        """
        super().__init__(ledger_api, crypto.private_key)
        self.safe_address = safe_address
        self.ethereum_client = ethereum_client
        self.safe_client = SafeClient(ethereum_client, safe_address)

    def execute_transaction(
        self,
        contract: Web3Contract,
        method_name: str,
        method_args: Dict[str, Any],
        tx_args: Dict[str, Any],
    ) -> str:
        """
        Execute a contract transaction through Safe multisig.

        Builds the transaction, creates a Safe transaction, signs it,
        and executes it through the Safe.

        :param contract: Contract instance to call
        :param method_name: Name of the contract method
        :param method_args: Arguments for the contract method
        :param tx_args: Transaction arguments (sender, value, gas, etc.)
        :return: Transaction hash
        :raises Exception: If transaction fails
        """
        # Build transaction data
        function = contract.functions[method_name](**method_args)
        transaction = function.build_transaction(
            {
                # pylint: disable=protected-access
                "chainId": int(self.ledger_api._chain_id),
                "gas": 0,
                "nonce": self.safe_client.get_nonce(),
            }
        )

        # Execute through Safe
        value = tx_args.get("value", 0)
        tx_hash = self.safe_client.send_transaction(
            to_address=contract.address,
            tx_data=transaction["data"],
            signer_private_key=self.private_key,
            value=value,
        )

        if tx_hash is None:
            raise Exception("Failed to execute Safe transaction")

        return tx_hash.to_0x_hex()

    def get_sender_address(self) -> str:
        """
        Get the Safe address that will send transactions.

        :return: Safe multisig address
        """
        return self.safe_address

    def get_nonce(self) -> int:
        """
        Get the nonce for the next Safe transaction.

        :return: Safe nonce
        """
        return self.safe_client.get_nonce()
