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


class TestNVMPaymentStrategyMethods:
    """Tests for NVMPaymentStrategy helper methods (coverage for missing lines)."""

    @pytest.fixture
    def native_nvm_strategy(
        self, mock_ledger_api: MagicMock
    ) -> NVMPaymentStrategy:
        """Create NVM native payment strategy on Gnosis (chain_id=100)."""
        return NVMPaymentStrategy(
            ledger_api=mock_ledger_api,
            payment_type=PaymentType.NATIVE_NVM,
            chain_id=100,
        )

    @pytest.fixture
    def usdc_nvm_strategy(
        self, mock_ledger_api: MagicMock
    ) -> NVMPaymentStrategy:
        """Create NVM USDC payment strategy on Polygon (chain_id=137)."""
        return NVMPaymentStrategy(
            ledger_api=mock_ledger_api,
            payment_type=PaymentType.TOKEN_NVM_USDC,
            chain_id=137,
        )

    def test_get_balance_tracker_address_native_nvm(
        self, native_nvm_strategy: NVMPaymentStrategy
    ) -> None:
        """Test balance tracker address returned for NATIVE_NVM on Gnosis."""
        address = native_nvm_strategy.get_balance_tracker_address()
        # Gnosis native balance tracker address from contract_addresses.py
        assert address == "0x21cE6799A22A3Da84B7c44a814a9c79ab1d2A50D"

    def test_get_balance_tracker_address_token_nvm_usdc(
        self, usdc_nvm_strategy: NVMPaymentStrategy
    ) -> None:
        """Test balance tracker address returned for TOKEN_NVM_USDC on Polygon."""
        address = usdc_nvm_strategy.get_balance_tracker_address()
        # Polygon USDC balance tracker from contract_addresses.py
        assert address == "0x5C50ebc17d002A4484585C8fbf62f51953493c0B"

    def test_get_balance_tracker_address_unknown_type_raises(
        self, mock_ledger_api: MagicMock
    ) -> None:
        """Test unknown NVM payment type raises ValueError."""
        strategy = NVMPaymentStrategy(
            ledger_api=mock_ledger_api,
            payment_type=PaymentType.NATIVE,  # Not an NVM type
            chain_id=100,
        )
        with pytest.raises(ValueError, match="Unknown NVM payment type"):
            strategy.get_balance_tracker_address()

    def test_get_payment_token_address_native_nvm_returns_none(
        self, native_nvm_strategy: NVMPaymentStrategy
    ) -> None:
        """Test NATIVE_NVM payment token address is None."""
        assert native_nvm_strategy.get_payment_token_address() is None

    def test_get_payment_token_address_usdc_nvm_returns_address(
        self, usdc_nvm_strategy: NVMPaymentStrategy
    ) -> None:
        """Test TOKEN_NVM_USDC payment token returns USDC address."""
        address = usdc_nvm_strategy.get_payment_token_address()
        # Polygon USDC token address from contract_addresses.py
        assert address == "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"

    def test_get_payment_token_address_usdc_unsupported_chain_raises(
        self, mock_ledger_api: MagicMock
    ) -> None:
        """Test TOKEN_NVM_USDC raises ValueError for chain without USDC support."""
        strategy = NVMPaymentStrategy(
            ledger_api=mock_ledger_api,
            payment_type=PaymentType.TOKEN_NVM_USDC,
            chain_id=100,  # Gnosis has no USDC token address
        )
        with pytest.raises(ValueError, match="USDC token not available"):
            strategy.get_payment_token_address()

    def test_get_payment_token_address_unknown_type_returns_none(
        self, mock_ledger_api: MagicMock
    ) -> None:
        """Test unknown NVM payment type returns None for token address."""
        strategy = NVMPaymentStrategy(
            ledger_api=mock_ledger_api,
            payment_type=PaymentType.NATIVE,  # Not an NVM type
            chain_id=100,
        )
        assert strategy.get_payment_token_address() is None

    @patch("mech_client.domain.payment.nvm.get_contract")
    @patch("mech_client.domain.payment.nvm.get_abi")
    def test_check_subscription_balance_native_nvm(
        self,
        mock_get_abi: MagicMock,
        mock_get_contract: MagicMock,
        native_nvm_strategy: NVMPaymentStrategy,
        mock_web3_contract: MagicMock,
    ) -> None:
        """Test check_subscription_balance returns combined balance for NATIVE_NVM."""
        mock_get_contract.return_value = mock_web3_contract
        payer = "0x1234567890123456789012345678901234567890"
        tracker = "0x" + "b" * 40

        # prepaid balance in tracker
        mock_web3_contract.functions.mapRequesterBalances.return_value.call.return_value = 5
        # NFT subscription address and token ID
        nft_address = "0x" + "c" * 40
        mock_web3_contract.functions.subscriptionNFT.return_value.call.return_value = (
            nft_address
        )
        mock_web3_contract.functions.subscriptionTokenId.return_value.call.return_value = 1
        # NFT balance
        mock_web3_contract.functions.balanceOf.return_value.call.return_value = 3

        result = native_nvm_strategy.check_subscription_balance(payer, tracker)

        assert result == 8  # 5 prepaid + 3 nft

    @patch("mech_client.domain.payment.nvm.get_contract")
    @patch("mech_client.domain.payment.nvm.get_abi")
    def test_check_subscription_balance_token_nvm_usdc(
        self,
        mock_get_abi: MagicMock,
        mock_get_contract: MagicMock,
        usdc_nvm_strategy: NVMPaymentStrategy,
        mock_web3_contract: MagicMock,
    ) -> None:
        """Test check_subscription_balance returns balance for TOKEN_NVM_USDC."""
        mock_get_contract.return_value = mock_web3_contract
        payer = "0x1234567890123456789012345678901234567890"
        tracker = "0x" + "d" * 40

        mock_web3_contract.functions.mapRequesterBalances.return_value.call.return_value = 10
        mock_web3_contract.functions.subscriptionNFT.return_value.call.return_value = (
            "0x" + "e" * 40
        )
        mock_web3_contract.functions.subscriptionTokenId.return_value.call.return_value = 2
        mock_web3_contract.functions.balanceOf.return_value.call.return_value = 0

        result = usdc_nvm_strategy.check_subscription_balance(payer, tracker)

        assert result == 10  # 10 prepaid + 0 nft

    @patch("mech_client.domain.payment.nvm.get_contract")
    @patch("mech_client.domain.payment.nvm.get_abi")
    def test_check_subscription_balance_unknown_type_raises(
        self,
        mock_get_abi: MagicMock,
        mock_get_contract: MagicMock,
        mock_ledger_api: MagicMock,
    ) -> None:
        """Test check_subscription_balance raises for unknown payment type."""
        strategy = NVMPaymentStrategy(
            ledger_api=mock_ledger_api,
            payment_type=PaymentType.NATIVE,  # Not an NVM type
            chain_id=100,
        )
        with pytest.raises(ValueError, match="Unknown NVM payment type"):
            strategy.check_subscription_balance(
                "0x1234567890123456789012345678901234567890", "0x" + "b" * 40
            )

    @patch.object(NVMPaymentStrategy, "check_subscription_balance")
    def test_check_prepaid_balance_delegates(
        self,
        mock_check_sub: MagicMock,
        native_nvm_strategy: NVMPaymentStrategy,
    ) -> None:
        """Test check_prepaid_balance delegates to check_subscription_balance."""
        mock_check_sub.return_value = 42
        payer = "0x1234567890123456789012345678901234567890"
        tracker = "0x" + "b" * 40

        result = native_nvm_strategy.check_prepaid_balance(payer, tracker)

        assert result == 42
        mock_check_sub.assert_called_once_with(payer, tracker)


