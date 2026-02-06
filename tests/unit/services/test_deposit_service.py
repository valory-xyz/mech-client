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

"""Tests for deposit service."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from mech_client.infrastructure.config import PaymentType
from mech_client.infrastructure.config.chain_config import LedgerConfig
from mech_client.services.deposit_service import DepositService


def create_mock_mech_config() -> MagicMock:
    """
    Create a mock MechConfig with proper LedgerConfig dataclass.

    :return: Mock MechConfig instance
    """
    ledger_config = LedgerConfig(
        address="https://rpc.example.com",
        chain_id=100,
        poa_chain=False,
        default_gas_price_strategy="eip1559",
        is_gas_estimation_enabled=True,
    )
    mock_mech_config = MagicMock()
    mock_mech_config.ledger_config = ledger_config
    mock_mech_config.gas_limit = 500000
    mock_mech_config.transaction_url = "https://explorer.com/tx/{}"
    return mock_mech_config


class TestDepositServiceInitialization:
    """Tests for DepositService initialization."""

    @patch("mech_client.services.deposit_service.get_mech_config")
    @patch("mech_client.services.deposit_service.EthereumApi")
    @patch("mech_client.services.deposit_service.EthereumCrypto")
    @patch("mech_client.services.deposit_service.ExecutorFactory")
    def test_initialization_client_mode(
        self,
        mock_executor_factory: MagicMock,
        mock_crypto: MagicMock,
        mock_ledger_api: MagicMock,
        mock_config: MagicMock,
    ) -> None:
        """Test DepositService initialization in client mode."""
        # Setup mocks
        mock_config.return_value = create_mock_mech_config()
        mock_executor = MagicMock()
        mock_executor_factory.create.return_value = mock_executor

        # Initialize service
        service = DepositService(
            chain_config="gnosis",
            agent_mode=False,
            private_key="0x" + "1" * 64,
        )

        # Verify initialization
        assert service.chain_config == "gnosis"
        assert service.agent_mode is False
        assert service.private_key == "0x" + "1" * 64
        assert service.safe_address is None
        assert service.ethereum_client is None
        mock_config.assert_called_once_with("gnosis")
        mock_executor_factory.create.assert_called_once()

    @patch("mech_client.services.deposit_service.get_mech_config")
    @patch("mech_client.services.deposit_service.EthereumApi")
    @patch("mech_client.services.deposit_service.EthereumCrypto")
    @patch("mech_client.services.deposit_service.ExecutorFactory")
    def test_initialization_agent_mode(
        self,
        mock_executor_factory: MagicMock,
        mock_crypto: MagicMock,
        mock_ledger_api: MagicMock,
        mock_config: MagicMock,
        mock_ethereum_client: MagicMock,
    ) -> None:
        """Test DepositService initialization in agent mode."""
        # Setup mocks
        mock_config.return_value = create_mock_mech_config()
        mock_executor = MagicMock()
        mock_executor_factory.create.return_value = mock_executor

        safe_address = "0x" + "2" * 40

        # Initialize service
        service = DepositService(
            chain_config="gnosis",
            agent_mode=True,
            private_key="0x" + "1" * 64,
            safe_address=safe_address,
            ethereum_client=mock_ethereum_client,
        )

        # Verify initialization
        assert service.chain_config == "gnosis"
        assert service.agent_mode is True
        assert service.safe_address == safe_address
        assert service.ethereum_client == mock_ethereum_client


class TestDepositNative:
    """Tests for deposit_native method."""

    @patch("mech_client.services.deposit_service.wait_for_receipt")
    @patch("mech_client.services.deposit_service.get_contract")
    @patch("mech_client.services.deposit_service.get_abi")
    @patch("mech_client.services.deposit_service.PaymentStrategyFactory")
    @patch("mech_client.services.deposit_service.ExecutorFactory")
    @patch("mech_client.services.deposit_service.EthereumCrypto")
    @patch("mech_client.services.deposit_service.EthereumApi")
    @patch("mech_client.services.deposit_service.get_mech_config")
    def test_deposit_native_success_client_mode(
        self,
        mock_config: MagicMock,
        mock_ledger_api_cls: MagicMock,
        mock_crypto: MagicMock,
        mock_executor_factory: MagicMock,
        mock_payment_factory: MagicMock,
        mock_get_abi: MagicMock,
        mock_get_contract: MagicMock,
        mock_wait_receipt: MagicMock,
    ) -> None:
        """Test successful native token deposit in client mode."""
        # Setup mocks
        mock_config.return_value = create_mock_mech_config()

        mock_ledger_api = MagicMock()
        mock_ledger_api_cls.return_value = mock_ledger_api

        mock_executor = MagicMock()
        mock_executor.get_sender_address.return_value = "0x" + "1" * 40
        mock_executor.execute_transaction.return_value = "0xtxhash"
        mock_executor_factory.create.return_value = mock_executor

        mock_payment_strategy = MagicMock()
        mock_payment_strategy.check_balance.return_value = True
        mock_payment_strategy.get_balance_tracker_address.return_value = "0x" + "2" * 40
        mock_payment_factory.create.return_value = mock_payment_strategy

        mock_contract = MagicMock()
        mock_get_contract.return_value = mock_contract

        # Create service
        service = DepositService(
            chain_config="gnosis",
            agent_mode=False,
            private_key="0x" + "3" * 64,
        )

        # Execute deposit
        amount = 10**18
        tx_hash = service.deposit_native(amount)

        # Verify
        assert tx_hash == "0xtxhash"
        mock_payment_factory.create.assert_called_once_with(
            payment_type=PaymentType.NATIVE,
            ledger_api=mock_ledger_api,
            chain_id=mock_config.return_value.ledger_config.chain_id,
        )
        mock_payment_strategy.check_balance.assert_called_once_with("0x" + "1" * 40, amount)
        mock_executor.execute_transaction.assert_called_once()
        mock_wait_receipt.assert_called_once_with("0xtxhash", mock_ledger_api)

    @patch("mech_client.services.deposit_service.PaymentStrategyFactory")
    @patch("mech_client.services.deposit_service.ExecutorFactory")
    @patch("mech_client.services.deposit_service.EthereumCrypto")
    @patch("mech_client.services.deposit_service.EthereumApi")
    @patch("mech_client.services.deposit_service.get_mech_config")
    def test_deposit_native_insufficient_balance(
        self,
        mock_config: MagicMock,
        mock_ledger_api_cls: MagicMock,
        mock_crypto: MagicMock,
        mock_executor_factory: MagicMock,
        mock_payment_factory: MagicMock,
    ) -> None:
        """Test native deposit with insufficient balance raises ValueError."""
        # Setup mocks
        mock_config.return_value = create_mock_mech_config()
        mock_ledger_api_cls.return_value = MagicMock()

        mock_executor = MagicMock()
        mock_executor.get_sender_address.return_value = "0x" + "1" * 40
        mock_executor_factory.create.return_value = mock_executor

        mock_payment_strategy = MagicMock()
        mock_payment_strategy.check_balance.return_value = False  # Insufficient balance
        mock_payment_factory.create.return_value = mock_payment_strategy

        # Create service
        service = DepositService(
            chain_config="gnosis",
            agent_mode=False,
            private_key="0x" + "3" * 64,
        )

        # Execute deposit and expect error
        amount = 10**18
        with pytest.raises(ValueError, match="Insufficient native token balance"):
            service.deposit_native(amount)


class TestDepositToken:
    """Tests for deposit_token method."""

    @patch("mech_client.services.deposit_service.wait_for_receipt")
    @patch("mech_client.services.deposit_service.get_contract")
    @patch("mech_client.services.deposit_service.get_abi")
    @patch("mech_client.services.deposit_service.PaymentStrategyFactory")
    @patch("mech_client.services.deposit_service.ExecutorFactory")
    @patch("mech_client.services.deposit_service.EthereumCrypto")
    @patch("mech_client.services.deposit_service.EthereumApi")
    @patch("mech_client.services.deposit_service.get_mech_config")
    def test_deposit_token_olas_success(
        self,
        mock_config: MagicMock,
        mock_ledger_api_cls: MagicMock,
        mock_crypto_cls: MagicMock,
        mock_executor_factory: MagicMock,
        mock_payment_factory: MagicMock,
        mock_get_abi: MagicMock,
        mock_get_contract: MagicMock,
        mock_wait_receipt: MagicMock,
    ) -> None:
        """Test successful OLAS token deposit."""
        # Setup mocks
        mock_config.return_value = create_mock_mech_config()

        mock_ledger_api = MagicMock()
        mock_ledger_api_cls.return_value = mock_ledger_api

        mock_crypto = MagicMock()
        mock_crypto_cls.return_value = mock_crypto

        mock_executor = MagicMock()
        mock_executor.get_sender_address.return_value = "0x" + "1" * 40
        mock_executor.execute_transaction.return_value = "0xtxhash"
        mock_executor_factory.create.return_value = mock_executor

        mock_payment_strategy = MagicMock()
        mock_payment_strategy.check_balance.return_value = True
        mock_payment_strategy.get_balance_tracker_address.return_value = "0x" + "2" * 40
        mock_payment_strategy.approve_if_needed.return_value = None  # No approval needed
        mock_payment_factory.create.return_value = mock_payment_strategy

        mock_contract = MagicMock()
        mock_get_contract.return_value = mock_contract

        # Create service
        service = DepositService(
            chain_config="gnosis",
            agent_mode=False,
            private_key="0x" + "3" * 64,
        )

        # Execute deposit
        amount = 10**18
        tx_hash = service.deposit_token(amount, token_type="olas")

        # Verify
        assert tx_hash == "0xtxhash"
        mock_payment_factory.create.assert_called_once_with(
            payment_type=PaymentType.TOKEN,
            ledger_api=mock_ledger_api,
            chain_id=mock_config.return_value.ledger_config.chain_id,
            crypto=mock_crypto,
        )
        mock_payment_strategy.check_balance.assert_called_once()
        mock_payment_strategy.approve_if_needed.assert_called_once()
        mock_executor.execute_transaction.assert_called_once()
        mock_wait_receipt.assert_called_once_with("0xtxhash", mock_ledger_api)

    @patch("mech_client.services.deposit_service.wait_for_receipt")
    @patch("mech_client.services.deposit_service.get_contract")
    @patch("mech_client.services.deposit_service.get_abi")
    @patch("mech_client.services.deposit_service.PaymentStrategyFactory")
    @patch("mech_client.services.deposit_service.ExecutorFactory")
    @patch("mech_client.services.deposit_service.EthereumCrypto")
    @patch("mech_client.services.deposit_service.EthereumApi")
    @patch("mech_client.services.deposit_service.get_mech_config")
    def test_deposit_token_usdc_success(
        self,
        mock_config: MagicMock,
        mock_ledger_api_cls: MagicMock,
        mock_crypto_cls: MagicMock,
        mock_executor_factory: MagicMock,
        mock_payment_factory: MagicMock,
        mock_get_abi: MagicMock,
        mock_get_contract: MagicMock,
        mock_wait_receipt: MagicMock,
    ) -> None:
        """Test successful USDC token deposit."""
        # Setup mocks
        mock_config.return_value = create_mock_mech_config()

        mock_ledger_api = MagicMock()
        mock_ledger_api_cls.return_value = mock_ledger_api

        mock_crypto = MagicMock()
        mock_crypto_cls.return_value = mock_crypto

        mock_executor = MagicMock()
        mock_executor.get_sender_address.return_value = "0x" + "1" * 40
        mock_executor.execute_transaction.return_value = "0xtxhash"
        mock_executor_factory.create.return_value = mock_executor

        mock_payment_strategy = MagicMock()
        mock_payment_strategy.check_balance.return_value = True
        mock_payment_strategy.get_balance_tracker_address.return_value = "0x" + "2" * 40
        mock_payment_strategy.approve_if_needed.return_value = "0xapprovetx"
        mock_payment_factory.create.return_value = mock_payment_strategy

        mock_contract = MagicMock()
        mock_get_contract.return_value = mock_contract

        # Create service
        service = DepositService(
            chain_config="base",
            agent_mode=False,
            private_key="0x" + "3" * 64,
        )

        # Execute deposit
        amount = 10**6  # 1 USDC
        tx_hash = service.deposit_token(amount, token_type="usdc")

        # Verify
        assert tx_hash == "0xtxhash"
        mock_payment_factory.create.assert_called_once_with(
            payment_type=PaymentType.USDC_TOKEN,
            ledger_api=mock_ledger_api,
            chain_id=mock_config.return_value.ledger_config.chain_id,
            crypto=mock_crypto,
        )
        # Approval should have been executed
        assert mock_wait_receipt.call_count == 2  # Once for approval, once for deposit

    @patch("mech_client.services.deposit_service.PaymentStrategyFactory")
    @patch("mech_client.services.deposit_service.ExecutorFactory")
    @patch("mech_client.services.deposit_service.EthereumCrypto")
    @patch("mech_client.services.deposit_service.EthereumApi")
    @patch("mech_client.services.deposit_service.get_mech_config")
    def test_deposit_token_insufficient_balance(
        self,
        mock_config: MagicMock,
        mock_ledger_api_cls: MagicMock,
        mock_crypto_cls: MagicMock,
        mock_executor_factory: MagicMock,
        mock_payment_factory: MagicMock,
    ) -> None:
        """Test token deposit with insufficient balance raises ValueError."""
        # Setup mocks
        mock_config.return_value = create_mock_mech_config()
        mock_ledger_api_cls.return_value = MagicMock()
        mock_crypto_cls.return_value = MagicMock()

        mock_executor = MagicMock()
        mock_executor.get_sender_address.return_value = "0x" + "1" * 40
        mock_executor_factory.create.return_value = mock_executor

        mock_payment_strategy = MagicMock()
        mock_payment_strategy.check_balance.return_value = False  # Insufficient balance
        mock_payment_factory.create.return_value = mock_payment_strategy

        # Create service
        service = DepositService(
            chain_config="gnosis",
            agent_mode=False,
            private_key="0x" + "3" * 64,
        )

        # Execute deposit and expect error
        amount = 10**18
        with pytest.raises(ValueError, match="Insufficient OLAS token balance"):
            service.deposit_token(amount, token_type="olas")

    @patch("mech_client.services.deposit_service.ExecutorFactory")
    @patch("mech_client.services.deposit_service.EthereumCrypto")
    @patch("mech_client.services.deposit_service.EthereumApi")
    @patch("mech_client.services.deposit_service.get_mech_config")
    def test_deposit_token_invalid_token_type(
        self,
        mock_config: MagicMock,
        mock_ledger_api_cls: MagicMock,
        mock_crypto_cls: MagicMock,
        mock_executor_factory: MagicMock,
    ) -> None:
        """Test deposit with invalid token type raises ValueError."""
        # Setup mocks
        mock_config.return_value = create_mock_mech_config()
        mock_ledger_api_cls.return_value = MagicMock()
        mock_crypto_cls.return_value = MagicMock()
        mock_executor_factory.create.return_value = MagicMock()

        # Create service
        service = DepositService(
            chain_config="gnosis",
            agent_mode=False,
            private_key="0x" + "3" * 64,
        )

        # Execute deposit with invalid token type
        with pytest.raises(ValueError, match="Unknown token type: invalid"):
            service.deposit_token(10**18, token_type="invalid")


class TestCheckBalance:
    """Tests for check_balance method."""

    @patch("mech_client.services.deposit_service.PaymentStrategyFactory")
    @patch("mech_client.services.deposit_service.ExecutorFactory")
    @patch("mech_client.services.deposit_service.EthereumCrypto")
    @patch("mech_client.services.deposit_service.EthereumApi")
    @patch("mech_client.services.deposit_service.get_mech_config")
    def test_check_balance_native(
        self,
        mock_config: MagicMock,
        mock_ledger_api_cls: MagicMock,
        mock_crypto: MagicMock,
        mock_executor_factory: MagicMock,
        mock_payment_factory: MagicMock,
    ) -> None:
        """Test checking prepaid balance for native payment."""
        # Setup mocks
        mock_config.return_value = create_mock_mech_config()

        mock_ledger_api = MagicMock()
        mock_ledger_api_cls.return_value = mock_ledger_api

        mock_executor = MagicMock()
        mock_executor_factory.create.return_value = mock_executor

        mock_payment_strategy = MagicMock()
        mock_payment_strategy.check_prepaid_balance.return_value = 5 * 10**18
        mock_payment_strategy.get_balance_tracker_address.return_value = "0x" + "2" * 40
        mock_payment_factory.create.return_value = mock_payment_strategy

        # Create service
        service = DepositService(
            chain_config="gnosis",
            agent_mode=False,
            private_key="0x" + "3" * 64,
        )

        # Check balance
        requester_address = "0x" + "1" * 40
        balance = service.check_balance(requester_address, PaymentType.NATIVE)

        # Verify
        assert balance == 5 * 10**18
        mock_payment_factory.create.assert_called_once_with(
            payment_type=PaymentType.NATIVE,
            ledger_api=mock_ledger_api,
            chain_id=mock_config.return_value.ledger_config.chain_id,
        )
        mock_payment_strategy.check_prepaid_balance.assert_called_once_with(
            requester_address, "0x" + "2" * 40
        )

    @patch("mech_client.services.deposit_service.PaymentStrategyFactory")
    @patch("mech_client.services.deposit_service.ExecutorFactory")
    @patch("mech_client.services.deposit_service.EthereumCrypto")
    @patch("mech_client.services.deposit_service.EthereumApi")
    @patch("mech_client.services.deposit_service.get_mech_config")
    def test_check_balance_token(
        self,
        mock_config: MagicMock,
        mock_ledger_api_cls: MagicMock,
        mock_crypto: MagicMock,
        mock_executor_factory: MagicMock,
        mock_payment_factory: MagicMock,
    ) -> None:
        """Test checking prepaid balance for token payment."""
        # Setup mocks
        mock_config.return_value = create_mock_mech_config()

        mock_ledger_api = MagicMock()
        mock_ledger_api_cls.return_value = mock_ledger_api

        mock_executor = MagicMock()
        mock_executor_factory.create.return_value = mock_executor

        mock_payment_strategy = MagicMock()
        mock_payment_strategy.check_prepaid_balance.return_value = 1000 * 10**18
        mock_payment_strategy.get_balance_tracker_address.return_value = "0x" + "2" * 40
        mock_payment_factory.create.return_value = mock_payment_strategy

        # Create service
        service = DepositService(
            chain_config="gnosis",
            agent_mode=False,
            private_key="0x" + "3" * 64,
        )

        # Check balance
        requester_address = "0x" + "1" * 40
        balance = service.check_balance(requester_address, PaymentType.TOKEN)

        # Verify
        assert balance == 1000 * 10**18
        mock_payment_factory.create.assert_called_once_with(
            payment_type=PaymentType.TOKEN,
            ledger_api=mock_ledger_api,
            chain_id=mock_config.return_value.ledger_config.chain_id,
        )
