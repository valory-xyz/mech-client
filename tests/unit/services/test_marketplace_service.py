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
import requests

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


# ---------------------------------------------------------------------------
# Additional tests for missing coverage lines
# ---------------------------------------------------------------------------


COMMON_PATCHES = [
    "mech_client.services.marketplace_service.IPFSClient",
    "mech_client.services.marketplace_service.ToolManager",
    "mech_client.services.base_service.ExecutorFactory",
    "mech_client.services.marketplace_service.EthereumCrypto",
    "mech_client.services.base_service.EthereumApi",
    "mech_client.services.base_service.get_mech_config",
]


def _apply_patches(test_func):  # type: ignore
    """Helper to stack common @patch decorators bottom-up."""
    import functools  # pylint: disable=import-outside-toplevel

    for target in reversed(COMMON_PATCHES):
        test_func = patch(target)(test_func)
    return test_func


def _build_service(
    mock_config_return: MagicMock,
    mock_ledger_api_cls: MagicMock,
    mock_executor_factory: MagicMock,
) -> MarketplaceService:
    """
    Create a MarketplaceService with common mocks pre-configured.

    :param mock_config_return: Return value for get_mech_config
    :param mock_ledger_api_cls: Mocked EthereumApi class
    :param mock_executor_factory: Mocked ExecutorFactory class
    :return: Configured MarketplaceService instance
    """
    mock_ledger_api_cls.return_value = MagicMock()
    mock_executor_factory.create.return_value = MagicMock()
    return MarketplaceService(
        chain_config="gnosis",
        agent_mode=False,
        crypto=create_mock_crypto(),
    )


class TestGetMarketplaceContractError:
    """Test _get_marketplace_contract when contract is not configured."""

    @patch("mech_client.services.marketplace_service.IPFSClient")
    @patch("mech_client.services.marketplace_service.ToolManager")
    @patch("mech_client.services.base_service.ExecutorFactory")
    @patch("mech_client.services.marketplace_service.EthereumCrypto")
    @patch("mech_client.services.base_service.EthereumApi")
    @patch("mech_client.services.base_service.get_mech_config")
    def test_raises_when_no_marketplace_contract(
        self,
        mock_config: MagicMock,
        mock_ledger_api_cls: MagicMock,
        mock_crypto: MagicMock,
        mock_executor_factory: MagicMock,
        mock_tool_manager: MagicMock,
        mock_ipfs_client: MagicMock,
    ) -> None:
        """Test ValueError when marketplace contract is not set (line 403)."""
        mock_mech_config = create_mock_mech_config()
        mock_mech_config.mech_marketplace_contract = None  # Not configured
        mock_config.return_value = mock_mech_config
        service = _build_service(mock_mech_config, mock_ledger_api_cls, mock_executor_factory)

        with pytest.raises(ValueError, match="Marketplace contract not available"):
            service._get_marketplace_contract()  # pylint: disable=protected-access


class TestFetchMechInfoError:
    """Test _fetch_mech_info when no mech address is specified."""

    @patch("mech_client.services.marketplace_service.IPFSClient")
    @patch("mech_client.services.marketplace_service.ToolManager")
    @patch("mech_client.services.base_service.ExecutorFactory")
    @patch("mech_client.services.marketplace_service.EthereumCrypto")
    @patch("mech_client.services.base_service.EthereumApi")
    @patch("mech_client.services.base_service.get_mech_config")
    def test_raises_when_no_mech_address(
        self,
        mock_config: MagicMock,
        mock_ledger_api_cls: MagicMock,
        mock_crypto: MagicMock,
        mock_executor_factory: MagicMock,
        mock_tool_manager: MagicMock,
        mock_ipfs_client: MagicMock,
    ) -> None:
        """Test ValueError when no mech address available (line 426)."""
        mock_mech_config = create_mock_mech_config()
        mock_mech_config.priority_mech_address = None  # No default address
        mock_config.return_value = mock_mech_config
        service = _build_service(mock_mech_config, mock_ledger_api_cls, mock_executor_factory)

        with pytest.raises(ValueError, match="No mech address specified"):
            service._fetch_mech_info(None)  # pylint: disable=protected-access