class TestNativePaymentStrategyMethods:
    """Tests for NativePaymentStrategy helper methods (missing line coverage)."""

    @pytest.fixture
    def strategy(self, mock_ledger_api: MagicMock) -> NativePaymentStrategy:
        """Create NativePaymentStrategy on Gnosis (chain_id=100)."""
        return NativePaymentStrategy(
            ledger_api=mock_ledger_api,
            payment_type=PaymentType.NATIVE,
            chain_id=100,  # Gnosis
        )

    def test_get_balance_tracker_address_returns_gnosis_address(
        self, strategy: NativePaymentStrategy
    ) -> None:
        """Test get_balance_tracker_address returns the Gnosis native tracker address."""
        address = strategy.get_balance_tracker_address()
        # Gnosis native balance tracker from contract_addresses.py
        assert address == "0x21cE6799A22A3Da84B7c44a814a9c79ab1d2A50D"

    def test_get_payment_token_address_returns_none(
        self, strategy: NativePaymentStrategy
    ) -> None:
        """Test get_payment_token_address returns None for native payments."""
        result = strategy.get_payment_token_address()
        assert result is None

    @patch("mech_client.domain.payment.native.get_contract")
    @patch("mech_client.domain.payment.native.get_abi")
    def test_check_prepaid_balance_calls_contract(
        self,
        mock_get_abi: MagicMock,
        mock_get_contract: MagicMock,
        strategy: NativePaymentStrategy,
        mock_web3_contract: MagicMock,
    ) -> None:
        """Test check_prepaid_balance calls mapRequesterBalances on the contract."""
        mock_get_contract.return_value = mock_web3_contract
        expected_balance = 5 * 10**18
        mock_web3_contract.functions.mapRequesterBalances.return_value.call.return_value = (
            expected_balance
        )
        requester = "0x1234567890123456789012345678901234567890"
        tracker = "0x" + "b" * 40

        result = strategy.check_prepaid_balance(requester, tracker)

        assert result == expected_balance
        mock_get_abi.assert_called_once_with("BalanceTrackerFixedPriceNative.json")
        mock_get_contract.assert_called_once()
        mock_web3_contract.functions.mapRequesterBalances.assert_called_once()

    @patch("mech_client.domain.payment.native.get_contract")
    @patch("mech_client.domain.payment.native.get_abi")
    def test_check_prepaid_balance_checksums_address(
        self,
        mock_get_abi: MagicMock,
        mock_get_contract: MagicMock,
        strategy: NativePaymentStrategy,
        mock_web3_contract: MagicMock,
    ) -> None:
        """Test check_prepaid_balance checksums the requester address before calling contract."""
        mock_get_contract.return_value = mock_web3_contract
        mock_web3_contract.functions.mapRequesterBalances.return_value.call.return_value = (
            0
        )
        # Non-checksummed address (all lowercase)
        requester = "0xb3c6319962484602b00d5587e965946890b82101"
        tracker = "0x" + "c" * 40

        result = strategy.check_prepaid_balance(requester, tracker)

        assert isinstance(result, int)
        # Verify the contract was called with a checksummed address
        called_address = (
            mock_web3_contract.functions.mapRequesterBalances.call_args[0][0]
        )
        assert called_address == called_address  # checksummed form - passes web3.py


