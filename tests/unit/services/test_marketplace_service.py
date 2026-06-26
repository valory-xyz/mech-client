# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2025-2026 Valory AG
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

from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import requests

from mech_client.infrastructure.config import PaymentType
from mech_client.infrastructure.config.chain_config import LedgerConfig
from mech_client.services.marketplace_service import (
    MarketplaceService,
    PaymentChallenge,
)


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
        contract = (
            service._get_marketplace_contract()
        )  # pylint: disable=protected-access

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
        mock_mech_contract.functions.paymentType.return_value.call.return_value = (
            payment_type_bytes
        )
        mock_mech_contract.functions.serviceId.return_value.call.return_value = 42
        mock_mech_contract.functions.maxDeliveryRate.return_value.call.return_value = (
            10**17
        )

        mock_get_contract.return_value = mock_mech_contract
        mock_executor_factory.create.return_value = MagicMock()

        # Create service
        service = MarketplaceService(
            chain_config="gnosis",
            agent_mode=False,
            crypto=create_mock_crypto(),
        )

        # Fetch mech info
        payment_type, service_id, max_rate = (
            service._fetch_mech_info(  # pylint: disable=protected-access
                "0x" + "9" * 40
            )
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
        service = _build_service(
            mock_mech_config, mock_ledger_api_cls, mock_executor_factory
        )

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
        service = _build_service(
            mock_mech_config, mock_ledger_api_cls, mock_executor_factory
        )

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
        service = _build_service(
            mock_mech_config, mock_ledger_api_cls, mock_executor_factory
        )

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

        service = _build_service(
            mock_mech_config, mock_ledger_api_cls, mock_executor_factory
        )

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

        service = _build_service(
            mock_mech_config, mock_ledger_api_cls, mock_executor_factory
        )

        # Mock payment strategy with is_token() = True, sufficient balance
        mock_strategy = MagicMock()
        mock_strategy.get_balance_tracker_address.return_value = "0x" + "c" * 40
        mock_strategy.check_balance.return_value = True  # Sufficient balance
        mock_payment_factory.create.return_value = mock_strategy

        mock_contract = MagicMock()
        mock_push_metadata.return_value = ("0x" + "b" * 64, "ipfs://hash")
        # Approve returns a distinct hash so we can verify wait_for_receipt
        # is called with it before the request transaction is built.
        mock_strategy.approve_if_needed.return_value = "0xapprovehash"
        mock_watch_request_ids.return_value = ["req-1"]

        mock_watcher = AsyncMock()
        mock_watcher.watch.return_value = {"req-1": "result"}
        mock_onchain_watcher_cls.return_value = mock_watcher

        # Use TOKEN payment type (is_token() returns True)
        token_payment_type = PaymentType.USDC_TOKEN
        max_delivery_rate = 10**17

        # Track call order between approval-receipt wait and request send.
        call_order: list[str] = []
        mock_wait_receipt.side_effect = lambda tx_hash, _api: (
            call_order.append(f"wait:{tx_hash}") or {"status": 1}
        )

        with patch.object(
            service, "_get_marketplace_contract", return_value=mock_contract
        ):
            with patch.object(
                service,
                "_fetch_mech_info",
                return_value=(token_payment_type, 1, max_delivery_rate),
            ):
                with patch.object(service, "_validate_tools"):
                    with patch.object(
                        service,
                        "_send_marketplace_request",
                        side_effect=lambda **_: (
                            call_order.append("send_request") or "0xtxhash"
                        ),
                    ):
                        result = await service.send_request(
                            prompts=("hello",),
                            tools=("some-tool",),
                            use_prepaid=False,
                        )

        # Verify approval was triggered with the per-mech rate, not mech_config.price
        mock_strategy.approve_if_needed.assert_called_once()
        approve_kwargs = mock_strategy.approve_if_needed.call_args.kwargs
        assert approve_kwargs["amount"] == max_delivery_rate * 1
        # Approve receipt must be awaited before the request tx is sent.
        assert call_order[0] == "wait:0xapprovehash"
        assert "send_request" in call_order
        assert call_order.index("wait:0xapprovehash") < call_order.index(
            "send_request"
        )
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

        service = _build_service(
            mock_mech_config, mock_ledger_api_cls, mock_executor_factory
        )

        # Mock payment strategy with insufficient balance
        mock_strategy = MagicMock()
        mock_strategy.get_balance_tracker_address.return_value = "0x" + "c" * 40
        mock_strategy.check_balance.return_value = False  # Insufficient
        mock_payment_factory.create.return_value = mock_strategy

        mock_push_metadata.return_value = ("0x" + "b" * 64, "ipfs://hash")

        with patch.object(
            service, "_get_marketplace_contract", return_value=MagicMock()
        ):
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

    @pytest.mark.asyncio
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
    async def test_onchain_reverted_tx_raises_error(
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
    ) -> None:
        """Test that a reverted transaction raises ValueError."""
        mock_mech_config = create_mock_mech_config()
        mock_mech_config.mech_marketplace_contract = "0x" + "2" * 40
        mock_mech_config.priority_mech_address = "0x" + "9" * 40
        mock_config.return_value = mock_mech_config

        mock_executor = MagicMock()
        mock_executor.execute_transaction.return_value = "0xtxhash"
        mock_executor.get_sender_address.return_value = "0x" + "a" * 40
        mock_executor_factory.create.return_value = mock_executor

        service = _build_service(
            mock_mech_config, mock_ledger_api_cls, mock_executor_factory
        )

        mock_contract = MagicMock()
        mock_push_metadata.return_value = ("0x" + "b" * 64, "ipfs://hash")
        # Receipt with status=0 means reverted
        mock_wait_receipt.return_value = {"status": 0}

        mock_strategy = MagicMock()
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
                        with pytest.raises(ValueError, match="reverted"):
                            await service.send_request(
                                prompts=("hello",),
                                tools=("some-tool",),
                            )

        # watch_for_marketplace_request_ids should NOT be called
        mock_watch_request_ids.assert_not_called()

    @pytest.mark.asyncio
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
    async def test_onchain_token_reverted_approve_raises_before_request(
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
    ) -> None:
        """A status=0 approve receipt must raise before _send_marketplace_request."""
        mock_mech_config = create_mock_mech_config()
        mock_mech_config.mech_marketplace_contract = "0x" + "2" * 40
        mock_mech_config.priority_mech_address = "0x" + "9" * 40
        mock_mech_config.price = 10**18
        mock_config.return_value = mock_mech_config

        mock_executor = MagicMock()
        mock_executor.get_sender_address.return_value = "0x" + "a" * 40
        mock_executor_factory.create.return_value = mock_executor

        service = _build_service(
            mock_mech_config, mock_ledger_api_cls, mock_executor_factory
        )

        mock_strategy = MagicMock()
        mock_strategy.get_balance_tracker_address.return_value = "0x" + "c" * 40
        mock_strategy.check_balance.return_value = True
        mock_strategy.approve_if_needed.return_value = "0xapprovehash"
        mock_payment_factory.create.return_value = mock_strategy

        mock_push_metadata.return_value = ("0x" + "b" * 64, "ipfs://hash")
        # Receipt with status=0 means the approve reverted on-chain
        mock_wait_receipt.return_value = {"status": 0}

        max_delivery_rate = 10**17
        mock_contract = MagicMock()
        with patch.object(
            service, "_get_marketplace_contract", return_value=mock_contract
        ):
            with patch.object(
                service,
                "_fetch_mech_info",
                return_value=(PaymentType.USDC_TOKEN, 1, max_delivery_rate),
            ):
                with patch.object(service, "_validate_tools"):
                    with patch.object(
                        service, "_send_marketplace_request"
                    ) as mock_send_request:
                        with pytest.raises(
                            ValueError,
                            match="Token approval transaction reverted",
                        ):
                            await service.send_request(
                                prompts=("hello",),
                                tools=("some-tool",),
                                use_prepaid=False,
                            )
                        # Request must not be sent if approve reverted
                        mock_send_request.assert_not_called()
        # Approval was sent for the per-mech rate, not mech_config.price
        approve_kwargs = mock_strategy.approve_if_needed.call_args.kwargs
        assert approve_kwargs["amount"] == max_delivery_rate * 1
        mock_watch_request_ids.assert_not_called()

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
    async def test_onchain_token_nvm_usdc_skips_approve_branch(
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
        """TOKEN_NVM_USDC is_token() but uses NVMPaymentStrategy (no approve);
        approve_if_needed returns None and must not flow into wait_for_receipt."""
        mock_mech_config = create_mock_mech_config()
        mock_mech_config.mech_marketplace_contract = "0x" + "2" * 40
        mock_mech_config.priority_mech_address = "0x" + "9" * 40
        mock_config.return_value = mock_mech_config

        mock_executor = MagicMock()
        mock_executor.execute_transaction.return_value = "0xtxhash"
        mock_executor.get_sender_address.return_value = "0x" + "a" * 40
        mock_executor_factory.create.return_value = mock_executor

        service = _build_service(
            mock_mech_config, mock_ledger_api_cls, mock_executor_factory
        )

        # NVMPaymentStrategy.approve_if_needed returns None — the regression
        # was that this None flowed through cast(str, None) into
        # wait_for_receipt(None, ...) and blocked for the full poll timeout.
        mock_strategy = MagicMock()
        mock_strategy.approve_if_needed.return_value = None
        mock_payment_factory.create.return_value = mock_strategy

        mock_push_metadata.return_value = ("0x" + "b" * 64, "ipfs://hash")
        mock_wait_receipt.return_value = {"status": 1}
        mock_watch_request_ids.return_value = ["req-1"]

        mock_watcher = AsyncMock()
        mock_watcher.watch.return_value = {"req-1": "result"}
        mock_onchain_watcher_cls.return_value = mock_watcher

        mock_contract = MagicMock()
        with patch.object(
            service, "_get_marketplace_contract", return_value=mock_contract
        ):
            with patch.object(
                service,
                "_fetch_mech_info",
                return_value=(PaymentType.TOKEN_NVM_USDC, 1, 10**17),
            ):
                with patch.object(service, "_validate_tools"):
                    with patch.object(
                        service,
                        "_send_marketplace_request",
                        return_value="0xtxhash",
                    ):
                        await service.send_request(
                            prompts=("hello",),
                            tools=("some-tool",),
                            use_prepaid=False,
                        )

        # The approve branch must be skipped entirely for NVM.
        mock_strategy.approve_if_needed.assert_not_called()
        # Only the request-tx receipt is awaited; no None hash polled.
        for call in mock_wait_receipt.call_args_list:
            assert call.args[0] is not None
            assert call.args[0] != ""

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
    async def test_onchain_token_approve_amount_scales_with_prompt_count(
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
        """With n_prompts=2, approve amount must scale as max_delivery_rate * 2;
        a single-prompt assertion would not catch dropping `* len(prompts)`."""
        mock_mech_config = create_mock_mech_config()
        mock_mech_config.mech_marketplace_contract = "0x" + "2" * 40
        mock_mech_config.priority_mech_address = "0x" + "9" * 40
        mock_config.return_value = mock_mech_config

        mock_executor = MagicMock()
        mock_executor.execute_transaction.return_value = "0xtxhash"
        mock_executor.get_sender_address.return_value = "0x" + "a" * 40
        mock_executor_factory.create.return_value = mock_executor

        service = _build_service(
            mock_mech_config, mock_ledger_api_cls, mock_executor_factory
        )

        mock_strategy = MagicMock()
        mock_strategy.get_balance_tracker_address.return_value = "0x" + "c" * 40
        mock_strategy.check_balance.return_value = True
        mock_strategy.approve_if_needed.return_value = "0xapprovehash"
        mock_payment_factory.create.return_value = mock_strategy

        mock_push_metadata.return_value = ("0x" + "b" * 64, "ipfs://hash")
        mock_wait_receipt.return_value = {"status": 1}
        mock_watch_request_ids.return_value = ["req-1", "req-2"]

        mock_watcher = AsyncMock()
        mock_watcher.watch.return_value = {"req-1": "r1", "req-2": "r2"}
        mock_onchain_watcher_cls.return_value = mock_watcher

        max_delivery_rate = 10**17
        prompts = ("hello", "world")
        tools = ("some-tool", "some-tool")
        mock_contract = MagicMock()

        with patch.object(
            service, "_get_marketplace_contract", return_value=mock_contract
        ):
            with patch.object(
                service,
                "_fetch_mech_info",
                return_value=(PaymentType.USDC_TOKEN, 1, max_delivery_rate),
            ):
                with patch.object(service, "_validate_tools"):
                    with patch.object(
                        service,
                        "_send_marketplace_request",
                        return_value="0xtxhash",
                    ):
                        await service.send_request(
                            prompts=prompts,
                            tools=tools,
                            use_prepaid=False,
                        )

        approve_kwargs = mock_strategy.approve_if_needed.call_args.kwargs
        assert approve_kwargs["amount"] == max_delivery_rate * len(prompts)
        assert approve_kwargs["amount"] == max_delivery_rate * 2


class TestGasEstimationEnabled:
    """Tests for gas estimation via is_gas_estimation_enabled config."""

    def test_gas_estimation_enabled_in_default_configs(self) -> None:
        """Test that is_gas_estimation_enabled is true in all chain configs."""
        import json  # pylint: disable=import-outside-toplevel
        from pathlib import Path  # pylint: disable=import-outside-toplevel

        config_path = (
            Path(__file__).parents[3] / "mech_client" / "configs" / "mechs.json"
        )
        with open(config_path, encoding="utf-8") as f:
            configs = json.load(f)

        for chain_name, chain_config in configs.items():
            ledger_config = chain_config.get("ledger_config", {})
            assert (
                ledger_config.get("is_gas_estimation_enabled") is True
            ), f"is_gas_estimation_enabled must be true for {chain_name}"


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
            with patch(
                "mech_client.services.marketplace_service.requests"
            ) as mock_requests:
                mock_response = MagicMock()
                mock_response.ok = True
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
        mock_contract.functions.getRequestId.return_value.call.return_value = (
            b"\x00" * 32
        )

        with patch(
            "mech_client.infrastructure.ipfs.metadata.fetch_ipfs_hash",
            return_value=("0x" + "b" * 64, "full-hash", '{"prompt":"hello"}'),
        ):
            with patch(
                "mech_client.services.marketplace_service.requests"
            ) as mock_requests:
                # Simulate HTTP error
                mock_requests.exceptions.RequestException = (
                    requests.exceptions.RequestException
                )
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

    @pytest.mark.asyncio
    @patch("mech_client.services.marketplace_service.OffchainDeliveryWatcher")
    @patch("mech_client.services.marketplace_service.IPFSClient")
    @patch("mech_client.services.marketplace_service.ToolManager")
    @patch("mech_client.services.base_service.ExecutorFactory")
    @patch("mech_client.services.marketplace_service.EthereumCrypto")
    @patch("mech_client.services.base_service.EthereumApi")
    @patch("mech_client.services.base_service.get_mech_config")
    async def test_offchain_request_rejected_with_json_reason(
        self,
        mock_config: MagicMock,
        mock_ledger_api_cls: MagicMock,
        mock_crypto: MagicMock,
        mock_executor_factory: MagicMock,
        mock_tool_manager: MagicMock,
        mock_ipfs_client: MagicMock,
        mock_offchain_watcher_cls: MagicMock,
    ) -> None:
        """Test non-2xx response with JSON reason raises ValueError."""
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
        mock_contract.functions.getRequestId.return_value.call.return_value = (
            b"\x00" * 32
        )

        with patch(
            "mech_client.infrastructure.ipfs.metadata.fetch_ipfs_hash",
            return_value=("0x" + "b" * 64, "full-hash", '{"prompt":"hello"}'),
        ):
            with patch(
                "mech_client.services.marketplace_service.requests"
            ) as mock_requests:
                mock_response = MagicMock()
                mock_response.ok = False
                mock_response.status_code = 400
                mock_response.reason = "Bad Request"
                mock_response.json.return_value = {"reason": "invalid signature"}
                mock_requests.post.return_value = mock_response
                mock_requests.exceptions.RequestException = (
                    requests.exceptions.RequestException
                )

                with pytest.raises(
                    ValueError, match="Offchain request rejected: invalid signature"
                ):
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

    @pytest.mark.asyncio
    @patch("mech_client.services.marketplace_service.OffchainDeliveryWatcher")
    @patch("mech_client.services.marketplace_service.IPFSClient")
    @patch("mech_client.services.marketplace_service.ToolManager")
    @patch("mech_client.services.base_service.ExecutorFactory")
    @patch("mech_client.services.marketplace_service.EthereumCrypto")
    @patch("mech_client.services.base_service.EthereumApi")
    @patch("mech_client.services.base_service.get_mech_config")
    async def test_offchain_request_rejected_no_json_body(
        self,
        mock_config: MagicMock,
        mock_ledger_api_cls: MagicMock,
        mock_crypto: MagicMock,
        mock_executor_factory: MagicMock,
        mock_tool_manager: MagicMock,
        mock_ipfs_client: MagicMock,
        mock_offchain_watcher_cls: MagicMock,
    ) -> None:
        """Test non-2xx response with no JSON body falls back to response.reason."""
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
        mock_contract.functions.getRequestId.return_value.call.return_value = (
            b"\x00" * 32
        )

        with patch(
            "mech_client.infrastructure.ipfs.metadata.fetch_ipfs_hash",
            return_value=("0x" + "b" * 64, "full-hash", '{"prompt":"hello"}'),
        ):
            with patch(
                "mech_client.services.marketplace_service.requests"
            ) as mock_requests:
                mock_response = MagicMock()
                mock_response.ok = False
                mock_response.status_code = 502
                mock_response.reason = "Bad Gateway"
                mock_response.json.side_effect = ValueError("No JSON")
                mock_requests.post.return_value = mock_response
                mock_requests.exceptions.RequestException = (
                    requests.exceptions.RequestException
                )

                with pytest.raises(
                    ValueError, match="Offchain request rejected: Bad Gateway"
                ):
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

        with patch.object(
            service, "_get_marketplace_contract", return_value=MagicMock()
        ):
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
                        # Mock tool_manager.get_offchain_url for auto-discovery
                        service.tool_manager = MagicMock()
                        service.tool_manager.get_offchain_url.return_value = (
                            "https://mech.example.com"
                        )

                        result = await service.send_request(
                            prompts=("hello",),
                            tools=("tool",),
                            use_offchain=True,
                        )

        mock_offchain.assert_called_once()
        assert result["tx_hash"] is None


def _build_offchain_service() -> MarketplaceService:
    """Build a MarketplaceService with its heavy init dependencies mocked."""
    with (
        patch(
            "mech_client.services.base_service.get_mech_config",
            return_value=create_mock_mech_config(),
        ),
        patch("mech_client.services.base_service.EthereumApi"),
        patch("mech_client.services.base_service.ExecutorFactory"),
        patch("mech_client.services.marketplace_service.EthereumCrypto"),
        patch("mech_client.services.marketplace_service.ToolManager"),
        patch("mech_client.services.marketplace_service.IPFSClient"),
    ):
        return MarketplaceService(
            chain_config="gnosis",
            agent_mode=False,
            crypto=create_mock_crypto(),
        )


def _mock_http_response(
    status_code: int,
    json_body: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
) -> MagicMock:
    """Build a mock requests.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.ok = 200 <= status_code < 300
    resp.reason = "OK" if resp.ok else "Payment Required"
    resp.headers = headers or {}
    resp.json.return_value = json_body if json_body is not None else {}
    return resp


class TestOffchain402Handling:
    """Tests for the structured offchain 402 challenge handling."""

    def test_parse_402_challenge_full_body(self) -> None:
        """A full 402 body + WWW-Authenticate header parses to a typed PaymentChallenge."""
        resp = _mock_http_response(
            402,
            {
                "required": "100",
                "currentBalance": "30",
                "payTo": "0xbalancetracker",
                "asset": "0x0000000000000000000000000000000000000000",
                "chainId": 100,
                "error": "insufficient balance",
            },
            {"WWW-Authenticate": 'Payment scheme="erc20-balance-tracker"'},
        )
        challenge = MarketplaceService._parse_402_challenge(resp)
        assert challenge == PaymentChallenge(
            required=100,
            current_balance=30,
            pay_to="0xbalancetracker",
            asset="0x0000000000000000000000000000000000000000",
            chain_id=100,
            error="insufficient balance",
        )
        assert challenge.shortfall == 70

    def test_parse_402_challenge_invalid_body_defaults_and_warns(self) -> None:
        """A non-JSON 402 body falls back to safe defaults and logs a warning."""
        resp = MagicMock()
        resp.headers = {}
        resp.json.side_effect = ValueError("no json")
        resp.text = "<html>500</html>"
        # mech_client sets propagate=False on its root logger (see
        # mech_client/utils/logger.py), so caplog can't see these records.
        # Patch the module logger's warning method directly.
        with patch(
            "mech_client.services.marketplace_service.logger.warning"
        ) as mock_warn:
            challenge = MarketplaceService._parse_402_challenge(resp)
        assert challenge.required == 0
        assert challenge.current_balance == 0
        assert challenge.error == "payment required"
        # Operators need a breadcrumb that the mech sent a bad body — silently
        # zeroing the challenge would mask a mech-side regression. The warning
        # must carry the format string AND the raw body so it's actionable.
        mock_warn.assert_called_once()
        fmt, *args = mock_warn.call_args[0]
        assert "not valid JSON" in fmt
        assert "<html>500</html>" in args

    def test_parse_402_challenge_non_numeric_value_is_tolerated(self) -> None:
        """A 402 body whose numeric fields hold strings doesn't blow up."""
        # A mech that sends ``"required": "N/A"`` instead of an int would
        # otherwise surface as an unhandled ValueError. Treat it as zero so
        # the caller still gets the no-deposit error message rather than a
        # raw traceback.
        resp = _mock_http_response(
            402,
            {
                "required": "N/A",
                "currentBalance": None,
                "chainId": "not-a-number",
                "payTo": "0xbt",
            },
        )
        challenge = MarketplaceService._parse_402_challenge(resp)
        assert challenge.required == 0
        assert challenge.current_balance == 0
        assert challenge.chain_id == 0
        assert challenge.pay_to == "0xbt"

    def test_log_payment_receipt_present_logs_value(self) -> None:
        """The Payment-Receipt header value is the audit signal — log it.

        Patches the module logger directly because mech_client sets
        propagate=False on its root logger, blocking caplog from seeing
        the records.
        """
        resp = _mock_http_response(200, headers={"Payment-Receipt": "abc123"})
        with patch(
            "mech_client.services.marketplace_service.logger.info"
        ) as mock_info:
            MarketplaceService._log_payment_receipt(resp)
        mock_info.assert_called_once()
        assert "abc123" in mock_info.call_args[0][0]

    def test_log_payment_receipt_absent_emits_no_record(self) -> None:
        """No Payment-Receipt header means no log line written."""
        resp = _mock_http_response(200, headers={})
        with patch(
            "mech_client.services.marketplace_service.logger.info"
        ) as mock_info:
            MarketplaceService._log_payment_receipt(resp)
        mock_info.assert_not_called()

    def test_auto_deposit_native(self) -> None:
        """Native payment deposits the shortfall via deposit_native."""
        service = _build_offchain_service()
        with patch("mech_client.services.deposit_service.DepositService") as mock_ds:
            service._auto_deposit_for_402(
                PaymentType.NATIVE,
                PaymentChallenge(100, 30, "0xbt", "", 100, "ib"),
                max_delivery_rate=100,
            )
            mock_ds.return_value.deposit_native.assert_called_once_with(70)

    def test_auto_deposit_token_usdc(self) -> None:
        """USDC payment deposits via deposit_token with the usdc token type."""
        service = _build_offchain_service()
        with patch("mech_client.services.deposit_service.DepositService") as mock_ds:
            service._auto_deposit_for_402(
                PaymentType.USDC_TOKEN,
                PaymentChallenge(100, 0, "0xbt", "", 100, "ib"),
                max_delivery_rate=100,
            )
            mock_ds.return_value.deposit_token.assert_called_once_with(100, "usdc")

    def test_auto_deposit_token_olas(self) -> None:
        """OLAS payment deposits via deposit_token with the olas token type."""
        service = _build_offchain_service()
        with patch("mech_client.services.deposit_service.DepositService") as mock_ds:
            service._auto_deposit_for_402(
                PaymentType.OLAS_TOKEN,
                PaymentChallenge(50, 10, "0xbt", "", 100, "ib"),
                max_delivery_rate=100,
            )
            mock_ds.return_value.deposit_token.assert_called_once_with(40, "olas")

    def test_auto_deposit_skips_when_no_shortfall(self) -> None:
        """No deposit happens when the balance already covers the requirement."""
        service = _build_offchain_service()
        with patch("mech_client.services.deposit_service.DepositService") as mock_ds:
            service._auto_deposit_for_402(
                PaymentType.NATIVE,
                PaymentChallenge(50, 50, "0xbt", "", 100, "ib"),
                max_delivery_rate=100,
            )
            mock_ds.assert_not_called()

    def test_auto_deposit_unsupported_type_raises(self) -> None:
        """NVM payment types can't be topped up via a balance-tracker deposit."""
        service = _build_offchain_service()
        with patch("mech_client.services.deposit_service.DepositService"):
            with pytest.raises(ValueError, match="not supported"):
                service._auto_deposit_for_402(
                    PaymentType.NATIVE_NVM,
                    PaymentChallenge(100, 0, "0xbt", "", 100, "ib"),
                    max_delivery_rate=100,
                )

    def test_auto_deposit_at_exactly_the_cap_proceeds(self) -> None:
        """A shortfall equal to 10x max_delivery_rate is allowed."""
        service = _build_offchain_service()
        # Cap = 10 * max_delivery_rate = 1000; shortfall = 1000 = at cap.
        with patch("mech_client.services.deposit_service.DepositService") as mock_ds:
            service._auto_deposit_for_402(
                PaymentType.NATIVE,
                PaymentChallenge(1000, 0, "0xbt", "", 100, "ib"),
                max_delivery_rate=100,
            )
            mock_ds.return_value.deposit_native.assert_called_once_with(1000)

    def test_auto_deposit_above_the_cap_is_refused(self) -> None:
        """A shortfall above 10x max_delivery_rate is refused with an actionable error.

        Without this cap a compromised or buggy mech could return a huge
        ``required`` and drain the user's wallet into their own prepaid
        balance tracker in one retry. The cap closes that hole; the error
        must name both the requested amount and the cap so the user can
        decide whether to deposit manually.
        """
        service = _build_offchain_service()
        with patch("mech_client.services.deposit_service.DepositService") as mock_ds:
            with pytest.raises(
                ValueError, match=r"refused.*1001.*safety cap of 1000"
            ):
                # Cap = 10 * 100 = 1000; shortfall = 1001 = above cap.
                service._auto_deposit_for_402(
                    PaymentType.NATIVE,
                    PaymentChallenge(1001, 0, "0xbt", "", 100, "ib"),
                    max_delivery_rate=100,
                )
            mock_ds.return_value.deposit_native.assert_not_called()

    def test_post_offchain_request_success_no_402(self) -> None:
        """A direct 200 returns the response (no deposit attempted)."""
        service = _build_offchain_service()
        with patch(
            "mech_client.services.marketplace_service.requests.post",
            return_value=_mock_http_response(200, headers={"Payment-Receipt": "r"}),
        ) as mock_post:
            resp = service._post_offchain_request(
                "http://mech/send_signed_requests",
                {},
                PaymentType.NATIVE,
                False,
                max_delivery_rate=100,
            )
            assert resp.status_code == 200
            mock_post.assert_called_once()

    def test_post_offchain_request_402_without_auto_deposit_raises(self) -> None:
        """A 402 without auto-deposit raises an error naming the amount + payTo."""
        service = _build_offchain_service()
        with patch(
            "mech_client.services.marketplace_service.requests.post",
            return_value=_mock_http_response(
                402, {"required": "100", "currentBalance": "0", "payTo": "0xbt"}
            ),
        ):
            with pytest.raises(ValueError, match=r"need 100.*0xbt"):
                service._post_offchain_request(
                    "http://mech/send_signed_requests",
                    {},
                    PaymentType.NATIVE,
                    False,
                    max_delivery_rate=100,
                )

    def test_post_offchain_request_402_auto_deposit_retries(self) -> None:
        """A 402 with auto-deposit deposits the shortfall and retries to a 200."""
        service = _build_offchain_service()
        responses = [
            _mock_http_response(402, {"required": "100", "currentBalance": "0"}),
            _mock_http_response(200, headers={"Payment-Receipt": "r"}),
        ]
        with (
            patch(
                "mech_client.services.marketplace_service.requests.post",
                side_effect=responses,
            ) as mock_post,
            patch("mech_client.services.deposit_service.DepositService") as mock_ds,
        ):
            resp = service._post_offchain_request(
                "http://mech/send_signed_requests",
                {},
                PaymentType.NATIVE,
                True,
                max_delivery_rate=100,
            )
            assert resp.status_code == 200
            assert mock_post.call_count == 2
            mock_ds.return_value.deposit_native.assert_called_once_with(100)

    def test_post_offchain_request_zero_shortfall_skips_retry(self) -> None:
        """A 402 reporting no shortfall raises directly without retry or deposit.

        Without this guard the code would call ``_auto_deposit_for_402`` (which
        no-ops on ``shortfall <= 0``), then issue a pointless retry POST, and
        if the retry also 402'd, surface the message claiming "Auto-deposit
        did not clear the 402: deposited to <pay_to>" — telling the user
        funds were deposited when none were. The two ways this gets reached
        in practice are a malformed 402 body (``_safe_int`` zeros out the
        numeric fields) and a mech bug reporting ``current_balance >=
        required`` while still 402-ing.
        """
        service = _build_offchain_service()
        with (
            patch(
                "mech_client.services.marketplace_service.requests.post",
                return_value=_mock_http_response(
                    402,
                    {"required": "100", "currentBalance": "100", "payTo": "0xbt"},
                ),
            ) as mock_post,
            patch("mech_client.services.deposit_service.DepositService") as mock_ds,
        ):
            with pytest.raises(
                ValueError, match=r"reports no shortfall.*required=100.*balance=100"
            ) as exc_info:
                service._post_offchain_request(
                    "http://mech/send_signed_requests",
                    {},
                    PaymentType.NATIVE,
                    True,
                    max_delivery_rate=100,
                )
        # Exactly one POST: the retry must not fire when no deposit happened.
        assert mock_post.call_count == 1
        mock_ds.return_value.deposit_native.assert_not_called()
        # And the error must not claim funds were deposited.
        assert "deposited to" not in str(exc_info.value)

    def test_post_offchain_request_above_cap_is_refused(self) -> None:
        """A 402 demanding more than the safety cap is refused, no retry, no deposit."""
        service = _build_offchain_service()
        with (
            patch(
                "mech_client.services.marketplace_service.requests.post",
                return_value=_mock_http_response(
                    402,
                    {"required": "10001", "currentBalance": "0", "payTo": "0xbt"},
                ),
            ) as mock_post,
            patch("mech_client.services.deposit_service.DepositService") as mock_ds,
        ):
            with pytest.raises(ValueError, match=r"refused.*safety cap"):
                service._post_offchain_request(
                    "http://mech/send_signed_requests",
                    {},
                    PaymentType.NATIVE,
                    True,
                    max_delivery_rate=1000,
                )
        # Only the original POST happened — no deposit, no retry.
        assert mock_post.call_count == 1
        mock_ds.return_value.deposit_native.assert_not_called()

    def test_post_offchain_request_second_402_after_deposit_raises_actionable(
        self,
    ) -> None:
        """A 402 that survives the auto-deposit retry surfaces a deposit-aware error.

        The deposit tx is awaited synchronously (``DepositService`` waits for
        receipt), so by the time the second POST runs the funds have moved.
        Silently returning the second 402 here would hit the generic
        ``Offchain request rejected: Payment Required (HTTP 402)`` branch and
        hide that fact from the user. The error must name the still-outstanding
        shortfall and the balance tracker the deposit landed in so they can
        debug (price moved, deposit too small, tx not mined yet, wrong asset).
        """
        service = _build_offchain_service()
        responses = [
            _mock_http_response(
                402, {"required": "100", "currentBalance": "0", "payTo": "0xbt"}
            ),
            _mock_http_response(
                402, {"required": "150", "currentBalance": "100", "payTo": "0xbt"}
            ),
        ]
        with (
            patch(
                "mech_client.services.marketplace_service.requests.post",
                side_effect=responses,
            ) as mock_post,
            patch("mech_client.services.deposit_service.DepositService") as mock_ds,
        ):
            with pytest.raises(
                ValueError, match=r"Auto-deposit did not clear the 402.*0xbt"
            ) as exc_info:
                service._post_offchain_request(
                    "http://mech/send_signed_requests",
                    {},
                    PaymentType.NATIVE,
                    True,
                    max_delivery_rate=200,
                )
        assert mock_post.call_count == 2
        # The deposit DID happen; the message has to make that visible.
        mock_ds.return_value.deposit_native.assert_called_once()
        # Surface the still-outstanding shortfall in the message.
        assert "remaining shortfall 50" in str(exc_info.value)
