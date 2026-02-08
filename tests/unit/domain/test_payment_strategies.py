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

"""Tests for domain.payment strategies."""

from unittest.mock import MagicMock, patch

import pytest

from mech_client.domain.payment.factory import PaymentStrategyFactory
from mech_client.domain.payment.native import NativePaymentStrategy
from mech_client.domain.payment.nvm import NVMPaymentStrategy
from mech_client.domain.payment.token import TokenPaymentStrategy
from mech_client.infrastructure.config import PaymentType


class TestNativePaymentStrategy:
    """Tests for NativePaymentStrategy."""

    @pytest.fixture
    def strategy(self, mock_ledger_api: MagicMock) -> NativePaymentStrategy:
        """Create native payment strategy instance."""
        return NativePaymentStrategy(
            ledger_api=mock_ledger_api,
            payment_type=PaymentType.NATIVE,
            chain_id=100,  # Gnosis
        )

    def test_initialization(self, strategy: NativePaymentStrategy) -> None:
        """Test strategy initialization."""
        assert strategy.payment_type == PaymentType.NATIVE
        assert strategy.chain_id == 100

    def test_check_balance_sufficient(
        self, strategy: NativePaymentStrategy, mock_ledger_api: MagicMock
    ) -> None:
        """Test balance check with sufficient balance."""
        mock_ledger_api.get_balance.return_value = 10**18  # 1 ETH
        payer_address = "0x1234567890123456789012345678901234567890"

        result = strategy.check_balance(payer_address, amount=10**17)
        assert result is True
        mock_ledger_api.get_balance.assert_called_once_with(payer_address)

    def test_check_balance_insufficient(
        self, strategy: NativePaymentStrategy, mock_ledger_api: MagicMock
    ) -> None:
        """Test balance check with insufficient balance."""
        mock_ledger_api.get_balance.return_value = 10**17  # 0.1 ETH
        payer_address = "0x1234567890123456789012345678901234567890"

        result = strategy.check_balance(payer_address, amount=10**18)
        assert result is False

    def test_approve_if_needed_returns_none(
        self, strategy: NativePaymentStrategy
    ) -> None:
        """Test that native payments don't need approval."""
        result = strategy.approve_if_needed(
            payer_address="0x1234567890123456789012345678901234567890",
            spender_address="0x" + "a" * 40,
            amount=10**18,
        )
        assert result is None