class TestValidateToolsEdgeCases:
    """Tests for edge cases in _validate_tools (lines 361, 366-382)."""

    @patch("mech_client.services.marketplace_service.IPFSClient")
    @patch("mech_client.services.marketplace_service.ToolManager")
    @patch("mech_client.services.base_service.ExecutorFactory")
    @patch("mech_client.services.marketplace_service.EthereumCrypto")
    @patch("mech_client.services.base_service.EthereumApi")
    @patch("mech_client.services.base_service.get_mech_config")
    def test_empty_tool_identifier_raises(
        self,
        mock_config: MagicMock,
        mock_ledger_api_cls: MagicMock,
        mock_crypto: MagicMock,
        mock_executor_factory: MagicMock,
        mock_tool_manager_cls: MagicMock,
        mock_ipfs_client: MagicMock,
    ) -> None:
        """Test that empty string tool raises ValueError (line 361)."""
        mock_config.return_value = create_mock_mech_config()
        service = _build_service(
            mock_config.return_value, mock_ledger_api_cls, mock_executor_factory
        )

        with pytest.raises(ValueError, match="Empty tool identifier"):
            service._validate_tools(("",), 1)  # pylint: disable=protected-access

    @patch("mech_client.services.marketplace_service.IPFSClient")
    @patch("mech_client.services.marketplace_service.ToolManager")
    @patch("mech_client.services.base_service.ExecutorFactory")
    @patch("mech_client.services.marketplace_service.EthereumCrypto")
    @patch("mech_client.services.base_service.EthereumApi")
    @patch("mech_client.services.base_service.get_mech_config")
    def test_get_tools_exception_logs_warning_and_returns(
        self,
        mock_config: MagicMock,
        mock_ledger_api_cls: MagicMock,
        mock_crypto: MagicMock,
        mock_executor_factory: MagicMock,
        mock_tool_manager_cls: MagicMock,
        mock_ipfs_client: MagicMock,
    ) -> None:
        """Test exception in get_tools is caught and logged (lines 366-373)."""
        mock_config.return_value = create_mock_mech_config()

        mock_tool_manager = MagicMock()
        mock_tool_manager.get_tools.side_effect = AttributeError("metadata missing")
        mock_tool_manager_cls.return_value = mock_tool_manager

        service = _build_service(
            mock_config.return_value, mock_ledger_api_cls, mock_executor_factory
        )

        # Should NOT raise — logs warning and returns silently
        service._validate_tools(("some-tool",), 1)  # pylint: disable=protected-access

    @patch("mech_client.services.marketplace_service.IPFSClient")
    @patch("mech_client.services.marketplace_service.ToolManager")
    @patch("mech_client.services.base_service.ExecutorFactory")
    @patch("mech_client.services.marketplace_service.EthereumCrypto")
    @patch("mech_client.services.base_service.EthereumApi")
    @patch("mech_client.services.base_service.get_mech_config")
    def test_empty_tools_info_logs_warning_and_returns(
        self,
        mock_config: MagicMock,
        mock_ledger_api_cls: MagicMock,
        mock_crypto: MagicMock,
        mock_executor_factory: MagicMock,
        mock_tool_manager_cls: MagicMock,
        mock_ipfs_client: MagicMock,
    ) -> None:
        """Test empty tools_info is handled gracefully (lines 375-382)."""
        mock_config.return_value = create_mock_mech_config()

        mock_tool_manager = MagicMock()
        mock_tool_manager.get_tools.return_value = None  # Falsy tools_info
        mock_tool_manager_cls.return_value = mock_tool_manager

        service = _build_service(
            mock_config.return_value, mock_ledger_api_cls, mock_executor_factory
        )

        # Should NOT raise — logs warning and returns silently
        service._validate_tools(("some-tool",), 1)  # pylint: disable=protected-access


