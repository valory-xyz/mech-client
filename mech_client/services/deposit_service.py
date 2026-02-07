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

"""Deposit service for managing prepaid balances."""

from typing import Optional

from aea_ledger_ethereum import EthereumCrypto
from safe_eth.eth import EthereumClient

from mech_client.domain.payment import PaymentStrategyFactory
from mech_client.infrastructure.blockchain.abi_loader import get_abi
from mech_client.infrastructure.blockchain.contracts import get_contract
from mech_client.infrastructure.blockchain.receipt_waiter import wait_for_receipt
from mech_client.infrastructure.config import PaymentType
from mech_client.services.base_service import BaseTransactionService


class DepositService(BaseTransactionService):  # pylint: disable=too-many-instance-attributes
    """Service for managing prepaid balance deposits.

    Provides operations for depositing native tokens and ERC20 tokens
    into prepaid balances on the marketplace.
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        chain_config: str,
        agent_mode: bool,
        crypto: EthereumCrypto,
        safe_address: Optional[str] = None,
        ethereum_client: Optional[EthereumClient] = None,
    ):
        """
        Initialize deposit service.

        :param chain_config: Chain configuration name (gnosis, base, etc.)
        :param agent_mode: True for agent mode (Safe), False for client mode (EOA)
        :param crypto: Ethereum crypto object for signing
        :param safe_address: Safe address (required for agent mode)
        :param ethereum_client: Ethereum client (required for agent mode)
        """
        super().__init__(
            chain_config=chain_config,
            agent_mode=agent_mode,
            crypto=crypto,
            safe_address=safe_address,
            ethereum_client=ethereum_client,
        )

    def deposit_native(self, amount: int) -> str:
        """
        Deposit native tokens into prepaid balance.

        :param amount: Amount to deposit in wei
        :return: Transaction hash
        :raises ValueError: If insufficient balance or chain doesn't support deposits
        """
        # Create native payment strategy
        payment_strategy = PaymentStrategyFactory.create(
            payment_type=PaymentType.NATIVE,
            ledger_api=self.ledger_api,
            chain_id=self.mech_config.ledger_config.chain_id,
        )

        # Check balance
        sender = self.executor.get_sender_address()
        if not payment_strategy.check_balance(sender, amount):
            raise ValueError(
                f"Insufficient native token balance for deposit. Amount: {amount}"
            )

        # Get balance tracker contract
        balance_tracker_address = payment_strategy.get_balance_tracker_address()
        abi = get_abi("BalanceTrackerFixedPriceNative.json")
        balance_tracker = get_contract(balance_tracker_address, abi, self.ledger_api)

        # Execute deposit transaction
        tx_args = {
            "sender_address": sender,
            "value": amount,
            "gas": self.mech_config.gas_limit,
        }

        tx_hash = self.executor.execute_transaction(
            contract=balance_tracker,
            method_name="deposit",
            method_args={},
            tx_args=tx_args,
        )

        # Wait for receipt
        wait_for_receipt(tx_hash, self.ledger_api)

        print(f"✓ Native deposit successful: {amount} wei")
        # Format with the expected {transaction_digest} placeholder
        tx_url = self.mech_config.transaction_url.format(transaction_digest=tx_hash)
        print(f"  Transaction: {tx_url}")

        return tx_hash

    def deposit_token(self, amount: int, token_type: str = "olas") -> str:  # nosec B107
        """
        Deposit ERC20 tokens into prepaid balance.

        :param amount: Amount to deposit in token's smallest unit
        :param token_type: Token type ("olas" or "usdc")
        :return: Transaction hash
        :raises ValueError: If insufficient balance or chain doesn't support token
        """
        # Determine payment type
        if token_type == "olas":  # nosec B105
            payment_type = PaymentType.TOKEN
        elif token_type == "usdc":  # nosec B105
            payment_type = PaymentType.USDC_TOKEN
        else:
            raise ValueError(f"Unknown token type: {token_type}")

        # Create token payment strategy
        payment_strategy = PaymentStrategyFactory.create(
            payment_type=payment_type,
            ledger_api=self.ledger_api,
            chain_id=self.mech_config.ledger_config.chain_id,
            crypto=self.crypto,
        )

        # Check balance
        sender = self.executor.get_sender_address()
        if not payment_strategy.check_balance(sender, amount):
            raise ValueError(
                f"Insufficient {token_type.upper()} token balance. Amount: {amount}"
            )

        # Get balance tracker address
        balance_tracker_address = payment_strategy.get_balance_tracker_address()

        # Approve tokens
        print(f"Approving {token_type.upper()} tokens...")
        # Returns None if approval not needed, tx hash otherwise
        # pylint: disable=assignment-from-none
        approve_tx = payment_strategy.approve_if_needed(
            payer_address=sender,
            spender_address=balance_tracker_address,
            amount=amount,
            private_key=self.private_key,
        )
        if approve_tx:
            wait_for_receipt(approve_tx, self.ledger_api)
            print("✓ Token approval successful")

        # Deposit tokens
        abi = get_abi("BalanceTrackerFixedPriceToken.json")
        balance_tracker = get_contract(balance_tracker_address, abi, self.ledger_api)

        tx_args = {
            "sender_address": sender,
            "value": 0,
            "gas": self.mech_config.gas_limit,
        }

        method_args = {
            "amount": amount,
        }

        tx_hash = self.executor.execute_transaction(
            contract=balance_tracker,
            method_name="deposit",
            method_args=method_args,
            tx_args=tx_args,
        )

        # Wait for receipt
        wait_for_receipt(tx_hash, self.ledger_api)

        print(f"✓ {token_type.upper()} deposit successful: {amount}")
        # Format with the expected {transaction_digest} placeholder
        tx_url = self.mech_config.transaction_url.format(transaction_digest=tx_hash)
        print(f"  Transaction: {tx_url}")

        return tx_hash

    def check_balance(self, requester_address: str, payment_type: PaymentType) -> int:
        """
        Check prepaid balance for a requester.

        :param requester_address: Address to check balance for
        :param payment_type: Payment type to check
        :return: Prepaid balance amount
        """
        payment_strategy = PaymentStrategyFactory.create(
            payment_type=payment_type,
            ledger_api=self.ledger_api,
            chain_id=self.mech_config.ledger_config.chain_id,
        )

        balance_tracker_address = payment_strategy.get_balance_tracker_address()
        return payment_strategy.check_prepaid_balance(
            requester_address, balance_tracker_address
        )
