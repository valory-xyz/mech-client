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

"""Tests for domain.subscription.manager."""

from unittest.mock import MagicMock, patch

import pytest

from mech_client.domain.subscription.agreement import AgreementData
from mech_client.domain.subscription.manager import SubscriptionManager


class TestSubscriptionManager:
    """Tests for SubscriptionManager."""

    @pytest.fixture
    def mock_w3(self) -> MagicMock:
        """Create mock Web3 instance."""
        w3 = MagicMock()
        w3.eth.wait_for_transaction_receipt.return_value = {"status": 1}
        return w3

    @pytest.fixture
    def mock_ledger_api(self) -> MagicMock:
        """Create mock EthereumApi."""
        return MagicMock()

    @pytest.fixture
    def mock_config(self) -> MagicMock:
        """Create mock NVM configuration."""
        config = MagicMock()
        config.requires_token_approval.return_value = False
        config.get_transaction_value.return_value = 1000000
        config.get_total_payment_amount.return_value = 1000000
        config.plan_fee_nvm = "500000"
        config.plan_price_mechs = "500000"
        config.token_address = "0x0000000000000000000000000000000000000000"  # nosec
        config.subscription_id = "1"
        return config

    @pytest.fixture
    def mock_executor(self) -> MagicMock:
        """Create mock transaction executor."""
        executor = MagicMock()
        executor.execute_transaction.return_value = "0xabcd1234"
        return executor

    @pytest.fixture
    def mock_agreement_builder(self) -> MagicMock:
        """Create mock agreement builder."""
        builder = MagicMock()
        agreement_data = MagicMock(spec=AgreementData)
        agreement_data.agreement_id = bytes.fromhex("a" * 64)
        agreement_data.agreement_id_seed = bytes.fromhex("b" * 64)
        agreement_data.did = "did:nvm:test"
        agreement_data.condition_seeds = [bytes.fromhex("c" * 64)] * 3
        agreement_data.timelocks = [0, 0, 0]
        agreement_data.timeouts = [0, 0, 0]
        agreement_data.reward_address = "0x" + "1" * 40
        agreement_data.receivers = ["0x" + "2" * 40]
        builder.build.return_value = agreement_data
        builder.lock_payment.address = "0x" + "3" * 40
        return builder

    @pytest.fixture
    def mock_fulfillment_builder(self) -> MagicMock:
        """Create mock fulfillment builder."""
        builder = MagicMock()
        fulfillment_data = MagicMock()
        fulfillment_data.fulfill_for_delegate_params = (
            "0x" + "4" * 40,
            "0x" + "5" * 40,
            100,
            "0x" + "c" * 64,
            "0x" + "6" * 40,
            False,
            0,
        )
        fulfillment_data.fulfill_params = (
            [500000, 500000],
            ["0x" + "2" * 40],
            "0x" + "7" * 40,
            "0x" + "8" * 40,
        )
        builder.build.return_value = fulfillment_data
        return builder

    @pytest.fixture
    def mock_balance_checker(self) -> MagicMock:
        """Create mock balance checker."""
        checker = MagicMock()
        checker.check.return_value = None  # No exception = balance OK
        return checker

    @pytest.fixture
    def mock_contracts(self) -> dict:
        """Create mock NVM contracts."""
        nft_sales = MagicMock()
        nft_sales.contract = MagicMock()

        subscription_provider = MagicMock()
        subscription_provider.contract = MagicMock()

        subscription_nft = MagicMock()
        subscription_nft.get_balance.side_effect = [0, 100]  # before, after

        return {
            "nft_sales": nft_sales,
            "subscription_provider": subscription_provider,
            "subscription_nft": subscription_nft,
        }

    @pytest.fixture
    def manager(
        self,
        mock_w3: MagicMock,
        mock_ledger_api: MagicMock,
        mock_config: MagicMock,
        mock_executor: MagicMock,
        mock_agreement_builder: MagicMock,
        mock_fulfillment_builder: MagicMock,
        mock_balance_checker: MagicMock,
        mock_contracts: dict,
    ) -> SubscriptionManager:
        """Create SubscriptionManager instance."""
        return SubscriptionManager(
            w3=mock_w3,
            ledger_api=mock_ledger_api,
            config=mock_config,
            sender="0x1234567890123456789012345678901234567890",
            executor=mock_executor,
            agreement_builder=mock_agreement_builder,
            fulfillment_builder=mock_fulfillment_builder,
            balance_checker=mock_balance_checker,
            nft_sales=mock_contracts["nft_sales"],
            subscription_provider=mock_contracts["subscription_provider"],
            subscription_nft=mock_contracts["subscription_nft"],
            token_contract=None,
        )

    def test_purchase_subscription_success_gnosis(
        self,
        manager: SubscriptionManager,
        mock_balance_checker: MagicMock,
        mock_agreement_builder: MagicMock,
        mock_fulfillment_builder: MagicMock,
        mock_executor: MagicMock,
        mock_contracts: dict,
    ) -> None:
        """Test successful subscription purchase on Gnosis (no token approval)."""
        plan_did = "did:nvm:test123"

        with patch(
            "mech_client.domain.subscription.manager.wait_for_receipt",
            return_value={"status": 1},
        ) as mock_wait_for_receipt:
            result = manager.purchase_subscription(plan_did)

        # Verify workflow steps
        mock_balance_checker.check.assert_called_once()
        mock_agreement_builder.build.assert_called_once_with(plan_did)
        mock_fulfillment_builder.build.assert_called_once()

        # Verify transactions (2 for Gnosis: create + fulfill)
        assert mock_executor.execute_transaction.call_count == 2

        # Verify agreement creation uses legacy-compatible method signature
        create_call = mock_executor.execute_transaction.call_args_list[0]
        assert create_call[1]["method_name"] == "createAgreementAndPayEscrow"
        assert create_call[1]["method_args"]["_accessConsumer"] == manager.sender
        assert create_call[1]["tx_args"]["sender_address"] == manager.sender

        # Verify fulfill call uses ABI-compatible argument names
        fulfill_call = mock_executor.execute_transaction.call_args_list[1]
        assert fulfill_call[1]["method_name"] == "fulfill"
        assert "agreementId" in fulfill_call[1]["method_args"]
        assert "did" in fulfill_call[1]["method_args"]
        assert "fulfillForDelegateParams" in fulfill_call[1]["method_args"]
        assert "fulfillParams" in fulfill_call[1]["method_args"]
        assert fulfill_call[1]["tx_args"]["sender_address"] == manager.sender

        # Verify receipt waiting (2 for Gnosis: create + fulfill)
        assert mock_wait_for_receipt.call_count == 2

        # Verify NFT balance checks
        assert mock_contracts["subscription_nft"].get_balance.call_count == 2

        # Verify result structure
        assert result["status"] == "success"
        assert "agreement_id" in result
        assert "agreement_tx_hash" in result
        assert "fulfillment_tx_hash" in result
        assert result["credits_before"] == 0
        assert result["credits_after"] == 100

    def test_purchase_subscription_success_base(
        self,
        mock_w3: MagicMock,
        mock_config: MagicMock,
        mock_executor: MagicMock,
        mock_agreement_builder: MagicMock,
        mock_fulfillment_builder: MagicMock,
        mock_balance_checker: MagicMock,
        mock_contracts: dict,
    ) -> None:
        """Test successful subscription purchase on Base (with token approval)."""
        # Configure for Base (requires token approval)
        mock_config.requires_token_approval.return_value = True
        mock_config.get_transaction_value.return_value = 0  # Base pays with USDC

        mock_token_contract = MagicMock()
        mock_token_contract.contract = MagicMock()

        manager = SubscriptionManager(
            w3=mock_w3,
            ledger_api=MagicMock(),
            config=mock_config,
            sender="0x1234567890123456789012345678901234567890",
            executor=mock_executor,
            agreement_builder=mock_agreement_builder,
            fulfillment_builder=mock_fulfillment_builder,
            balance_checker=mock_balance_checker,
            nft_sales=mock_contracts["nft_sales"],
            subscription_provider=mock_contracts["subscription_provider"],
            subscription_nft=mock_contracts["subscription_nft"],
            token_contract=mock_token_contract,
        )

        plan_did = "did:nvm:test456"
        with patch(
            "mech_client.domain.subscription.manager.wait_for_receipt",
            return_value={"status": 1},
        ) as mock_wait_for_receipt:
            result = manager.purchase_subscription(plan_did)

        # Verify transactions (3 for Base: approve + create + fulfill)
        assert mock_executor.execute_transaction.call_count == 3
        assert mock_wait_for_receipt.call_count == 3

        # Verify approval was called
        approve_call = mock_executor.execute_transaction.call_args_list[0]
        assert approve_call[1]["method_name"] == "approve"

        # Verify agreement creation uses legacy-compatible method signature
        create_call = mock_executor.execute_transaction.call_args_list[1]
        assert create_call[1]["method_name"] == "createAgreementAndPayEscrow"
        assert create_call[1]["method_args"]["_accessConsumer"] == manager.sender
        assert create_call[1]["tx_args"]["sender_address"] == manager.sender

        # Verify fulfill call uses ABI-compatible argument names
        fulfill_call = mock_executor.execute_transaction.call_args_list[2]
        assert fulfill_call[1]["method_name"] == "fulfill"
        assert "agreementId" in fulfill_call[1]["method_args"]
        assert "did" in fulfill_call[1]["method_args"]
        assert "fulfillForDelegateParams" in fulfill_call[1]["method_args"]
        assert "fulfillParams" in fulfill_call[1]["method_args"]
        assert fulfill_call[1]["tx_args"]["sender_address"] == manager.sender

        # Verify result
        assert result["status"] == "success"

    def test_purchase_subscription_balance_check_failure(
        self,
        manager: SubscriptionManager,
        mock_balance_checker: MagicMock,
    ) -> None:
        """Test subscription purchase fails on insufficient balance."""
        mock_balance_checker.check.side_effect = ValueError("Insufficient balance")

        with pytest.raises(ValueError, match="Insufficient balance"):
            manager.purchase_subscription("did:nvm:test")

    def test_purchase_subscription_missing_token_contract_base(
        self,
        mock_w3: MagicMock,
        mock_config: MagicMock,
        mock_executor: MagicMock,
        mock_agreement_builder: MagicMock,
        mock_fulfillment_builder: MagicMock,
        mock_balance_checker: MagicMock,
        mock_contracts: dict,
    ) -> None:
        """Test subscription purchase fails if token contract missing on Base."""
        mock_config.requires_token_approval.return_value = True

        manager = SubscriptionManager(
            w3=mock_w3,
            ledger_api=MagicMock(),
            config=mock_config,
            sender="0x1234567890123456789012345678901234567890",
            executor=mock_executor,
            agreement_builder=mock_agreement_builder,
            fulfillment_builder=mock_fulfillment_builder,
            balance_checker=mock_balance_checker,
            nft_sales=mock_contracts["nft_sales"],
            subscription_provider=mock_contracts["subscription_provider"],
            subscription_nft=mock_contracts["subscription_nft"],
            token_contract=None,  # Missing token contract
        )

        with pytest.raises(ValueError, match="Token contract required"):
            manager.purchase_subscription("did:nvm:test")

    def test_purchase_subscription_agreement_creation_failure(
        self,
        manager: SubscriptionManager,
    ) -> None:
        """Test subscription purchase fails if agreement creation fails."""
        with patch(
            "mech_client.domain.subscription.manager.wait_for_receipt",
            return_value={"status": 0},
        ):
            with pytest.raises(RuntimeError, match="Agreement creation failed"):
                manager.purchase_subscription("did:nvm:test")

    def test_approve_token_gnosis_skipped(
        self,
        manager: SubscriptionManager,
        mock_executor: MagicMock,
    ) -> None:
        """Test token approval is skipped on Gnosis."""
        with patch(
            "mech_client.domain.subscription.manager.wait_for_receipt",
            return_value={"status": 1},
        ):
            manager.purchase_subscription("did:nvm:test")

        # Verify no approval transaction (only create + fulfill)
        assert mock_executor.execute_transaction.call_count == 2
        for call in mock_executor.execute_transaction.call_args_list:
            assert call[1]["method_name"] != "approve"