class TestSendMarketplaceRequestInvalidPaymentType:
    """Test invalid payment type bytes handling (lines 477-478)."""

    @patch("mech_client.services.marketplace_service.IPFSClient")
    @patch("mech_client.services.marketplace_service.ToolManager")
    @patch("mech_client.services.base_service.ExecutorFactory")
    @patch("mech_client.services.marketplace_service.EthereumCrypto")
    @patch("mech_client.services.base_service.EthereumApi")
    @patch("mech_client.services.base_service.get_mech_config")
    def test_invalid_payment_type_hex_raises(
        self,
        mock_config: MagicMock,
        mock_ledger_api_cls: MagicMock,
        mock_crypto: MagicMock,
        mock_executor_factory: MagicMock,
        mock_tool_manager: MagicMock,
        mock_ipfs_client: MagicMock,
    ) -> None:
        """Test ValueError when payment_type.value is not valid hex (lines 477-478)."""
        mock_config.return_value = create_mock_mech_config()
        service = _build_service(
            mock_config.return_value, mock_ledger_api_cls, mock_executor_factory
        )

        # Create a payment_type mock whose value is invalid hex
        bad_payment_type = MagicMock()
        bad_payment_type.value = "ZZZZZZ"  # Invalid hex
        bad_payment_type.is_token.return_value = False

        with pytest.raises(ValueError, match="Invalid payment type value"):
            service._send_marketplace_request(  # pylint: disable=protected-access
                marketplace_contract=MagicMock(),
                data_hashes=["0x" + "a" * 64],
                max_delivery_rate=10**17,
                payment_type=bad_payment_type,
                priority_mech="0x" + "9" * 40,
                response_timeout=300,
                use_prepaid=False,
            )


class TestSendRequestNoPriorityMech:
    """Test send_request raises when no priority mech is configured."""

    @pytest.mark.asyncio
    @patch("mech_client.services.marketplace_service.IPFSClient")
    @patch("mech_client.services.marketplace_service.ToolManager")
    @patch("mech_client.services.base_service.ExecutorFactory")
    @patch("mech_client.services.marketplace_service.EthereumCrypto")
    @patch("mech_client.services.base_service.EthereumApi")
    @patch("mech_client.services.base_service.get_mech_config")
    async def test_raises_when_no_priority_mech(
        self,
        mock_config: MagicMock,
        mock_ledger_api_cls: MagicMock,
        mock_crypto: MagicMock,
        mock_executor_factory: MagicMock,
        mock_tool_manager: MagicMock,
        mock_ipfs_client: MagicMock,
    ) -> None:
        """Test ValueError when no priority mech address (line 135)."""
        mock_mech_config = create_mock_mech_config()
        mock_mech_config.priority_mech_address = None  # No default
        mock_config.return_value = mock_mech_config
        service = _build_service(mock_mech_config, mock_ledger_api_cls, mock_executor_factory)

        # Patch the internal helpers that run before the priority mech check
        with patch.object(
            service,
            "_get_marketplace_contract",
            return_value=MagicMock(),
        ):
            with patch.object(
                service,
                "_fetch_mech_info",
                return_value=(PaymentType.NATIVE, 1, 10**17),
            ):
                with patch.object(service, "_validate_tools"):
                    with pytest.raises(ValueError, match="No priority mech address"):
                        await service.send_request(
                            prompts=("hello",),
                            tools=("tool",),
                            priority_mech=None,  # No override either
                        )