class TestTokenPaymentStrategy:
    """Tests for TokenPaymentStrategy."""

    @pytest.fixture
    def strategy(self, mock_ledger_api: MagicMock) -> TokenPaymentStrategy:
        """Create token payment strategy instance."""
        return TokenPaymentStrategy(
            ledger_api=mock_ledger_api,
            payment_type=PaymentType.OLAS_TOKEN,
            chain_id=100,  # Gnosis
        )

    def test_initialization(self, strategy: TokenPaymentStrategy) -> None:
        """Test strategy initialization."""
        assert strategy.payment_type == PaymentType.OLAS_TOKEN
        assert strategy.chain_id == 100

    @patch("mech_client.domain.payment.token.get_contract")
    @patch("mech_client.domain.payment.token.get_abi")
    def test_check_balance_sufficient(
        self,
        mock_get_abi: MagicMock,
        mock_get_contract: MagicMock,
        strategy: TokenPaymentStrategy,
        mock_ledger_api: MagicMock,
        mock_web3_contract: MagicMock,
    ) -> None:
        """Test balance check with sufficient token balance."""
        mock_get_contract.return_value = mock_web3_contract
        mock_web3_contract.functions.balanceOf.return_value.call.return_value = (
            10**18
        )
        payer_address = "0x1234567890123456789012345678901234567890"

        result = strategy.check_balance(payer_address, amount=10**17)
        assert result is True

    @patch("mech_client.domain.payment.token.get_contract")
    @patch("mech_client.domain.payment.token.get_abi")
    def test_check_balance_insufficient(
        self,
        mock_get_abi: MagicMock,
        mock_get_contract: MagicMock,
        strategy: TokenPaymentStrategy,
        mock_web3_contract: MagicMock,
    ) -> None:
        """Test balance check with insufficient token balance."""
        mock_get_contract.return_value = mock_web3_contract
        mock_web3_contract.functions.balanceOf.return_value.call.return_value = (
            10**17
        )
        payer_address = "0x1234567890123456789012345678901234567890"

        result = strategy.check_balance(payer_address, amount=10**18)
        assert result is False

    @patch("mech_client.domain.payment.token.get_contract")
    @patch("mech_client.domain.payment.token.get_abi")
    def test_approve_if_needed_with_executor(
        self,
        mock_get_abi: MagicMock,
        mock_get_contract: MagicMock,
        strategy: TokenPaymentStrategy,
        mock_web3_contract: MagicMock,
    ) -> None:
        """Test approval with executor (agent mode and client mode)."""
        mock_get_contract.return_value = mock_web3_contract
        mock_executor = MagicMock()
        mock_executor.execute_transaction.return_value = "0xtxhash"

        payer_address = "0x1234567890123456789012345678901234567890"
        spender_address = "0x" + "a" * 40
        amount = 10**18

        result = strategy.approve_if_needed(
            payer_address=payer_address,
            spender_address=spender_address,
            amount=amount,
            executor=mock_executor,
        )

        assert result == "0xtxhash"
        mock_executor.execute_transaction.assert_called_once()
        call_args = mock_executor.execute_transaction.call_args[1]
        assert call_args["contract"] == mock_web3_contract
        assert call_args["method_name"] == "approve"
        assert call_args["method_args"] == {"_to": spender_address, "_value": amount}
        assert call_args["tx_args"]["sender_address"] == payer_address
        assert call_args["tx_args"]["value"] == 0
        assert call_args["tx_args"]["gas"] == 60000

    def test_approve_if_needed_no_executor_raises_error(
        self,
        strategy: TokenPaymentStrategy,
    ) -> None:
        """Test that approval raises error when executor not provided."""
        payer_address = "0x1234567890123456789012345678901234567890"
        spender_address = "0x" + "a" * 40
        amount = 10**18

        with pytest.raises(
            ValueError,
            match="Transaction executor required for token approval",
        ):
            strategy.approve_if_needed(
                payer_address=payer_address,
                spender_address=spender_address,
                amount=amount,
            )


class TestNVMPaymentStrategy:
    """Tests for NVMPaymentStrategy (NVM subscription payments)."""

    @pytest.fixture
    def strategy(self, mock_ledger_api: MagicMock) -> NVMPaymentStrategy:
        """Create NVM payment strategy instance."""
        return NVMPaymentStrategy(
            ledger_api=mock_ledger_api,
            payment_type=PaymentType.NATIVE_NVM,
            chain_id=100,  # Gnosis
        )

    def test_initialization(self, strategy: NVMPaymentStrategy) -> None:
        """Test strategy initialization."""
        assert strategy.payment_type == PaymentType.NATIVE_NVM
        assert strategy.chain_id == 100

    @patch.object(NVMPaymentStrategy, "check_subscription_balance")
    @patch.object(NVMPaymentStrategy, "get_balance_tracker_address")
    def test_check_balance_with_subscription(
        self,
        mock_get_tracker: MagicMock,
        mock_check_sub: MagicMock,
        strategy: NVMPaymentStrategy,
    ) -> None:
        """Test balance check with active subscription."""
        mock_get_tracker.return_value = "0x" + "b" * 40
        mock_check_sub.return_value = 100  # Active subscription balance

        payer_address = "0x1234567890123456789012345678901234567890"
        result = strategy.check_balance(payer_address, amount=10**18)
        assert result is True

    @patch.object(NVMPaymentStrategy, "check_subscription_balance")
    @patch.object(NVMPaymentStrategy, "get_balance_tracker_address")
    def test_check_balance_without_subscription(
        self,
        mock_get_tracker: MagicMock,
        mock_check_sub: MagicMock,
        strategy: NVMPaymentStrategy,
    ) -> None:
        """Test balance check without active subscription."""
        mock_get_tracker.return_value = "0x" + "b" * 40
        mock_check_sub.return_value = 0  # No subscription balance

        payer_address = "0x1234567890123456789012345678901234567890"
        result = strategy.check_balance(payer_address, amount=10**18)
        assert result is False

    def test_approve_if_needed_returns_none(
        self, strategy: NVMPaymentStrategy
    ) -> None:
        """Test that NVM payments don't need approval."""
        result = strategy.approve_if_needed(
            payer_address="0x1234567890123456789012345678901234567890",
            spender_address="0x" + "a" * 40,
            amount=10**18,
        )
        assert result is None


