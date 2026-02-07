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

"""Tests for marketplace service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mech_client.infrastructure.config import PaymentType
from mech_client.infrastructure.config.chain_config import LedgerConfig
from mech_client.services.marketplace_service import MarketplaceService


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
    mock_mech_config.transaction_url = "https://explorer.com/tx/{transaction_digest}"
    mock_mech_config.priority_mech_address = "0x" + "9" * 40
    mock_mech_config.price = 10**16  # 0.01 tokens
    return mock_mech_config


def create_mock_crypto(private_key: str = "0x" + "1" * 64) -> MagicMock:
    """
    Create a mock EthereumCrypto object.

    :param private_key: Private key to use
    :return: Mock crypto instance
    """
    mock_crypto = MagicMock()
    mock_crypto.private_key = private_key
    return mock_crypto


class TestMarketplaceServiceInitialization:
    """Tests for MarketplaceService initialization."""

    @patch("mech_client.services.marketplace_service.IPFSClient")
    @patch("mech_client.services.marketplace_service.ToolManager")
    @patch("mech_client.services.base_service.ExecutorFactory")
    @patch("mech_client.services.marketplace_service.EthereumCrypto")
    @patch("mech_client.services.base_service.EthereumApi")
    @patch("mech_client.services.base_service.get_mech_config")
    def test_initialization_client_mode(
        self,
        mock_config: MagicMock,
        mock_ledger_api: MagicMock,
        mock_crypto: MagicMock,
        mock_executor_factory: MagicMock,
        mock_tool_manager: MagicMock,
        mock_ipfs_client: MagicMock,
    ) -> None:
        """Test MarketplaceService initialization in client mode."""
        # Setup mocks
        mock_config.return_value = create_mock_mech_config()
        mock_executor = MagicMock()
        mock_executor_factory.create.return_value = mock_executor

        # Initialize service
        service = MarketplaceService(
            chain_config="gnosis",
            agent_mode=False,
            crypto=create_mock_crypto(),
        )

        # Verify initialization
        assert service.chain_config == "gnosis"
        assert service.agent_mode is False
        assert service.private_key == "0x" + "1" * 64
        assert service.safe_address is None
        assert service.ethereum_client is None
        mock_config.assert_called_once_with("gnosis", agent_mode=False)
        mock_executor_factory.create.assert_called_once()
        mock_tool_manager.assert_called_once_with("gnosis")
        mock_ipfs_client.assert_called_once()


class TestMarketplaceServiceValidation:
    """Tests for input validation in marketplace service."""

    def test_send_request_validates_prompt_tool_count(self) -> None:
        """Test that mismatched prompts/tools raises ValueError."""
        # Create a minimal mock service without full initialization
        service = MagicMock(spec=MarketplaceService)
        service.send_request = MarketplaceService.send_request.__get__(
            service, MarketplaceService
        )

        # The validation happens before any API calls, so we don't need mocks
        with pytest.raises(ValueError, match="must match"):
            # This will raise in the validation step
            import asyncio

            asyncio.run(
                service.send_request(
                    prompts=("prompt1", "prompt2"),
                    tools=("tool1",),  # Only one tool for two prompts
                )
            )

    def test_send_request_validates_offchain_url_required(self) -> None:
        """Test that use_offchain without URL raises ValueError."""
        service = MagicMock(spec=MarketplaceService)
        service.send_request = MarketplaceService.send_request.__get__(
            service, MarketplaceService
        )

        with pytest.raises(ValueError, match="mech_offchain_url required"):
            import asyncio

            asyncio.run(
                service.send_request(
                    prompts=("prompt1",),
                    tools=("tool1",),
                    use_offchain=True,
                    # Missing mech_offchain_url
                )
            )


class TestGetMarketplaceContract:
    """Tests for _get_marketplace_contract method."""

    @patch("mech_client.services.marketplace_service.get_contract")
    @patch("mech_client.services.marketplace_service.get_abi")
    @patch("mech_client.services.marketplace_service.IPFSClient")
    @patch("mech_client.services.marketplace_service.ToolManager")
    @patch("mech_client.services.base_service.ExecutorFactory")
    @patch("mech_client.services.marketplace_service.EthereumCrypto")
    @patch("mech_client.services.base_service.EthereumApi")
    @patch("mech_client.services.base_service.get_mech_config")
    def test_get_marketplace_contract_success(
        self,
        mock_config: MagicMock,
        mock_ledger_api_cls: MagicMock,
        mock_crypto: MagicMock,
        mock_executor_factory: MagicMock,
        mock_tool_manager: MagicMock,
        mock_ipfs_client: MagicMock,
        mock_get_abi: MagicMock,
        mock_get_contract: MagicMock,
    ) -> None:
        """Test successful marketplace contract retrieval."""
        # Setup mocks
        mock_mech_config = create_mock_mech_config()
        mock_mech_config.mech_marketplace_contract = "0x" + "2" * 40
        mock_config.return_value = mock_mech_config

        mock_ledger_api = MagicMock()
        mock_ledger_api_cls.return_value = mock_ledger_api

        mock_contract = MagicMock()
        mock_get_contract.return_value = mock_contract

        mock_abi = [{"name": "request"}]
        mock_get_abi.return_value = mock_abi

        mock_executor_factory.create.return_value = MagicMock()

        # Create service
        service = MarketplaceService(
            chain_config="gnosis",
            agent_mode=False,
            crypto=create_mock_crypto(),
        )

        # Get contract
        contract = service._get_marketplace_contract()  # pylint: disable=protected-access

        # Verify
        assert contract == mock_contract
        mock_get_abi.assert_called_once_with("MechMarketplace.json")
        mock_get_contract.assert_called_once_with(
            "0x" + "2" * 40, mock_abi, mock_ledger_api
        )


class TestFetchMechInfo:
    """Tests for _fetch_mech_info method."""

    @patch("mech_client.services.marketplace_service.get_contract")
    @patch("mech_client.services.marketplace_service.get_abi")
    @patch("mech_client.services.marketplace_service.IPFSClient")
    @patch("mech_client.services.marketplace_service.ToolManager")
    @patch("mech_client.services.base_service.ExecutorFactory")
    @patch("mech_client.services.marketplace_service.EthereumCrypto")
    @patch("mech_client.services.base_service.EthereumApi")
    @patch("mech_client.services.base_service.get_mech_config")
    def test_fetch_mech_info_success(
        self,
        mock_config: MagicMock,
        mock_ledger_api_cls: MagicMock,
        mock_crypto: MagicMock,
        mock_executor_factory: MagicMock,
        mock_tool_manager: MagicMock,
        mock_ipfs_client: MagicMock,
        mock_get_abi: MagicMock,
        mock_get_contract: MagicMock,
    ) -> None:
        """Test successful mech info fetching."""
        # Setup mocks
        mock_mech_config = create_mock_mech_config()
        mock_mech_config.priority_mech_address = "0x" + "9" * 40
        mock_config.return_value = mock_mech_config

        mock_ledger_api = MagicMock()
        mock_ledger_api_cls.return_value = mock_ledger_api

        # Mock IMech contract
        mock_mech_contract = MagicMock()
        # Return NATIVE payment type value as bytes
        payment_type_bytes = bytes.fromhex(PaymentType.NATIVE.value)
        mock_mech_contract.functions.paymentType.return_value.call.return_value = payment_type_bytes
        mock_mech_contract.functions.serviceId.return_value.call.return_value = 42
        mock_mech_contract.functions.maxDeliveryRate.return_value.call.return_value = 10**17

        mock_get_contract.return_value = mock_mech_contract
        mock_executor_factory.create.return_value = MagicMock()

        # Create service
        service = MarketplaceService(
            chain_config="gnosis",
            agent_mode=False,
            crypto=create_mock_crypto(),
        )

        # Fetch mech info
        payment_type, service_id, max_rate = service._fetch_mech_info(  # pylint: disable=protected-access
            "0x" + "9" * 40
        )

        # Verify
        assert payment_type == PaymentType.NATIVE
        assert service_id == 42
        assert max_rate == 10**17


class TestValidateTools:
    """Tests for _validate_tools method."""

    @patch("mech_client.services.marketplace_service.IPFSClient")
    @patch("mech_client.services.marketplace_service.ToolManager")
    @patch("mech_client.services.base_service.ExecutorFactory")
    @patch("mech_client.services.marketplace_service.EthereumCrypto")
    @patch("mech_client.services.base_service.EthereumApi")
    @patch("mech_client.services.base_service.get_mech_config")
    def test_validate_tools_success(
        self,
        mock_config: MagicMock,
        mock_ledger_api_cls: MagicMock,
        mock_crypto: MagicMock,
        mock_executor_factory: MagicMock,
        mock_tool_manager_cls: MagicMock,
        mock_ipfs_client: MagicMock,
    ) -> None:
        """Test successful tool validation."""
        # Setup mocks
        mock_config.return_value = create_mock_mech_config()
        mock_ledger_api_cls.return_value = MagicMock()
        mock_executor_factory.create.return_value = MagicMock()

        # Mock tool manager to return available tools
        mock_tool_manager = MagicMock()
        # Create mock tools info with tool objects that have tool_name attribute
        mock_tool1 = MagicMock()
        mock_tool1.tool_name = "1-openai-gpt-4"
        mock_tool2 = MagicMock()
        mock_tool2.tool_name = "1-stability-ai"
        mock_tools_info = MagicMock()
        mock_tools_info.tools = [mock_tool1, mock_tool2]
        mock_tool_manager.get_tools.return_value = mock_tools_info
        mock_tool_manager_cls.return_value = mock_tool_manager

        # Create service
        service = MarketplaceService(
            chain_config="gnosis",
            agent_mode=False,
            crypto=create_mock_crypto(),
        )

        # Validate tools - should not raise
        service._validate_tools(  # pylint: disable=protected-access
            ("1-openai-gpt-4",), 1
        )

    @patch("mech_client.services.marketplace_service.IPFSClient")
    @patch("mech_client.services.marketplace_service.ToolManager")
    @patch("mech_client.services.base_service.ExecutorFactory")
    @patch("mech_client.services.marketplace_service.EthereumCrypto")
    @patch("mech_client.services.base_service.EthereumApi")
    @patch("mech_client.services.base_service.get_mech_config")
    def test_validate_tools_invalid_tool(
        self,
        mock_config: MagicMock,
        mock_ledger_api_cls: MagicMock,
        mock_crypto: MagicMock,
        mock_executor_factory: MagicMock,
        mock_tool_manager_cls: MagicMock,
        mock_ipfs_client: MagicMock,
    ) -> None:
        """Test tool validation with invalid tool."""
        # Setup mocks
        mock_config.return_value = create_mock_mech_config()
        mock_ledger_api_cls.return_value = MagicMock()
        mock_executor_factory.create.return_value = MagicMock()

        # Mock tool manager to return limited tools
        mock_tool_manager = MagicMock()
        mock_tool1 = MagicMock()
        mock_tool1.tool_name = "1-openai-gpt-4"
        mock_tools_info = MagicMock()
        mock_tools_info.tools = [mock_tool1]
        mock_tool_manager.get_tools.return_value = mock_tools_info
        mock_tool_manager_cls.return_value = mock_tool_manager

        # Create service
        service = MarketplaceService(
            chain_config="gnosis",
            agent_mode=False,
            crypto=create_mock_crypto(),
        )

        # Validate invalid tool - should raise
        with pytest.raises(ValueError, match="not available"):
            service._validate_tools(  # pylint: disable=protected-access
                ("1-invalid-tool",), 1
            )


class TestSendMarketplaceRequest:
    """Tests for _send_marketplace_request method."""

    @patch("mech_client.services.marketplace_service.get_contract")
    @patch("mech_client.services.marketplace_service.get_abi")
    @patch("mech_client.services.marketplace_service.IPFSClient")
    @patch("mech_client.services.marketplace_service.ToolManager")
    @patch("mech_client.services.base_service.ExecutorFactory")
    @patch("mech_client.services.marketplace_service.EthereumCrypto")
    @patch("mech_client.services.base_service.EthereumApi")
    @patch("mech_client.services.base_service.get_mech_config")
    def test_send_marketplace_request_single(
        self,
        mock_config: MagicMock,
        mock_ledger_api_cls: MagicMock,
        mock_crypto: MagicMock,
        mock_executor_factory: MagicMock,
        mock_tool_manager: MagicMock,
        mock_ipfs_client: MagicMock,
        mock_get_abi: MagicMock,
        mock_get_contract: MagicMock,
    ) -> None:
        """Test sending single marketplace request."""
        # Setup mocks
        mock_mech_config = create_mock_mech_config()
        mock_mech_config.mech_marketplace_contract = "0x" + "2" * 40
        mock_config.return_value = mock_mech_config

        mock_ledger_api = MagicMock()
        mock_ledger_api_cls.return_value = mock_ledger_api

        mock_executor = MagicMock()
        mock_executor.execute_transaction.return_value = "0xtxhash"
        mock_executor_factory.create.return_value = mock_executor

        mock_contract = MagicMock()
        mock_get_contract.return_value = mock_contract

        # Create service
        service = MarketplaceService(
            chain_config="gnosis",
            agent_mode=False,
            crypto=create_mock_crypto(),
        )

        # Send request
        tx_hash = service._send_marketplace_request(  # pylint: disable=protected-access
            marketplace_contract=mock_contract,
            data_hashes=["0x" + "a" * 64],
            max_delivery_rate=10**17,
            payment_type=PaymentType.NATIVE,
            priority_mech="0x" + "9" * 40,
            response_timeout=300,
            use_prepaid=False,
        )

        # Verify
        assert tx_hash == "0xtxhash"
        mock_executor.execute_transaction.assert_called_once()
        # Should call request() not requestBatch() for single request
        call_args = mock_executor.execute_transaction.call_args
        assert call_args[1]["method_name"] == "request"

    @patch("mech_client.services.marketplace_service.get_contract")
    @patch("mech_client.services.marketplace_service.get_abi")
    @patch("mech_client.services.marketplace_service.IPFSClient")
    @patch("mech_client.services.marketplace_service.ToolManager")
    @patch("mech_client.services.base_service.ExecutorFactory")
    @patch("mech_client.services.marketplace_service.EthereumCrypto")
    @patch("mech_client.services.base_service.EthereumApi")
    @patch("mech_client.services.base_service.get_mech_config")
    def test_send_marketplace_request_batch(
        self,
        mock_config: MagicMock,
        mock_ledger_api_cls: MagicMock,
        mock_crypto: MagicMock,
        mock_executor_factory: MagicMock,
        mock_tool_manager: MagicMock,
        mock_ipfs_client: MagicMock,
        mock_get_abi: MagicMock,
        mock_get_contract: MagicMock,
    ) -> None:
        """Test sending batch marketplace request."""
        # Setup mocks
        mock_mech_config = create_mock_mech_config()
        mock_mech_config.mech_marketplace_contract = "0x" + "2" * 40
        mock_config.return_value = mock_mech_config

        mock_ledger_api = MagicMock()
        mock_ledger_api_cls.return_value = mock_ledger_api

        mock_executor = MagicMock()
        mock_executor.execute_transaction.return_value = "0xtxhash"
        mock_executor_factory.create.return_value = mock_executor

        mock_contract = MagicMock()
        mock_get_contract.return_value = mock_contract

        # Create service
        service = MarketplaceService(
            chain_config="gnosis",
            agent_mode=False,
            crypto=create_mock_crypto(),
        )

        # Send batch request (multiple hashes)
        tx_hash = service._send_marketplace_request(  # pylint: disable=protected-access
            marketplace_contract=mock_contract,
            data_hashes=["0x" + "a" * 64, "0x" + "b" * 64],
            max_delivery_rate=10**17,
            payment_type=PaymentType.NATIVE,
            priority_mech="0x" + "9" * 40,
            response_timeout=300,
            use_prepaid=False,
        )

        # Verify
        assert tx_hash == "0xtxhash"
        mock_executor.execute_transaction.assert_called_once()
        # Should call requestBatch() for multiple requests
        call_args = mock_executor.execute_transaction.call_args
        assert call_args[1]["method_name"] == "requestBatch"