class TestSendRequestOnchainFlow:
    """Test send_request on-chain flow (lines 122-228)."""

    @pytest.mark.asyncio
    @patch("mech_client.services.marketplace_service.OnchainDeliveryWatcher")
    @patch("mech_client.services.marketplace_service.watch_for_marketplace_request_ids")
    @patch("mech_client.services.marketplace_service.wait_for_receipt")
    @patch("mech_client.services.marketplace_service.push_metadata_to_ipfs")
    @patch("mech_client.services.marketplace_service.PaymentStrategyFactory")
    @patch("mech_client.services.marketplace_service.IPFSClient")
    @patch("mech_client.services.marketplace_service.ToolManager")
    @patch("mech_client.services.base_service.ExecutorFactory")
    @patch("mech_client.services.marketplace_service.EthereumCrypto")
    @patch("mech_client.services.base_service.EthereumApi")
    @patch("mech_client.services.base_service.get_mech_config")
    async def test_onchain_native_payment_flow(
        self,
        mock_config: MagicMock,
        mock_ledger_api_cls: MagicMock,
        mock_crypto: MagicMock,
        mock_executor_factory: MagicMock,
        mock_tool_manager: MagicMock,
        mock_ipfs_client: MagicMock,
        mock_payment_factory: MagicMock,
        mock_push_metadata: MagicMock,
        mock_wait_receipt: MagicMock,
        mock_watch_request_ids: MagicMock,
        mock_onchain_watcher_cls: MagicMock,
    ) -> None:
        """Test full on-chain native payment flow (lines 122-228)."""
        mock_mech_config = create_mock_mech_config()
        mock_mech_config.mech_marketplace_contract = "0x" + "2" * 40
        mock_mech_config.priority_mech_address = "0x" + "9" * 40
        mock_config.return_value = mock_mech_config

        mock_executor = MagicMock()
        mock_executor.execute_transaction.return_value = "0xtxhash"
        mock_executor.get_sender_address.return_value = "0x" + "a" * 40
        mock_executor_factory.create.return_value = mock_executor

        service = _build_service(mock_mech_config, mock_ledger_api_cls, mock_executor_factory)

        # Patch internal service methods
        mock_contract = MagicMock()
        mock_push_metadata.return_value = ("0x" + "b" * 64, "ipfs://hash")
        mock_wait_receipt.return_value = {"status": 1}
        mock_watch_request_ids.return_value = ["req-1"]

        mock_watcher = AsyncMock()
        mock_watcher.watch.return_value = {"req-1": "result"}
        mock_onchain_watcher_cls.return_value = mock_watcher

        # Mock payment strategy (NATIVE — not token, so no approval needed)
        mock_strategy = MagicMock()
        mock_strategy.get_balance_tracker_address.return_value = "0x" + "c" * 40
        mock_payment_factory.create.return_value = mock_strategy

        with patch.object(
            service, "_get_marketplace_contract", return_value=mock_contract
        ):
            with patch.object(
                service,
                "_fetch_mech_info",
                return_value=(PaymentType.NATIVE, 1, 10**17),
            ):
                with patch.object(service, "_validate_tools"):
                    with patch.object(
                        service,
                        "_send_marketplace_request",
                        return_value="0xtxhash",
                    ):
                        result = await service.send_request(
                            prompts=("hello",),
                            tools=("some-tool",),
                        )

        assert result["tx_hash"] == "0xtxhash"
        assert result["request_ids"] == ["req-1"]

    @pytest.mark.asyncio
    @patch("mech_client.services.marketplace_service.OnchainDeliveryWatcher")
    @patch("mech_client.services.marketplace_service.watch_for_marketplace_request_ids")
    @patch("mech_client.services.marketplace_service.wait_for_receipt")
    @patch("mech_client.services.marketplace_service.push_metadata_to_ipfs")
    @patch("mech_client.services.marketplace_service.PaymentStrategyFactory")
    @patch("mech_client.services.marketplace_service.IPFSClient")
    @patch("mech_client.services.marketplace_service.ToolManager")
    @patch("mech_client.services.base_service.ExecutorFactory")
    @patch("mech_client.services.marketplace_service.EthereumCrypto")
    @patch("mech_client.services.base_service.EthereumApi")
    @patch("mech_client.services.base_service.get_mech_config")
    async def test_onchain_token_payment_flow(
        self,
        mock_config: MagicMock,
        mock_ledger_api_cls: MagicMock,
        mock_crypto: MagicMock,
        mock_executor_factory: MagicMock,
        mock_tool_manager: MagicMock,
        mock_ipfs_client: MagicMock,
        mock_payment_factory: MagicMock,
        mock_push_metadata: MagicMock,
        mock_wait_receipt: MagicMock,
        mock_watch_request_ids: MagicMock,
        mock_onchain_watcher_cls: MagicMock,
    ) -> None:
        """Test on-chain token payment flow including approval (lines 174-195)."""
        mock_mech_config = create_mock_mech_config()
        mock_mech_config.mech_marketplace_contract = "0x" + "2" * 40
        mock_mech_config.priority_mech_address = "0x" + "9" * 40
        mock_mech_config.price = 10**18
        mock_config.return_value = mock_mech_config

        mock_executor = MagicMock()
        mock_executor.execute_transaction.return_value = "0xtxhash"
        mock_executor.get_sender_address.return_value = "0x" + "a" * 40
        mock_executor_factory.create.return_value = mock_executor

        service = _build_service(mock_mech_config, mock_ledger_api_cls, mock_executor_factory)

        # Mock payment strategy with is_token() = True, sufficient balance
        mock_strategy = MagicMock()
        mock_strategy.get_balance_tracker_address.return_value = "0x" + "c" * 40
        mock_strategy.check_balance.return_value = True  # Sufficient balance
        mock_payment_factory.create.return_value = mock_strategy

        mock_contract = MagicMock()
        mock_push_metadata.return_value = ("0x" + "b" * 64, "ipfs://hash")
        mock_wait_receipt.return_value = {"status": 1}
        mock_watch_request_ids.return_value = ["req-1"]

        mock_watcher = AsyncMock()
        mock_watcher.watch.return_value = {"req-1": "result"}
        mock_onchain_watcher_cls.return_value = mock_watcher

        # Use TOKEN payment type (is_token() returns True)
        token_payment_type = PaymentType.USDC_TOKEN

        with patch.object(
            service, "_get_marketplace_contract", return_value=mock_contract
        ):
            with patch.object(
                service,
                "_fetch_mech_info",
                return_value=(token_payment_type, 1, 10**17),
            ):
                with patch.object(service, "_validate_tools"):
                    with patch.object(
                        service,
                        "_send_marketplace_request",
                        return_value="0xtxhash",
                    ):
                        result = await service.send_request(
                            prompts=("hello",),
                            tools=("some-tool",),
                            use_prepaid=False,
                        )

        # Verify approval was triggered
        mock_strategy.approve_if_needed.assert_called_once()
        assert result["tx_hash"] == "0xtxhash"

    @pytest.mark.asyncio
    @patch("mech_client.services.marketplace_service.OnchainDeliveryWatcher")
    @patch("mech_client.services.marketplace_service.watch_for_marketplace_request_ids")
    @patch("mech_client.services.marketplace_service.wait_for_receipt")
    @patch("mech_client.services.marketplace_service.push_metadata_to_ipfs")
    @patch("mech_client.services.marketplace_service.PaymentStrategyFactory")
    @patch("mech_client.services.marketplace_service.IPFSClient")
    @patch("mech_client.services.marketplace_service.ToolManager")
    @patch("mech_client.services.base_service.ExecutorFactory")
    @patch("mech_client.services.marketplace_service.EthereumCrypto")
    @patch("mech_client.services.base_service.EthereumApi")
    @patch("mech_client.services.base_service.get_mech_config")
    async def test_onchain_token_insufficient_balance_raises(
        self,
        mock_config: MagicMock,
        mock_ledger_api_cls: MagicMock,
        mock_crypto: MagicMock,
        mock_executor_factory: MagicMock,
        mock_tool_manager: MagicMock,
        mock_ipfs_client: MagicMock,
        mock_payment_factory: MagicMock,
        mock_push_metadata: MagicMock,
        mock_wait_receipt: MagicMock,
        mock_watch_request_ids: MagicMock,
        mock_onchain_watcher_cls: MagicMock,
    ) -> None:
        """Test that insufficient token balance raises ValueError (lines 182-185)."""
        mock_mech_config = create_mock_mech_config()
        mock_mech_config.mech_marketplace_contract = "0x" + "2" * 40
        mock_mech_config.priority_mech_address = "0x" + "9" * 40
        mock_mech_config.price = 10**18
        mock_config.return_value = mock_mech_config

        mock_executor = MagicMock()
        mock_executor.get_sender_address.return_value = "0x" + "a" * 40
        mock_executor_factory.create.return_value = mock_executor

        service = _build_service(mock_mech_config, mock_ledger_api_cls, mock_executor_factory)

        # Mock payment strategy with insufficient balance
        mock_strategy = MagicMock()
        mock_strategy.get_balance_tracker_address.return_value = "0x" + "c" * 40
        mock_strategy.check_balance.return_value = False  # Insufficient
        mock_payment_factory.create.return_value = mock_strategy

        mock_push_metadata.return_value = ("0x" + "b" * 64, "ipfs://hash")

        with patch.object(service, "_get_marketplace_contract", return_value=MagicMock()):
            with patch.object(
                service,
                "_fetch_mech_info",
                return_value=(PaymentType.USDC_TOKEN, 1, 10**17),
            ):
                with patch.object(service, "_validate_tools"):
                    with pytest.raises(ValueError, match="Insufficient balance"):
                        await service.send_request(
                            prompts=("hello",),
                            tools=("some-tool",),
                            use_prepaid=False,
                        )