class TestPaymentStrategyFactory:
    """Tests for PaymentStrategyFactory."""

    def test_create_native_strategy(
        self,
        mock_ledger_api: MagicMock,
    ) -> None:
        """Test factory creates native payment strategy."""
        strategy = PaymentStrategyFactory.create(
            payment_type=PaymentType.NATIVE,
            ledger_api=mock_ledger_api,
            chain_id=100,
        )

        assert isinstance(strategy, NativePaymentStrategy)
        assert strategy.payment_type == PaymentType.NATIVE
        assert strategy.chain_id == 100

    def test_create_token_strategy(
        self,
        mock_ledger_api: MagicMock,
    ) -> None:
        """Test factory creates token payment strategy."""
        strategy = PaymentStrategyFactory.create(
            payment_type=PaymentType.OLAS_TOKEN,
            ledger_api=mock_ledger_api,
            chain_id=100,
        )

        assert isinstance(strategy, TokenPaymentStrategy)
        assert strategy.payment_type == PaymentType.OLAS_TOKEN

    def test_create_usdc_token_strategy(
        self,
        mock_ledger_api: MagicMock,
    ) -> None:
        """Test factory creates USDC token payment strategy."""
        strategy = PaymentStrategyFactory.create(
            payment_type=PaymentType.USDC_TOKEN,
            ledger_api=mock_ledger_api,
            chain_id=137,  # Polygon
        )

        assert isinstance(strategy, TokenPaymentStrategy)
        assert strategy.payment_type == PaymentType.USDC_TOKEN

    def test_create_nvm_native_strategy(
        self,
        mock_ledger_api: MagicMock,
    ) -> None:
        """Test factory creates NVM native payment strategy."""
        strategy = PaymentStrategyFactory.create(
            payment_type=PaymentType.NATIVE_NVM,
            ledger_api=mock_ledger_api,
            chain_id=100,
        )

        assert isinstance(strategy, NVMPaymentStrategy)
        assert strategy.payment_type == PaymentType.NATIVE_NVM

    def test_create_nvm_usdc_strategy(
        self,
        mock_ledger_api: MagicMock,
    ) -> None:
        """Test factory creates NVM USDC payment strategy."""
        strategy = PaymentStrategyFactory.create(
            payment_type=PaymentType.TOKEN_NVM_USDC,
            ledger_api=mock_ledger_api,
            chain_id=100,
        )

        assert isinstance(strategy, NVMPaymentStrategy)
        assert strategy.payment_type == PaymentType.TOKEN_NVM_USDC

    def test_create_with_invalid_payment_type(
        self,
        mock_ledger_api: MagicMock,
    ) -> None:
        """Test factory raises error for unsupported payment type."""
        with pytest.raises(ValueError, match="Unknown payment type"):
            PaymentStrategyFactory.create(
                payment_type="INVALID",  # type: ignore
                ledger_api=mock_ledger_api,
                chain_id=100,
            )