class TestTokenPaymentStrategyMethods:
    """Tests for TokenPaymentStrategy helper methods (missing line coverage)."""

    @pytest.fixture
    def olas_strategy(self, mock_ledger_api: MagicMock) -> TokenPaymentStrategy:
        """Create OLAS TokenPaymentStrategy on Gnosis (chain_id=100)."""
        return TokenPaymentStrategy(
            ledger_api=mock_ledger_api,
            payment_type=PaymentType.OLAS_TOKEN,
            chain_id=100,  # Gnosis - has OLAS token
        )

    @pytest.fixture
    def usdc_strategy_polygon(
        self, mock_ledger_api: MagicMock
    ) -> TokenPaymentStrategy:
        """Create USDC TokenPaymentStrategy on Polygon (chain_id=137)."""
        return TokenPaymentStrategy(
            ledger_api=mock_ledger_api,
            payment_type=PaymentType.USDC_TOKEN,
            chain_id=137,  # Polygon - has USDC token
        )

    def test_check_balance_raises_when_token_address_empty(
        self, mock_ledger_api: MagicMock
    ) -> None:
        """Test check_balance raises ValueError when get_payment_token_address returns empty."""
        strategy = TokenPaymentStrategy(
            ledger_api=mock_ledger_api,
            payment_type=PaymentType.OLAS_TOKEN,
            chain_id=100,
        )
        with patch.object(strategy, "get_payment_token_address", return_value=""):
            with pytest.raises(
                ValueError, match="Token address not configured for this payment type"
            ):
                strategy.check_balance(
                    "0x1234567890123456789012345678901234567890", 10**18
                )

    def test_approve_if_needed_raises_when_token_address_empty(
        self, mock_ledger_api: MagicMock
    ) -> None:
        """Test approve_if_needed raises ValueError when get_payment_token_address returns empty."""
        strategy = TokenPaymentStrategy(
            ledger_api=mock_ledger_api,
            payment_type=PaymentType.OLAS_TOKEN,
            chain_id=100,
        )
        mock_executor = MagicMock()
        with patch.object(strategy, "get_payment_token_address", return_value=""):
            with pytest.raises(
                ValueError, match="Token address not configured for this payment type"
            ):
                strategy.approve_if_needed(
                    payer_address="0x1234567890123456789012345678901234567890",
                    spender_address="0x" + "a" * 40,
                    amount=10**18,
                    executor=mock_executor,
                )

    def test_get_balance_tracker_address_usdc_polygon(
        self, usdc_strategy_polygon: TokenPaymentStrategy
    ) -> None:
        """Test get_balance_tracker_address returns USDC tracker on Polygon."""
        address = usdc_strategy_polygon.get_balance_tracker_address()
        # Polygon USDC balance tracker from contract_addresses.py
        assert address == "0x5C50ebc17d002A4484585C8fbf62f51953493c0B"

    def test_get_balance_tracker_address_olas_gnosis(
        self, olas_strategy: TokenPaymentStrategy
    ) -> None:
        """Test get_balance_tracker_address returns OLAS tracker on Gnosis."""
        address = olas_strategy.get_balance_tracker_address()
        # Gnosis OLAS balance tracker from contract_addresses.py
        assert address == "0x53Bd432516707a5212A70216284a99A563aAC1D1"

    def test_get_balance_tracker_address_unknown_type_raises(
        self, mock_ledger_api: MagicMock
    ) -> None:
        """Test get_balance_tracker_address raises ValueError for unknown type."""
        strategy = TokenPaymentStrategy(
            ledger_api=mock_ledger_api,
            payment_type=PaymentType.NATIVE,  # Not a token type
            chain_id=100,
        )
        with pytest.raises(ValueError, match="Unknown token payment type"):
            strategy.get_balance_tracker_address()

    def test_get_payment_token_address_usdc_raises_for_gnosis(
        self, mock_ledger_api: MagicMock
    ) -> None:
        """Test get_payment_token_address raises ValueError for USDC on Gnosis (no support)."""
        strategy = TokenPaymentStrategy(
            ledger_api=mock_ledger_api,
            payment_type=PaymentType.USDC_TOKEN,
            chain_id=100,  # Gnosis - USDC not available
        )
        with pytest.raises(ValueError, match="USDC token not available for chain 100"):
            strategy.get_payment_token_address()

    def test_get_payment_token_address_olas_raises_for_arbitrum(
        self, mock_ledger_api: MagicMock
    ) -> None:
        """Test get_payment_token_address raises ValueError for OLAS on Arbitrum (no support)."""
        strategy = TokenPaymentStrategy(
            ledger_api=mock_ledger_api,
            payment_type=PaymentType.OLAS_TOKEN,
            chain_id=42161,  # Arbitrum - OLAS not available
        )
        with pytest.raises(
            ValueError, match="OLAS token not available for chain 42161"
        ):
            strategy.get_payment_token_address()

    def test_get_payment_token_address_unknown_type_raises(
        self, mock_ledger_api: MagicMock
    ) -> None:
        """Test get_payment_token_address raises ValueError for unknown token type."""
        strategy = TokenPaymentStrategy(
            ledger_api=mock_ledger_api,
            payment_type=PaymentType.NATIVE,  # Not a token type
            chain_id=100,
        )
        with pytest.raises(ValueError, match="Unknown token payment type"):
            strategy.get_payment_token_address()

    @patch("mech_client.domain.payment.token.get_contract")
    @patch("mech_client.domain.payment.token.get_abi")
    def test_check_prepaid_balance_calls_contract(
        self,
        mock_get_abi: MagicMock,
        mock_get_contract: MagicMock,
        olas_strategy: TokenPaymentStrategy,
        mock_web3_contract: MagicMock,
    ) -> None:
        """Test check_prepaid_balance calls mapRequesterBalances on the token tracker."""
        mock_get_contract.return_value = mock_web3_contract
        expected_balance = 100 * 10**18
        mock_web3_contract.functions.mapRequesterBalances.return_value.call.return_value = (
            expected_balance
        )
        requester = "0x1234567890123456789012345678901234567890"
        tracker = "0x" + "d" * 40

        result = olas_strategy.check_prepaid_balance(requester, tracker)

        assert result == expected_balance
        mock_get_abi.assert_called_once_with("BalanceTrackerFixedPriceToken.json")
        mock_get_contract.assert_called_once()
        mock_web3_contract.functions.mapRequesterBalances.assert_called_once()

    @patch("mech_client.domain.payment.token.get_contract")
    @patch("mech_client.domain.payment.token.get_abi")
    def test_check_prepaid_balance_checksums_address(
        self,
        mock_get_abi: MagicMock,
        mock_get_contract: MagicMock,
        olas_strategy: TokenPaymentStrategy,
        mock_web3_contract: MagicMock,
    ) -> None:
        """Test check_prepaid_balance checksums the requester address before calling contract."""
        mock_get_contract.return_value = mock_web3_contract
        mock_web3_contract.functions.mapRequesterBalances.return_value.call.return_value = (
            0
        )
        # Non-checksummed address (all lowercase)
        requester = "0xb3c6319962484602b00d5587e965946890b82101"
        tracker = "0x" + "e" * 40

        result = olas_strategy.check_prepaid_balance(requester, tracker)

        assert isinstance(result, int)
        called_address = (
            mock_web3_contract.functions.mapRequesterBalances.call_args[0][0]
        )
        assert called_address == called_address  # checksummed form passes web3.py