class TestSendOffchainRequest:
    """Tests for _send_offchain_request method (lines 258-345)."""

    @pytest.mark.asyncio
    @patch("mech_client.services.marketplace_service.OffchainDeliveryWatcher")
    @patch("mech_client.services.marketplace_service.IPFSClient")
    @patch("mech_client.services.marketplace_service.ToolManager")
    @patch("mech_client.services.base_service.ExecutorFactory")
    @patch("mech_client.services.marketplace_service.EthereumCrypto")
    @patch("mech_client.services.base_service.EthereumApi")
    @patch("mech_client.services.base_service.get_mech_config")
    async def test_offchain_request_success(
        self,
        mock_config: MagicMock,
        mock_ledger_api_cls: MagicMock,
        mock_crypto: MagicMock,
        mock_executor_factory: MagicMock,
        mock_tool_manager: MagicMock,
        mock_ipfs_client: MagicMock,
        mock_offchain_watcher_cls: MagicMock,
    ) -> None:
        """Test successful offchain request (lines 258-344)."""
        mock_mech_config = create_mock_mech_config()
        mock_mech_config.priority_mech_address = "0x" + "9" * 40
        mock_config.return_value = mock_mech_config

        mock_executor_factory.create.return_value = MagicMock()
        mock_ledger_api_cls.return_value = MagicMock()

        service = MarketplaceService(
            chain_config="gnosis",
            agent_mode=False,
            crypto=create_mock_crypto(),
        )

        # Mock crypto address and signing
        service.crypto = MagicMock()
        service.crypto.address = "0x" + "a" * 40
        service.crypto.sign_message.return_value = "0xsignature"

        # Mock marketplace contract
        mock_contract = MagicMock()
        mock_contract.functions.mapNonces.return_value.call.return_value = 0
        request_id_bytes = b"\x00" * 32
        mock_contract.functions.getRequestId.return_value.call.return_value = (
            request_id_bytes
        )

        # Mock watcher
        mock_watcher = AsyncMock()
        mock_watcher.watch.return_value = {"0" * 64: "offchain-result"}
        mock_offchain_watcher_cls.return_value = mock_watcher

        # Patch fetch_ipfs_hash and requests.post
        with patch(
            "mech_client.infrastructure.ipfs.metadata.fetch_ipfs_hash",
            return_value=("0x" + "b" * 64, "full-hash", '{"prompt":"hello"}'),
        ):
            with patch("mech_client.services.marketplace_service.requests") as mock_requests:
                mock_response = MagicMock()
                mock_response.json.return_value = {"status": "ok"}
                mock_requests.post.return_value = mock_response
                mock_requests.exceptions.RequestException = Exception

                result = await service._send_offchain_request(  # pylint: disable=protected-access
                    marketplace_contract=mock_contract,
                    prompts=("hello",),
                    tools=("some-tool",),
                    priority_mech_address="0x" + "9" * 40,
                    max_delivery_rate=10**17,
                    payment_type=PaymentType.NATIVE,
                    response_timeout=300,
                    mech_offchain_url="https://mech.example.com",
                    extra_attributes=None,
                    timeout=30.0,
                )

        assert result["tx_hash"] is None
        assert result["receipt"] is None

    @pytest.mark.asyncio
    @patch("mech_client.services.marketplace_service.OffchainDeliveryWatcher")
    @patch("mech_client.services.marketplace_service.IPFSClient")
    @patch("mech_client.services.marketplace_service.ToolManager")
    @patch("mech_client.services.base_service.ExecutorFactory")
    @patch("mech_client.services.marketplace_service.EthereumCrypto")
    @patch("mech_client.services.base_service.EthereumApi")
    @patch("mech_client.services.base_service.get_mech_config")
    async def test_offchain_request_http_error_raises(
        self,
        mock_config: MagicMock,
        mock_ledger_api_cls: MagicMock,
        mock_crypto: MagicMock,
        mock_executor_factory: MagicMock,
        mock_tool_manager: MagicMock,
        mock_ipfs_client: MagicMock,
        mock_offchain_watcher_cls: MagicMock,
    ) -> None:
        """Test that HTTP error from offchain endpoint raises ValueError (lines 332-333)."""
        mock_mech_config = create_mock_mech_config()
        mock_mech_config.priority_mech_address = "0x" + "9" * 40
        mock_config.return_value = mock_mech_config

        mock_executor_factory.create.return_value = MagicMock()
        mock_ledger_api_cls.return_value = MagicMock()

        service = MarketplaceService(
            chain_config="gnosis",
            agent_mode=False,
            crypto=create_mock_crypto(),
        )

        service.crypto = MagicMock()
        service.crypto.address = "0x" + "a" * 40
        service.crypto.sign_message.return_value = "0xsignature"

        mock_contract = MagicMock()
        mock_contract.functions.mapNonces.return_value.call.return_value = 0
        mock_contract.functions.getRequestId.return_value.call.return_value = b"\x00" * 32

        with patch(
            "mech_client.infrastructure.ipfs.metadata.fetch_ipfs_hash",
            return_value=("0x" + "b" * 64, "full-hash", '{"prompt":"hello"}'),
        ):
            with patch("mech_client.services.marketplace_service.requests") as mock_requests:
                # Simulate HTTP error
                mock_requests.exceptions.RequestException = requests.exceptions.RequestException
                mock_requests.post.side_effect = requests.exceptions.RequestException(
                    "connection refused"
                )

                with pytest.raises(ValueError, match="Failed to send offchain request"):
                    await service._send_offchain_request(  # pylint: disable=protected-access
                        marketplace_contract=mock_contract,
                        prompts=("hello",),
                        tools=("some-tool",),
                        priority_mech_address="0x" + "9" * 40,
                        max_delivery_rate=10**17,
                        payment_type=PaymentType.NATIVE,
                        response_timeout=300,
                        mech_offchain_url="https://mech.example.com",
                        extra_attributes=None,
                        timeout=30.0,
                    )


