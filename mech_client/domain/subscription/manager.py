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

"""Subscription manager for NVM subscription workflow."""

import logging
from typing import Any, Dict, Optional

from aea_ledger_ethereum import EthereumApi
from web3 import Web3

from mech_client.domain.execution.base import TransactionExecutor
from mech_client.domain.subscription.agreement import AgreementBuilder, AgreementData
from mech_client.domain.subscription.balance_checker import SubscriptionBalanceChecker
from mech_client.domain.subscription.fulfillment import FulfillmentBuilder
from mech_client.infrastructure.blockchain.receipt_waiter import wait_for_receipt
from mech_client.infrastructure.nvm.config import NVMConfig
from mech_client.infrastructure.nvm.contracts import (
    NFTContract,
    NFTSalesTemplateContract,
    SubscriptionProviderContract,
    TokenContract,
)


logger = logging.getLogger(__name__)


class SubscriptionManager:  # pylint: disable=too-few-public-methods,too-many-instance-attributes
    """Manages the NVM subscription purchase workflow."""

    def __init__(  # pylint: disable=too-many-arguments
        self,
        w3: Web3,
        ledger_api: EthereumApi,
        config: NVMConfig,
        sender: str,
        executor: TransactionExecutor,
        agreement_builder: AgreementBuilder,
        fulfillment_builder: FulfillmentBuilder,
        balance_checker: SubscriptionBalanceChecker,
        nft_sales: NFTSalesTemplateContract,
        subscription_provider: SubscriptionProviderContract,
        subscription_nft: NFTContract,
        token_contract: Optional[TokenContract] = None,
    ):
        """
        Initialize the subscription manager.

        :param w3: Web3 instance
        :param ledger_api: Ledger API instance
        :param config: NVM configuration
        :param sender: Sender address
        :param executor: Transaction executor
        :param agreement_builder: Agreement builder
        :param fulfillment_builder: Fulfillment builder
        :param balance_checker: Balance checker
        :param nft_sales: NFT sales template contract
        :param subscription_provider: Subscription provider contract
        :param subscription_nft: Subscription NFT contract
        :param token_contract: Token contract (required for Base)
        """
        self.w3 = w3
        self.ledger_api = ledger_api
        self.config = config
        self.sender = sender
        self.executor = executor
        self.agreement_builder = agreement_builder
        self.fulfillment_builder = fulfillment_builder
        self.balance_checker = balance_checker
        self.nft_sales = nft_sales
        self.subscription_provider = subscription_provider
        self.subscription_nft = subscription_nft
        self.token_contract = token_contract

    def purchase_subscription(self, plan_did: str) -> Dict[str, Any]:
        """
        Execute the complete subscription purchase workflow.

        Workflow:
        1. Check balance
        2. [Base only] Approve USDC token
        3. Create agreement transaction
        4. Fulfill agreement transaction

        :param plan_did: Plan DID to subscribe to
        :return: Result dictionary with status and transaction details
        """
        logger.info(f"Starting subscription purchase for DID: {plan_did}")

        # Step 1: Check balance
        logger.info(f"Checking {self.sender} balance for purchasing subscription")
        self.balance_checker.check()

        # Step 2: Build agreement data
        agreement = self.agreement_builder.build(plan_did)

        # Check NFT balance before purchase
        balance_before = self.subscription_nft.get_balance(
            self.sender, self.config.subscription_id
        )
        logger.info(f"Sender credits before purchase: {balance_before}")

        # Step 3: Token approval (Base only)
        if self.config.requires_token_approval():
            logger.info("Token approval required for Base chain")
            self._approve_token()

        # Step 4: Create agreement
        agreement_tx_hash = self._create_agreement(agreement)

        # Step 5: Fulfill agreement
        fulfillment_tx_hash = self._fulfill_agreement(agreement)

        # Check NFT balance after purchase
        balance_after = self.subscription_nft.get_balance(
            self.sender, self.config.subscription_id
        )
        logger.info(f"Sender credits after purchase: {balance_after}")

        logger.info("Subscription purchased successfully")

        return {
            "status": "success",
            "agreement_id": agreement.agreement_id.hex(),
            "agreement_tx_hash": agreement_tx_hash,
            "fulfillment_tx_hash": fulfillment_tx_hash,
            "credits_before": balance_before,
            "credits_after": balance_after,
        }

    def _approve_token(self) -> None:
        """Approve USDC token for lock payment contract (Base only)."""
        if not self.token_contract:
            raise ValueError("Token contract required for Base chain approval")

        logger.info("Approving USDC token for lock payment contract")

        # Approve total payment amount
        approval_amount = self.config.get_total_payment_amount()

        # Execute approval transaction
        tx_hash = self.executor.execute_transaction(
            contract=self.token_contract.contract,
            method_name="approve",
            method_args={
                "spender": self.w3.to_checksum_address(
                    self.agreement_builder.lock_payment.address
                ),
                "amount": approval_amount,
            },
            tx_args={
                "sender_address": self.sender,
                "value": 0,
                "gas": 60000,
            },
        )

        # Wait for receipt
        receipt = wait_for_receipt(tx_hash, self.ledger_api)

        if receipt["status"] != 1:
            raise RuntimeError(f"Token approval failed. Transaction hash: {tx_hash}")

        logger.info(f"Token approval successful. Tx hash: {tx_hash}")

    def _create_agreement(self, agreement: AgreementData) -> str:
        """
        Create the subscription agreement on-chain.

        :param agreement: Agreement data
        :return: Transaction hash (hex string)
        """
        logger.info("Creating subscription agreement")

        # Prepare amounts [fee, price]
        amounts = [
            int(self.config.plan_fee_nvm),
            int(self.config.plan_price_mechs),
        ]

        # Get transaction value (native token for Gnosis, 0 for Base)
        tx_value = self.config.get_transaction_value()

        # Execute agreement creation transaction
        tx_hash = self.executor.execute_transaction(
            contract=self.nft_sales.contract,
            method_name="createAgreementAndPayEscrow",
            method_args={
                "_id": agreement.agreement_id_seed,
                "_did": agreement.did,
                "_conditionIds": agreement.condition_seeds,
                "_timeLocks": agreement.timelocks,
                "_timeOuts": agreement.timeouts,
                "_accessConsumer": self.sender,
                "_idx": 0,
                "_rewardAddress": agreement.reward_address,
                "_tokenAddress": self.config.token_address,
                "_amounts": amounts,
                "_receivers": agreement.receivers,
            },
            tx_args={
                "sender_address": self.sender,
                "value": tx_value,
                "gas": 600000,
            },
        )

        # Wait for receipt
        receipt = wait_for_receipt(tx_hash, self.ledger_api)

        if receipt["status"] != 1:
            raise RuntimeError(
                f"Agreement creation failed. Transaction hash: {tx_hash}"
            )

        logger.info(f"Agreement created successfully. Tx hash: {tx_hash}")

        return tx_hash

    def _fulfill_agreement(self, agreement: AgreementData) -> str:
        """
        Fulfill the subscription agreement.

        :param agreement: Agreement data
        :return: Transaction hash (hex string)
        """
        logger.info("Fulfilling subscription agreement")

        # Build fulfillment parameters
        fulfillment = self.fulfillment_builder.build(agreement)

        # Execute fulfillment transaction
        tx_hash = self.executor.execute_transaction(
            contract=self.subscription_provider.contract,
            method_name="fulfill",
            method_args={
                "agreementId": "0x" + agreement.agreement_id.hex(),
                "did": agreement.did,
                "fulfillForDelegateParams": fulfillment.fulfill_for_delegate_params,
                "fulfillParams": fulfillment.fulfill_params,
            },
            tx_args={
                "sender_address": self.sender,
                "value": 0,
                "gas": 500000,
            },
        )

        # Wait for receipt
        receipt = wait_for_receipt(tx_hash, self.ledger_api)

        if receipt["status"] != 1:
            raise RuntimeError(
                f"Agreement fulfillment failed. Transaction hash: {tx_hash}"
            )

        logger.info(f"Agreement fulfilled successfully. Tx hash: {tx_hash}")

        return tx_hash
