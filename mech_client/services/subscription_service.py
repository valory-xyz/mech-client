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

"""Subscription service for NVM subscription management."""

from dataclasses import asdict
from typing import Any, Dict, Optional, cast

from aea_ledger_ethereum import EthereumApi, EthereumCrypto
from safe_eth.eth import EthereumClient
from web3 import Web3

from mech_client.domain.execution.factory import ExecutorFactory
from mech_client.domain.subscription import (
    AgreementBuilder,
    FulfillmentBuilder,
    SubscriptionBalanceChecker,
    SubscriptionManager,
)
from mech_client.infrastructure.config.loader import get_mech_config
from mech_client.infrastructure.nvm.config import NVMConfig
from mech_client.infrastructure.nvm.contracts import (
    AgreementManagerContract,
    DIDRegistryContract,
    EscrowPaymentContract,
    LockPaymentContract,
    NFTContract,
    NFTSalesTemplateContract,
    NVMContractFactory,
    NeverminedConfigContract,
    SubscriptionProviderContract,
    TokenContract,
    TransferNFTContract,
)


class SubscriptionService:  # pylint: disable=too-many-instance-attributes,too-few-public-methods
    """Service for managing Nevermined (NVM) subscriptions.

    Orchestrates subscription purchase workflow using the layered architecture:
    - Infrastructure: NVM contracts and configuration
    - Domain: Agreement building, fulfillment, balance checking
    - Execution: Transaction signing and submission
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        chain_config: str,
        crypto: EthereumCrypto,
        agent_mode: bool,
        ethereum_client: Optional[EthereumClient] = None,
        safe_address: Optional[str] = None,
    ):
        """
        Initialize subscription service.

        :param chain_config: Chain configuration name (gnosis, base)
        :param crypto: Ethereum crypto object with private key
        :param agent_mode: True for agent mode (Safe), False for client mode (EOA)
        :param ethereum_client: Ethereum client (required for agent mode)
        :param safe_address: Safe address (required for agent mode)
        """
        self.chain_config = chain_config
        self.crypto = crypto
        self.agent_mode = agent_mode
        self.ethereum_client = ethereum_client
        self.safe_address = safe_address

        # Load mech configuration and create ledger API (pass agent_mode to load RPC from operate config in agent mode)
        mech_config = get_mech_config(chain_config, agent_mode=agent_mode)
        self.ledger_api = EthereumApi(**asdict(mech_config.ledger_config))

        # Load NVM configuration
        self.config = NVMConfig.from_chain(chain_config)

        # Get Web3 instance from ledger API
        self.w3: Web3 = self.ledger_api._api  # pylint: disable=protected-access

        # Get sender address (EOA in client mode, Safe in agent mode)
        if self.agent_mode:
            if not self.safe_address:
                raise ValueError("safe_address is required in agent mode")
            self.sender = self.safe_address
        else:
            self.sender = self.crypto.address

    def purchase_subscription(  # pylint: disable=too-many-locals
        self, plan_did: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Purchase NVM subscription for the chain.

        Executes the complete subscription workflow:
        1. Check balance
        2. [Base only] Approve USDC token
        3. Create agreement transaction
        4. Fulfill agreement transaction

        :param plan_did: Optional plan DID (uses config default if not provided)
        :return: Result dictionary with status and transaction details
        :raises ValueError: If insufficient balance or invalid configuration
        :raises RuntimeError: If transaction fails
        """
        # Use plan DID from config if not provided
        if not plan_did:
            plan_did = self.config.plan_did

        # Create executor
        executor = ExecutorFactory.create(
            ledger_api=self.ledger_api,
            agent_mode=self.agent_mode,
            crypto=self.crypto,
            ethereum_client=self.ethereum_client,
            safe_address=self.safe_address,
        )

        # Create only the NVM contracts required for this chain.
        contract_names = NVMContractFactory.subscription_contract_names(
            include_token=self.config.requires_token_approval()
        )
        contracts = NVMContractFactory.create_all(self.w3, contract_names=contract_names)

        # Cast contracts to specific types
        did_registry = cast(DIDRegistryContract, contracts["did_registry"])
        agreement_manager = cast(
            AgreementManagerContract, contracts["agreement_manager"]
        )
        lock_payment = cast(LockPaymentContract, contracts["lock_payment"])
        transfer_nft = cast(TransferNFTContract, contracts["transfer_nft"])
        escrow_payment = cast(EscrowPaymentContract, contracts["escrow_payment"])
        nevermined_config = cast(
            NeverminedConfigContract, contracts["nevermined_config"]
        )
        nft_sales = cast(NFTSalesTemplateContract, contracts["nft_sales"])
        subscription_provider = cast(
            SubscriptionProviderContract, contracts["subscription_provider"]
        )
        subscription_nft = cast(NFTContract, contracts["nft"])

        # Get token contract for Base chain
        token_contract: Optional[TokenContract] = None
        if self.config.requires_token_approval():
            token_contract = cast(TokenContract, contracts["token"])

        # Create agreement builder
        agreement_builder = AgreementBuilder(
            config=self.config,
            sender=self.sender,
            did_registry=did_registry,
            agreement_manager=agreement_manager,
            lock_payment=lock_payment,
            transfer_nft=transfer_nft,
            escrow_payment=escrow_payment,
            nevermined_config_contract=nevermined_config,
        )

        # Create fulfillment builder
        fulfillment_builder = FulfillmentBuilder(
            config=self.config,
            sender=self.sender,
        )

        # Create balance checker
        balance_checker = SubscriptionBalanceChecker(
            w3=self.w3,
            config=self.config,
            sender=self.sender,
            token_contract=token_contract,
        )

        # Create subscription manager
        manager = SubscriptionManager(
            w3=self.w3,
            ledger_api=self.ledger_api,
            config=self.config,
            sender=self.sender,
            executor=executor,
            agreement_builder=agreement_builder,
            fulfillment_builder=fulfillment_builder,
            balance_checker=balance_checker,
            nft_sales=nft_sales,
            subscription_provider=subscription_provider,
            subscription_nft=subscription_nft,
            token_contract=token_contract,
        )

        # Execute purchase workflow
        result = manager.purchase_subscription(plan_did)

        return result