class TestSendRequestOffchainBranch:
    """Test send_request routing to _send_offchain_request (lines 141-154)."""

    @pytest.mark.asyncio
    @patch("mech_client.services.marketplace_service.IPFSClient")
    @patch("mech_client.services.marketplace_service.ToolManager")
    @patch("mech_client.services.base_service.ExecutorFactory")
    @patch("mech_client.services.marketplace_service.EthereumCrypto")
    @patch("mech_client.services.base_service.EthereumApi")
    @patch("mech_client.services.base_service.get_mech_config")
    async def test_send_request_routes_to_offchain(
        self,
        mock_config: MagicMock,
        mock_ledger_api_cls: MagicMock,
        mock_crypto: MagicMock,
        mock_executor_factory: MagicMock,
        mock_tool_manager: MagicMock,
        mock_ipfs_client: MagicMock,
    ) -> None:
        """Test that use_offchain=True calls _send_offchain_request (line 141-154)."""
        mock_mech_config = create_mock_mech_config()
        mock_mech_config.priority_mech_address = "0x" + "9" * 40
        mock_config.return_value = mock_mech_config

        mock_executor_factory.create.return_value = MagicMock()
        mock_ledger_api_cls.return_value = MagicMock()

        service = MarketplaceService(
            chain_config="gnosis",
            agent_mode=False,
            crypto=create_mock_crypto(),
        )

        offchain_result = {
            "tx_hash": None,
            "request_ids": ["hex-id"],
            "delivery_results": {},
            "receipt": None,
        }

        with patch.object(service, "_get_marketplace_contract", return_value=MagicMock()):
            with patch.object(
                service,
                "_fetch_mech_info",
                return_value=(PaymentType.NATIVE, 1, 10**17),
            ):
                with patch.object(service, "_validate_tools"):
                    with patch.object(
                        service,
                        "_send_offchain_request",
                        new_callable=AsyncMock,
                        return_value=offchain_result,
                    ) as mock_offchain:
                        result = await service.send_request(
                            prompts=("hello",),
                            tools=("tool",),
                            use_offchain=True,
                            mech_offchain_url="https://mech.example.com",
                        )

        mock_offchain.assert_called_once()
        assert result["tx_hash"] is None
