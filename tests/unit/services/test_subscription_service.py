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

"""Tests for services.subscription_service."""

from unittest.mock import MagicMock, patch

import pytest


class TestSubscriptionService:
    """Tests for SubscriptionService."""

    @pytest.fixture
    def mock_crypto(self) -> MagicMock:
        """Create mock EthereumCrypto."""
        crypto = MagicMock()
        crypto.address = "0x1234567890123456789012345678901234567890"
        return crypto

    @pytest.fixture
    def mock_ledger_api(self) -> MagicMock:
        """Create mock EthereumApi."""
        ledger_api = MagicMock()
        ledger_api._api = MagicMock()  # Mock Web3 instance
        ledger_api._api.eth.chain_id = 100
        return ledger_api

    @pytest.fixture
    def mock_ethereum_client(self) -> MagicMock:
        """Create mock EthereumClient."""
        return MagicMock()

    @patch("mech_client.services.subscription_service.asdict")
    @patch("mech_client.services.subscription_service.EthereumApi")
    @patch("mech_client.services.subscription_service.get_mech_config")
    @patch("mech_client.services.subscription_service.NVMConfig")
    def test_initialization(
        self,
        mock_config_class: MagicMock,
        mock_get_mech_config: MagicMock,
        mock_ethereum_api_class: MagicMock,
        mock_asdict: MagicMock,
        mock_crypto: MagicMock,
        mock_ledger_api: MagicMock,
    ) -> None:
        """Test service initialization."""
        from mech_client.services.subscription_service import SubscriptionService

        mock_config = MagicMock()
        mock_config_class.from_chain.return_value = mock_config

        mock_mech_config = MagicMock()
        mock_mech_config.ledger_config = MagicMock()
        mock_get_mech_config.return_value = mock_mech_config

        mock_asdict.return_value = {}
        mock_ethereum_api_class.return_value = mock_ledger_api

        service = SubscriptionService(
            chain_config="gnosis",
            crypto=mock_crypto,
            agent_mode=False,
            ethereum_client=None,
            safe_address=None,
        )

        assert service.chain_config == "gnosis"
        assert service.agent_mode is False
        mock_config_class.from_chain.assert_called_once_with("gnosis")
        mock_get_mech_config.assert_called_once_with("gnosis", agent_mode=False)

    @patch("mech_client.services.subscription_service.SubscriptionManager")
    @patch("mech_client.services.subscription_service.SubscriptionBalanceChecker")
    @patch("mech_client.services.subscription_service.FulfillmentBuilder")
    @patch("mech_client.services.subscription_service.AgreementBuilder")
    @patch("mech_client.services.subscription_service.NVMContractFactory")
    @patch("mech_client.services.subscription_service.ExecutorFactory")
    @patch("mech_client.services.subscription_service.asdict")
    @patch("mech_client.services.subscription_service.EthereumApi")
    @patch("mech_client.services.subscription_service.get_mech_config")
    @patch("mech_client.services.subscription_service.NVMConfig")
    def test_purchase_subscription_client_mode(
        self,
        mock_config_class: MagicMock,
        mock_get_mech_config: MagicMock,
        mock_ethereum_api_class: MagicMock,
        mock_asdict: MagicMock,
        mock_executor_factory: MagicMock,
        mock_contract_factory: MagicMock,
        mock_agreement_builder_class: MagicMock,
        mock_fulfillment_builder_class: MagicMock,
        mock_balance_checker_class: MagicMock,
        mock_manager_class: MagicMock,
        mock_crypto: MagicMock,
        mock_ledger_api: MagicMock,
    ) -> None:
        """Test subscription purchase in client mode."""
        from mech_client.services.subscription_service import SubscriptionService

        # Setup mocks
        mock_config = MagicMock()
        mock_config.plan_did = "did:nvm:default"
        mock_config.requires_token_approval.return_value = False
        mock_config_class.from_chain.return_value = mock_config

        mock_mech_config = MagicMock()
        mock_mech_config.ledger_config = MagicMock()
        mock_get_mech_config.return_value = mock_mech_config

        mock_asdict.return_value = {}
        mock_ethereum_api_class.return_value = mock_ledger_api

        mock_executor = MagicMock()
        mock_executor_factory.create.return_value = mock_executor

        mock_contracts = {
            "did_registry": MagicMock(),
            "agreement_manager": MagicMock(),
            "lock_payment": MagicMock(),
            "transfer_nft": MagicMock(),
            "escrow_payment": MagicMock(),
            "nevermined_config": MagicMock(),
            "nft_sales": MagicMock(),
            "subscription_provider": MagicMock(),
            "nft": MagicMock(),
        }
        mock_contract_factory.create_all.return_value = mock_contracts

        mock_manager = MagicMock()
        mock_manager.purchase_subscription.return_value = {
            "status": "success",
            "agreement_id": "0x" + "a" * 64,
            "agreement_tx_hash": "0x" + "b" * 64,
            "fulfillment_tx_hash": "0x" + "c" * 64,
            "credits_before": 0,
            "credits_after": 100,
        }
        mock_manager_class.return_value = mock_manager

        # Create service
        service = SubscriptionService(
            chain_config="gnosis",
            crypto=mock_crypto,
            agent_mode=False,
            ethereum_client=None,
            safe_address=None,
        )

        # Execute
        result = service.purchase_subscription()

        # Verify executor creation
        mock_executor_factory.create.assert_called_once()
        call_kwargs = mock_executor_factory.create.call_args[1]
        assert call_kwargs["agent_mode"] is False
        assert call_kwargs["ethereum_client"] is None
        assert call_kwargs["safe_address"] is None

        # Verify contract factory called
        mock_contract_factory.create_all.assert_called_once()

        # Verify builders created
        mock_agreement_builder_class.assert_called_once()
        mock_fulfillment_builder_class.assert_called_once()
        mock_balance_checker_class.assert_called_once()

        # Verify manager created and called
        mock_manager_class.assert_called_once()
        mock_manager.purchase_subscription.assert_called_once_with("did:nvm:default")

        # Verify result
        assert result["status"] == "success"
        assert result["agreement_id"] == "0x" + "a" * 64

    @patch("mech_client.services.subscription_service.SubscriptionManager")
    @patch("mech_client.services.subscription_service.SubscriptionBalanceChecker")
    @patch("mech_client.services.subscription_service.FulfillmentBuilder")
    @patch("mech_client.services.subscription_service.AgreementBuilder")
    @patch("mech_client.services.subscription_service.NVMContractFactory")
    @patch("mech_client.services.subscription_service.ExecutorFactory")
    @patch("mech_client.services.subscription_service.asdict")
    @patch("mech_client.services.subscription_service.EthereumApi")
    @patch("mech_client.services.subscription_service.get_mech_config")
    @patch("mech_client.services.subscription_service.NVMConfig")
    def test_purchase_subscription_agent_mode(
        self,
        mock_config_class: MagicMock,
        mock_get_mech_config: MagicMock,
        mock_ethereum_api_class: MagicMock,
        mock_asdict: MagicMock,
        mock_executor_factory: MagicMock,
        mock_contract_factory: MagicMock,
        mock_agreement_builder_class: MagicMock,
        mock_fulfillment_builder_class: MagicMock,
        mock_balance_checker_class: MagicMock,
        mock_manager_class: MagicMock,
        mock_crypto: MagicMock,
        mock_ledger_api: MagicMock,
        mock_ethereum_client: MagicMock,
    ) -> None:
        """Test subscription purchase in agent mode."""
        from mech_client.services.subscription_service import SubscriptionService

        # Setup mocks
        mock_config = MagicMock()
        mock_config.plan_did = "did:nvm:default"
        mock_config.requires_token_approval.return_value = False
        mock_config_class.from_chain.return_value = mock_config

        mock_mech_config = MagicMock()
        mock_mech_config.ledger_config = MagicMock()
        mock_get_mech_config.return_value = mock_mech_config

        mock_asdict.return_value = {}
        mock_ethereum_api_class.return_value = mock_ledger_api

        mock_executor = MagicMock()
        mock_executor_factory.create.return_value = mock_executor

        mock_contracts = {
            "did_registry": MagicMock(),
            "agreement_manager": MagicMock(),
            "lock_payment": MagicMock(),
            "transfer_nft": MagicMock(),
            "escrow_payment": MagicMock(),
            "nevermined_config": MagicMock(),
            "nft_sales": MagicMock(),
            "subscription_provider": MagicMock(),
            "nft": MagicMock(),
        }
        mock_contract_factory.create_all.return_value = mock_contracts

        mock_manager = MagicMock()
        mock_manager.purchase_subscription.return_value = {
            "status": "success",
            "agreement_id": "0x" + "a" * 64,
        }
        mock_manager_class.return_value = mock_manager

        # Create service
        service = SubscriptionService(
            chain_config="gnosis",
            crypto=mock_crypto,
            agent_mode=True,
            ethereum_client=mock_ethereum_client,
            safe_address="0x" + "a" * 40,
        )

        # Execute
        result = service.purchase_subscription()

        # Verify executor creation with agent mode parameters
        mock_executor_factory.create.assert_called_once()
        call_kwargs = mock_executor_factory.create.call_args[1]
        assert call_kwargs["agent_mode"] is True
        assert call_kwargs["ethereum_client"] is not None
        assert call_kwargs["safe_address"] == "0x" + "a" * 40

        # Verify result
        assert result["status"] == "success"

    @patch("mech_client.services.subscription_service.SubscriptionManager")
    @patch("mech_client.services.subscription_service.SubscriptionBalanceChecker")
    @patch("mech_client.services.subscription_service.FulfillmentBuilder")
    @patch("mech_client.services.subscription_service.AgreementBuilder")
    @patch("mech_client.services.subscription_service.NVMContractFactory")
    @patch("mech_client.services.subscription_service.ExecutorFactory")
    @patch("mech_client.services.subscription_service.asdict")
    @patch("mech_client.services.subscription_service.EthereumApi")
    @patch("mech_client.services.subscription_service.get_mech_config")
    @patch("mech_client.services.subscription_service.NVMConfig")
    def test_purchase_subscription_custom_plan_did(
        self,
        mock_config_class: MagicMock,
        mock_get_mech_config: MagicMock,
        mock_ethereum_api_class: MagicMock,
        mock_asdict: MagicMock,
        mock_executor_factory: MagicMock,
        mock_contract_factory: MagicMock,
        mock_agreement_builder_class: MagicMock,
        mock_fulfillment_builder_class: MagicMock,
        mock_balance_checker_class: MagicMock,
        mock_manager_class: MagicMock,
        mock_crypto: MagicMock,
        mock_ledger_api: MagicMock,
    ) -> None:
        """Test subscription purchase with custom plan DID."""
        from mech_client.services.subscription_service import SubscriptionService

        # Setup mocks
        mock_config = MagicMock()
        mock_config.plan_did = "did:nvm:default"
        mock_config.requires_token_approval.return_value = False
        mock_config_class.from_chain.return_value = mock_config

        mock_mech_config = MagicMock()
        mock_mech_config.ledger_config = MagicMock()
        mock_get_mech_config.return_value = mock_mech_config

        mock_asdict.return_value = {}
        mock_ethereum_api_class.return_value = mock_ledger_api

        mock_executor = MagicMock()
        mock_executor_factory.create.return_value = mock_executor

        mock_contracts = {
            "did_registry": MagicMock(),
            "agreement_manager": MagicMock(),
            "lock_payment": MagicMock(),
            "transfer_nft": MagicMock(),
            "escrow_payment": MagicMock(),
            "nevermined_config": MagicMock(),
            "nft_sales": MagicMock(),
            "subscription_provider": MagicMock(),
            "nft": MagicMock(),
        }
        mock_contract_factory.create_all.return_value = mock_contracts

        mock_manager = MagicMock()
        mock_manager.purchase_subscription.return_value = {"status": "success"}
        mock_manager_class.return_value = mock_manager

        # Create service
        service = SubscriptionService(
            chain_config="gnosis",
            crypto=mock_crypto,
            agent_mode=False,
            ethereum_client=None,
            safe_address=None,
        )

        # Execute with custom plan DID
        custom_plan = "did:nvm:custom123"
        service.purchase_subscription(plan_did=custom_plan)

        # Verify manager called with custom plan DID
        mock_manager.purchase_subscription.assert_called_once_with(custom_plan)
