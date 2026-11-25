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

import asyncio
import copy
import pickle
import re
import socket
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, MagicMock, call, patch

import eth_abi
import pytest
import requests
from click import ClickException
from eth_account import Account
from eth_utils import keccak
from eth_account.messages import encode_defunct
from web3.exceptions import Web3Exception

import mech_client
from mech_client.domain.delivery import DeliveryResult
from mech_client.domain.identification import VALORY_TERMS_NOTICE
from mech_client.domain.request_id import explicit_request_digest, request_digest
from mech_client.domain.signing import LocalSigner
from mech_client.domain.tools.manager import IDENTIFICATION_NOTE, ToolManager
from mech_client.domain.tools.models import MetadataRead
from mech_client.infrastructure.config import PaymentType
from mech_client.infrastructure.config.chain_config import LedgerConfig
from mech_client.nonces import NonceAllocator, NonceRefused, send_with_nonce
from mech_client.services.marketplace_service import (
    MAX_DERIVED_CAP_FACTOR,
    DEFAULT_CAP_FACTOR,
    EXPLICIT_NONCE_DEADLINE_SECONDS,
    EXPLICIT_NONCE_BITS,
    EXPLICIT_NONCE_DISABLED_REASON,
    MAX_DEADLINE_SECONDS,
    NONCE_MODE_EXPLICIT,
    NONCE_MODE_SEQUENTIAL,
    MINIMUM_CAP_REASON,
    MarketplaceService,
    MechInfo,
    MechPriceExceeded,
    OffchainRequestRejected,
    OffchainTopUpFailed,
    PaymentChallenge,
    PreSignHook,
    RequestIdMismatch,
    validate_request_shape,
)
from mech_client.utils.constants import UINT256_MAX
from mech_client.utils.errors import RpcError
from mech_client.utils.errors.handlers import handle_cli_errors
from mech_client.utils.validators import ensure_checksummed_address
from tests.unit.helpers import create_mock_signer

# Any mech address; the identification check is patched in these tests.
MECH_ADDRESS = "0x" + "9" * 40


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


# Real key material for the offchain signing path: the request signature is
# recovered locally against signer.address before the request goes out, so a
# canned byte string won't do.
_TEST_ACCOUNT = Account.from_key("0x" + "1" * 64)  # synthetic test key


def _real_signing_signer() -> MagicMock:
    """Create a mock signer that produces real raw-digest signatures.

    :return: Mock signer whose sign_message output recovers to its address
    """
    signer = create_mock_signer(address=_TEST_ACCOUNT.address)
    signer.sign_message.side_effect = lambda digest: bytes(
        _TEST_ACCOUNT.unsafe_sign_hash(digest).signature
    )
    return signer


MARKETPLACE_ADDRESS = "0x735FAAb1c4Ec41128c367AFb5c3baC73509f70bB"
# recorded from the deployed gnosis marketplace (see test_request_id.py)
DOMAIN_SEPARATOR = bytes.fromhex(
    "58fbb2508b962bcf6e2708fdfc23222115504128df851ae75ef8c66f2e0bdade"
)


def _derived_id(  # pylint: disable=too-many-arguments
    nonce: int,
    *,
    requester: str = _TEST_ACCOUNT.address,
    mech: str = MECH_ADDRESS,
    data: str = "0x" + "b" * 64,
    rate: int = 100,
    payment_type: str = "0x" + PaymentType.NATIVE.value,
) -> bytes:
    """Return the request id the deployed marketplace answers for these inputs."""
    return request_digest(
        domain_separator=DOMAIN_SEPARATOR,
        marketplace=MARKETPLACE_ADDRESS,
        mech=ensure_checksummed_address(mech),
        requester=ensure_checksummed_address(requester),
        data=bytes.fromhex(data.removeprefix("0x")),
        delivery_rate=rate,
        payment_type=bytes.fromhex(payment_type.removeprefix("0x")),
        nonce=nonce,
    )


def _honest(contract: MagicMock) -> MagicMock:
    """Make a marketplace mock answer getRequestId as the deployed contract does."""

    def get_request_id(  # pylint: disable=too-many-arguments
        mech: str, requester: str, data: str, rate: int, ptype: str, nonce: int
    ) -> MagicMock:
        request_id = _derived_id(
            nonce,
            requester=requester,
            mech=mech,
            data=data,
            rate=rate,
            payment_type=ptype,
        )
        return MagicMock(call=MagicMock(return_value=request_id))

    contract.address = MARKETPLACE_ADDRESS
    contract.functions.domainSeparator.return_value.call.return_value = DOMAIN_SEPARATOR
    contract.functions.getRequestId.side_effect = get_request_id
    return contract


def _explicit_id(  # pylint: disable=too-many-arguments
    nonce: int,
    deadline: int,
    *,
    requester: str = _TEST_ACCOUNT.address,
    mech: str = MECH_ADDRESS,
    data: str = "0x" + "b" * 64,
    rate: int = 100,
    payment_type: str = "0x" + PaymentType.NATIVE.value,
    marketplace: str = MARKETPLACE_ADDRESS,
) -> bytes:
    """Return the explicit-nonce request id the deployed marketplace answers on gnosis."""
    return explicit_request_digest(
        chain_id=100,
        marketplace=marketplace,
        mech=ensure_checksummed_address(mech),
        requester=ensure_checksummed_address(requester),
        data=bytes.fromhex(data.removeprefix("0x")),
        delivery_rate=rate,
        payment_type=bytes.fromhex(payment_type.removeprefix("0x")),
        nonce=nonce,
        deadline=deadline,
    )


def _honest_explicit(contract: MagicMock) -> MagicMock:
    """Make a marketplace mock answer getRequestIdWithNonce as the deployed contract does."""

    def get_request_id_with_nonce(  # pylint: disable=too-many-arguments
        mech: str, requester: str, data: str, rate: int, ptype: str, nonce: int, deadline: int
    ) -> MagicMock:
        request_id = _explicit_id(
            nonce,
            deadline,
            requester=requester,
            mech=mech,
            data=data,
            rate=rate,
            payment_type=ptype,
            marketplace=str(contract.address),
        )
        return MagicMock(call=MagicMock(return_value=request_id))

    if not isinstance(contract.address, str):
        contract.address = MARKETPLACE_ADDRESS
    contract.functions.getRequestIdWithNonce.side_effect = get_request_id_with_nonce
    return contract


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
        mock_crypto = create_mock_crypto()
        service = MarketplaceService(
            chain_config="gnosis",
            agent_mode=False,
            crypto=mock_crypto,
        )

        # Verify initialization
        assert service.chain_config == "gnosis"
        assert service.agent_mode is False
        # crypto is wrapped in the default LocalSigner, not stored on the service
        assert isinstance(service.signer, LocalSigner)
        assert service.signer.crypto is mock_crypto
        assert service.safe_address is None
        assert service.ethereum_client is None
        mock_config.assert_called_once_with("gnosis", agent_mode=False, rpc_url=None)
        mock_executor_factory.create.assert_called_once()
        mock_tool_manager.assert_called_once_with("gnosis", rpc_url=None)
        mock_ipfs_client.assert_called_once()

    @patch("mech_client.services.marketplace_service.IPFSClient")
    @patch("mech_client.services.marketplace_service.ToolManager")
    @patch("mech_client.services.base_service.ExecutorFactory")
    @patch("mech_client.services.base_service.EthereumApi")
    @patch("mech_client.services.base_service.get_mech_config")
    def test_initialization_with_signer_only(
        self,
        mock_config: MagicMock,
        mock_ledger_api: MagicMock,
        mock_executor_factory: MagicMock,
        mock_tool_manager: MagicMock,
        mock_ipfs_client: MagicMock,
    ) -> None:
        """Test initialization with an injected signer and no private key."""
        mock_config.return_value = create_mock_mech_config()
        mock_executor_factory.create.return_value = MagicMock()
        mock_signer = MagicMock()
        mock_signer.address = "0x" + "a" * 40

        service = MarketplaceService(
            chain_config="gnosis",
            agent_mode=False,
            signer=mock_signer,
        )

        # No key material in-process; signing goes through the signer
        assert service.signer is mock_signer
        create_kwargs = mock_executor_factory.create.call_args[1]
        assert create_kwargs["signer"] is mock_signer

    @patch("mech_client.services.base_service.get_mech_config")
    def test_initialization_requires_crypto_or_signer(
        self,
        mock_config: MagicMock,
    ) -> None:
        """Test initialization raises when neither crypto nor signer is given."""
        with pytest.raises(
            ValueError, match="Either a crypto object or a signer is required"
        ):
            MarketplaceService(
                chain_config="gnosis",
                agent_mode=False,
            )
        mock_config.assert_not_called()


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
    """Tests for marketplace_contract method."""

    @patch("mech_client.services.marketplace_service.get_contract")
    @patch("mech_client.services.marketplace_service.get_abi")
    @patch("mech_client.services.marketplace_service.IPFSClient")
    @patch("mech_client.services.marketplace_service.ToolManager")
    @patch("mech_client.services.base_service.ExecutorFactory")
    @patch("mech_client.services.marketplace_service.EthereumCrypto")
    @patch("mech_client.services.base_service.EthereumApi")
    @patch("mech_client.services.base_service.get_mech_config")
    def test_marketplace_contract_success(
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
        contract = service.marketplace_contract()

        # Verify
        assert contract == mock_contract
        mock_get_abi.assert_called_once_with("MechMarketplace.json")
        mock_get_contract.assert_called_once_with(
            "0x" + "2" * 40, mock_abi, mock_ledger_api
        )


class TestFetchMechInfo:
    """Tests for mech_info method."""

    @patch("mech_client.services.marketplace_service.get_contract")
    @patch("mech_client.services.marketplace_service.get_abi")
    @patch("mech_client.services.marketplace_service.IPFSClient")
    @patch("mech_client.services.marketplace_service.ToolManager")
    @patch("mech_client.services.base_service.ExecutorFactory")
    @patch("mech_client.services.marketplace_service.EthereumCrypto")
    @patch("mech_client.services.base_service.EthereumApi")
    @patch("mech_client.services.base_service.get_mech_config")
    def test_mech_info_success(
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
        info = service.mech_info("0x" + "9" * 40)

        # Verify
        assert info == MechInfo("0x" + "9" * 40, 42, PaymentType.NATIVE, 10**17)


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
        mock_tool_manager.tools_from_metadata.return_value = mock_tools_info
        mock_tool_manager_cls.return_value = mock_tool_manager

        # Create service
        service = MarketplaceService(
            chain_config="gnosis",
            agent_mode=False,
            crypto=create_mock_crypto(),
        )

        # Validate tools - should not raise
        service._validate_tools(  # pylint: disable=protected-access
            ("1-openai-gpt-4",), 1, {"tools": ["1-openai-gpt-4"]}
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
        mock_tool_manager.tools_from_metadata.return_value = mock_tools_info
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
                ("1-invalid-tool",), 1, {"tools": ["1-openai-gpt-4"]}
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
    """Test marketplace_contract when contract is not configured."""

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
            service.marketplace_contract()


class TestFetchMechInfoError:
    """Test mech_info when no mech address is specified."""

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
            service.mech_info("")


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
            service._validate_tools(("",), 1, {})  # pylint: disable=protected-access

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
        mock_tool_manager.tools_from_metadata.side_effect = AttributeError(
            "metadata missing"
        )
        mock_tool_manager_cls.return_value = mock_tool_manager

        service = _build_service(
            mock_config.return_value, mock_ledger_api_cls, mock_executor_factory
        )

        # Should NOT raise — logs warning and returns silently
        service._validate_tools(
            ("some-tool",), 1, {}
        )  # pylint: disable=protected-access

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
        mock_tool_manager.tools_from_metadata.return_value = None  # Falsy tools_info
        mock_tool_manager_cls.return_value = mock_tool_manager

        service = _build_service(
            mock_config.return_value, mock_ledger_api_cls, mock_executor_factory
        )

        # Should NOT raise — logs warning and returns silently
        service._validate_tools(
            ("some-tool",), 1, {}
        )  # pylint: disable=protected-access


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
            "marketplace_contract",
            return_value=MagicMock(),
        ):
            with patch.object(
                service,
                "mech_info",
                return_value=MechInfo(MECH_ADDRESS, 1, PaymentType.NATIVE, 10**17),
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
        mock_watcher.watch.return_value = {
            "req-1": DeliveryResult("req-1", data={"result": "answer"}, url="ipfs://1")
        }
        mock_onchain_watcher_cls.return_value = mock_watcher

        # Mock payment strategy (NATIVE — not token, so no approval needed)
        mock_strategy = MagicMock()
        mock_strategy.get_balance_tracker_address.return_value = "0x" + "c" * 40
        mock_payment_factory.create.return_value = mock_strategy

        with patch.object(service, "marketplace_contract", return_value=mock_contract):
            with patch.object(
                service,
                "mech_info",
                return_value=MechInfo(MECH_ADDRESS, 1, PaymentType.NATIVE, 10**17),
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
        # Content and location are separate keys, both keyed by request ID
        # One object per request: content and location cannot drift apart
        assert result["deliveries"] == {
            "req-1": DeliveryResult("req-1", data={"result": "answer"}, url="ipfs://1")
        }

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
        mock_watcher.watch.return_value = {
            "req-1": DeliveryResult("req-1", data={"result": "answer"}, url="ipfs://1")
        }
        mock_onchain_watcher_cls.return_value = mock_watcher

        # Use TOKEN payment type (is_token() returns True)
        token_payment_type = PaymentType.USDC_TOKEN
        max_delivery_rate = 10**17

        # Track call order between approval-receipt wait and request send.
        call_order: list[str] = []
        mock_wait_receipt.side_effect = lambda tx_hash, _api: (
            call_order.append(f"wait:{tx_hash}") or {"status": 1}
        )

        with patch.object(service, "marketplace_contract", return_value=mock_contract):
            with patch.object(
                service,
                "mech_info",
                return_value=MechInfo(
                    MECH_ADDRESS, 1, token_payment_type, max_delivery_rate
                ),
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
        assert call_order.index("wait:0xapprovehash") < call_order.index("send_request")
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

        with patch.object(service, "marketplace_contract", return_value=MagicMock()):
            with patch.object(
                service,
                "mech_info",
                return_value=MechInfo(MECH_ADDRESS, 1, PaymentType.USDC_TOKEN, 10**17),
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

        with patch.object(service, "marketplace_contract", return_value=mock_contract):
            with patch.object(
                service,
                "mech_info",
                return_value=MechInfo(MECH_ADDRESS, 1, PaymentType.NATIVE, 10**17),
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
        with patch.object(service, "marketplace_contract", return_value=mock_contract):
            with patch.object(
                service,
                "mech_info",
                return_value=MechInfo(
                    MECH_ADDRESS, 1, PaymentType.USDC_TOKEN, max_delivery_rate
                ),
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
        mock_watcher.watch.return_value = {
            "req-1": DeliveryResult("req-1", data={"result": "answer"}, url="ipfs://1")
        }
        mock_onchain_watcher_cls.return_value = mock_watcher

        mock_contract = MagicMock()
        with patch.object(service, "marketplace_contract", return_value=mock_contract):
            with patch.object(
                service,
                "mech_info",
                return_value=MechInfo(
                    MECH_ADDRESS, 1, PaymentType.TOKEN_NVM_USDC, 10**17
                ),
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
        mock_watcher.watch.return_value = {
            "req-1": DeliveryResult("req-1", data={"result": "r1"}, url="ipfs://1"),
            "req-2": DeliveryResult("req-2", data={"result": "r2"}, url="ipfs://2"),
        }
        mock_onchain_watcher_cls.return_value = mock_watcher

        max_delivery_rate = 10**17
        prompts = ("hello", "world")
        tools = ("some-tool", "some-tool")
        mock_contract = MagicMock()

        with patch.object(service, "marketplace_contract", return_value=mock_contract):
            with patch.object(
                service,
                "mech_info",
                return_value=MechInfo(
                    MECH_ADDRESS, 1, PaymentType.USDC_TOKEN, max_delivery_rate
                ),
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
        service.signer = _real_signing_signer()

        # Mock marketplace contract
        mock_contract = MagicMock()
        request_id_bytes = b"\x00" * 32
        _honest_explicit(mock_contract)

        # Mock watcher
        mock_watcher = AsyncMock()
        mock_watcher.watch.return_value = {
            "0"
            * 64: DeliveryResult(
                "0" * 64, data={"result": "offchain-result"}, url="ipfs://off"
            )
        }
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
        # Same shape as the on-chain path: content and location, keyed by request ID
        assert result["deliveries"] == {
            "0"
            * 64: DeliveryResult(
                "0" * 64, data={"result": "offchain-result"}, url="ipfs://off"
            )
        }

    @pytest.mark.asyncio
    @patch("mech_client.services.marketplace_service.OffchainDeliveryWatcher")
    @patch("mech_client.services.marketplace_service.IPFSClient")
    @patch("mech_client.services.marketplace_service.ToolManager")
    @patch("mech_client.services.base_service.ExecutorFactory")
    @patch("mech_client.services.marketplace_service.EthereumCrypto")
    @patch("mech_client.services.base_service.EthereumApi")
    @patch("mech_client.services.base_service.get_mech_config")
    async def test_client_mode_offchain_uses_eoa_as_requester(
        self,
        mock_config: MagicMock,
        mock_ledger_api_cls: MagicMock,
        mock_crypto: MagicMock,
        mock_executor_factory: MagicMock,
        mock_tool_manager: MagicMock,
        mock_ipfs_client: MagicMock,
        mock_offchain_watcher_cls: MagicMock,
    ) -> None:
        """Client-mode offchain request binds the EOA as the requester.

        Symmetric to the agent-mode invariant: with no Safe, the EOA is
        ``msg.sender`` on the settlement path and must be the address the
        offchain payload and ``getRequestIdWithNonce`` both
        key on. The Safe-wrapped signing helper must not be exercised.
        """
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
        service.signer = _real_signing_signer()

        mock_contract = MagicMock()
        request_id_bytes = b"\xcd" * 32
        _honest_explicit(mock_contract)

        mock_watcher = AsyncMock()
        mock_watcher.watch.return_value = {
            request_id_bytes.hex(): DeliveryResult(
                request_id_bytes.hex(), data={"result": "ok"}, url="ipfs://ok"
            )
        }
        mock_offchain_watcher_cls.return_value = mock_watcher

        with patch(
            "mech_client.infrastructure.ipfs.metadata.fetch_ipfs_hash",
            return_value=("0x" + "b" * 64, "full-hash", '{"prompt":"hi"}'),
        ):
            with patch(
                "mech_client.services.marketplace_service.requests"
            ) as mock_requests:
                mock_response = MagicMock()
                mock_response.ok = True
                mock_response.json.return_value = {"status": "ok"}
                mock_requests.post.return_value = mock_response
                mock_requests.exceptions.RequestException = Exception

                await service._send_offchain_request(  # pylint: disable=protected-access
                    marketplace_contract=mock_contract,
                    prompts=("hi",),
                    tools=("some-tool",),
                    priority_mech_address="0x" + "9" * 40,
                    max_delivery_rate=10**17,
                    payment_type=PaymentType.NATIVE,
                    response_timeout=300,
                    mech_offchain_url="https://mech.example.com",
                    extra_attributes=None,
                    timeout=30.0,
                )

        expected_sender = ensure_checksummed_address(_TEST_ACCOUNT.address)

        # Requester of record on all three surfaces is the EOA
        assert (
            mock_contract.functions.getRequestIdWithNonce.call_args.args[1] == expected_sender
        )
        posted_payload = mock_requests.post.call_args.kwargs["data"]
        assert posted_payload["sender"] == expected_sender

        # Safe-wrapped signing path is not exercised in client mode
        service.signer.sign_safe_message.assert_not_called()

    @pytest.mark.asyncio
    @patch("mech_client.services.marketplace_service.OffchainDeliveryWatcher")
    @patch("mech_client.services.marketplace_service.IPFSClient")
    @patch("mech_client.services.marketplace_service.ToolManager")
    @patch("mech_client.services.base_service.ExecutorFactory")
    @patch("mech_client.services.marketplace_service.EthereumCrypto")
    @patch("mech_client.services.base_service.EthereumApi")
    @patch("mech_client.services.base_service.get_mech_config")
    async def test_agent_mode_offchain_uses_safe_as_requester(
        self,
        mock_config: MagicMock,
        mock_ledger_api_cls: MagicMock,
        mock_crypto: MagicMock,
        mock_executor_factory: MagicMock,
        mock_tool_manager: MagicMock,
        mock_ipfs_client: MagicMock,
        mock_offchain_watcher_cls: MagicMock,
    ) -> None:
        """Agent-mode offchain request binds the Safe as the requester.

        End-to-end assertion of the requester-of-record property: the
        Safe address (not the signer EOA) must be the address passed
        into ``getRequestIdWithNonce`` and set as ``sender`` on the
        payload posted to the mech. The mech, subgraph, and settlement
        path all key on that field, so any of the three falling back to
        the EOA would split the identity across the offchain and onchain
        flows.
        """
        mock_mech_config = create_mock_mech_config()
        mock_mech_config.priority_mech_address = "0x" + "9" * 40
        mock_config.return_value = mock_mech_config
        mock_executor_factory.create.return_value = MagicMock()
        mock_ledger_api_cls.return_value = MagicMock()

        safe = "0x" + "5a" * 20
        service = MarketplaceService(
            chain_config="gnosis",
            agent_mode=True,
            crypto=create_mock_crypto(),
            safe_address=safe,
            ethereum_client=MagicMock(),
        )
        # Distinct EOA so a regression that binds the signer would surface
        service.signer = create_mock_signer(
            address="0x" + "e0" * 20, safe_signature=b"\xdd" * 64 + b"\x1b"
        )

        mock_contract = MagicMock()
        request_id_bytes = b"\xab" * 32
        _honest_explicit(mock_contract)

        mock_watcher = AsyncMock()
        mock_watcher.watch.return_value = {
            request_id_bytes.hex(): DeliveryResult(
                request_id_bytes.hex(), data={"result": "ok"}, url="ipfs://ok"
            )
        }
        mock_offchain_watcher_cls.return_value = mock_watcher

        with patch(
            "mech_client.infrastructure.ipfs.metadata.fetch_ipfs_hash",
            return_value=("0x" + "b" * 64, "full-hash", '{"prompt":"hi"}'),
        ):
            with patch(
                "mech_client.services.marketplace_service.requests"
            ) as mock_requests:
                mock_response = MagicMock()
                mock_response.ok = True
                mock_response.json.return_value = {"status": "ok"}
                mock_requests.post.return_value = mock_response
                mock_requests.exceptions.RequestException = Exception

                await service._send_offchain_request(  # pylint: disable=protected-access
                    marketplace_contract=mock_contract,
                    prompts=("hi",),
                    tools=("some-tool",),
                    priority_mech_address="0x" + "9" * 40,
                    max_delivery_rate=10**17,
                    payment_type=PaymentType.NATIVE,
                    response_timeout=300,
                    mech_offchain_url="https://mech.example.com",
                    extra_attributes=None,
                    timeout=30.0,
                )

        expected_sender = ensure_checksummed_address(safe)

        # 1. getRequestIdWithNonce was computed against the Safe as requester
        get_req_call = mock_contract.functions.getRequestIdWithNonce.call_args
        assert get_req_call.args[1] == expected_sender

        # 2. The signature was produced through the Safe-wrapped path, over
        # the id with the Safe as requester
        mech, _, data, rate, ptype, nonce, deadline = get_req_call.args
        service.signer.sign_safe_message.assert_called_once_with(
            expected_sender,
            service.mech_config.ledger_config.chain_id,
            _explicit_id(
                nonce,
                deadline,
                requester=expected_sender,
                mech=mech,
                data=data,
                rate=rate,
                payment_type=ptype,
            ),
        )

        # 3. The payload posted to the mech advertised the Safe as sender
        posted_payload = mock_requests.post.call_args.kwargs["data"]
        assert posted_payload["sender"] == expected_sender
        assert posted_payload["signature"] == "0x" + ("dd" * 64) + "1b"

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

        service.signer = _real_signing_signer()

        mock_contract = MagicMock()
        _honest_explicit(mock_contract)

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

        service.signer = _real_signing_signer()

        mock_contract = MagicMock()
        _honest_explicit(mock_contract)

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
    async def test_offchain_request_below_minimum_cap_names_the_minimum(
        self,
        mock_config: MagicMock,
        mock_ledger_api_cls: MagicMock,
        mock_crypto: MagicMock,
        mock_executor_factory: MagicMock,
        mock_tool_manager: MagicMock,
        mock_ipfs_client: MagicMock,
        mock_offchain_watcher_cls: MagicMock,
    ) -> None:
        """A minimum-cap 400 surfaces the minimum, not a generic rejection."""
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

        service.signer = _real_signing_signer()

        mock_contract = MagicMock()
        _honest_explicit(mock_contract)

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
                mock_response.json.return_value = {
                    "reason": MINIMUM_CAP_REASON,
                    "minimum_cap": 3 * 10**17,
                }
                mock_requests.post.return_value = mock_response
                mock_requests.exceptions.RequestException = (
                    requests.exceptions.RequestException
                )

                with pytest.raises(
                    ValueError, match=r"minimum cap: 300000000000000000"
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

        service.signer = _real_signing_signer()

        mock_contract = MagicMock()
        _honest_explicit(mock_contract)

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


class TestSignRequestDigest:
    """Tests for _sign_request_digest (fire-time ecrecover guard)."""

    @staticmethod
    def _digest() -> bytes:
        """Return a fixed 32-byte request-id digest.

        :return: 32-byte digest
        """
        return b"\x11" * 32

    def test_valid_signature_passes_and_is_hex_encoded(self) -> None:
        """A raw-digest signature recovers to the signer and is returned."""
        service = _build_offchain_service()
        service.signer = _real_signing_signer()

        signature = service._sign_request_digest(_TEST_ACCOUNT.address, self._digest())

        expected = bytes(_TEST_ACCOUNT.unsafe_sign_hash(self._digest()).signature)
        assert signature == "0x" + expected.hex()

    def test_low_v_signature_is_normalized_for_recovery_only(self) -> None:
        """A signer using v in {0, 1} passes; original bytes are sent."""
        service = _build_offchain_service()
        real = bytes(_TEST_ACCOUNT.unsafe_sign_hash(self._digest()).signature)
        low_v = real[:64] + bytes([real[64] - 27])
        service.signer = create_mock_signer(
            address=_TEST_ACCOUNT.address, signature=low_v
        )

        signature = service._sign_request_digest(_TEST_ACCOUNT.address, self._digest())

        # The low-v original goes out; normalization is check-only
        assert signature == "0x" + low_v.hex()

    def test_eip191_signature_is_rejected_with_diagnostic(self) -> None:
        """An EIP-191 personal-message signature recovers to the wrong address."""
        service = _build_offchain_service()
        eip191 = bytes(
            _TEST_ACCOUNT.sign_message(encode_defunct(self._digest())).signature
        )
        service.signer = create_mock_signer(
            address=_TEST_ACCOUNT.address, signature=eip191
        )

        with pytest.raises(ValueError, match="EIP-191"):
            service._sign_request_digest(_TEST_ACCOUNT.address, self._digest())

    def test_wrong_length_signature_is_rejected(self) -> None:
        """A non-65-byte signature fails fast with a clear message."""
        service = _build_offchain_service()
        service.signer = create_mock_signer(signature=b"\xab" * 64)

        with pytest.raises(ValueError, match="expected\\s+65 bytes"):
            service._sign_request_digest(create_mock_signer().address, self._digest())

    def test_unrecoverable_signature_is_rejected(self) -> None:
        """A malformed signature (r = s = 0) surfaces a diagnostic error."""
        service = _build_offchain_service()
        service.signer = create_mock_signer(signature=b"\x00" * 64 + b"\x1b")

        with (
            patch(f"{SERVICE}.logger.warning") as warning,
            pytest.raises(ValueError, match="cannot be recovered") as raised,
        ):
            service._sign_request_digest(create_mock_signer().address, self._digest())

        cause = type(raised.value.__cause__).__name__
        warning.assert_called_once()
        assert warning.call_args.args[0].startswith(
            f"Signature recovery failed: {cause}"
        )

    def test_agent_mode_signs_via_safe_message_wrapper(self) -> None:
        """Agent-mode signing routes through sign_safe_message with the Safe."""
        safe = "0x" + "5a" * 20
        service = _build_offchain_service(agent_mode=True, safe_address=safe)
        service.signer = create_mock_signer(safe_signature=b"\xdd" * 64 + b"\x1b")
        checksummed_safe = ensure_checksummed_address(safe)

        signature = service._sign_request_digest(checksummed_safe, self._digest())

        assert signature == "0x" + ("dd" * 64) + "1b"
        service.signer.sign_safe_message.assert_called_once_with(
            checksummed_safe,
            service.mech_config.ledger_config.chain_id,
            self._digest(),
        )
        # Client-mode signing path must not be exercised in agent mode
        service.signer.sign_message.assert_not_called()

    def test_agent_mode_signs_against_caller_provided_sender(self) -> None:
        """The signature is bound to the sender argument, not re-resolved.

        Threading ``sender`` through the API is the invariant that keeps
        the signed-over address identical to the address written into
        the payload and ``getRequestId``. Passing a distinct Safe address
        as ``sender`` (with the service configured for a different Safe)
        proves the sign path uses the caller's value rather than
        re-reading ``self.safe_address``.
        """
        service = _build_offchain_service(agent_mode=True)
        service.signer = create_mock_signer(safe_signature=b"\xdd" * 64 + b"\x1b")
        other_safe = ensure_checksummed_address("0x" + "cc" * 20)

        service._sign_request_digest(other_safe, self._digest())

        service.signer.sign_safe_message.assert_called_once_with(
            other_safe,
            service.mech_config.ledger_config.chain_id,
            self._digest(),
        )

    def test_agent_mode_rejects_wrong_length_safe_signature(self) -> None:
        """Agent-mode signing fails fast on a non-65-byte SafeMessage signature."""
        service = _build_offchain_service(agent_mode=True)
        service.signer = create_mock_signer(safe_signature=b"\xdd" * 64)

        with pytest.raises(ValueError, match="expected\\s+65 bytes"):
            service._sign_request_digest(
                ensure_checksummed_address("0x" + "5a" * 20), self._digest()
            )

    @pytest.mark.parametrize("bad_v", [0, 1, 26, 29, 255])
    def test_agent_mode_rejects_unsupported_v_byte(self, bad_v: int) -> None:
        """Agent-mode signing requires v in {27, 28}.

        Safe reads ``v=0`` as a contract signature marker and ``v=1`` as
        an approved-hash marker, both distinct from raw ECDSA recovery.
        A signer that returns any other ``v`` would be misinterpreted
        on-chain and fail as an opaque ``GS026``; the guard converts
        that into an actionable local error.
        """
        service = _build_offchain_service(agent_mode=True)
        bad_sig = b"\xdd" * 64 + bytes([bad_v])
        service.signer = create_mock_signer(safe_signature=bad_sig)

        with pytest.raises(ValueError, match=r"v in \{27, 28\}"):
            service._sign_request_digest(
                ensure_checksummed_address("0x" + "5a" * 20), self._digest()
            )

    def test_agent_mode_requires_signer_with_sign_safe_message(self) -> None:
        """A signer missing sign_safe_message surfaces an actionable error.

        Downstream :class:`Signer` implementations predating this method
        (e.g. Pearl BYOA signers) would otherwise die with a bare
        ``AttributeError`` deep in the request flow; catching the missing
        attribute early names the requirement and points to the protocol.
        """
        service = _build_offchain_service(agent_mode=True)
        # A plain object without sign_safe_message. Using ``spec`` on a
        # MagicMock would also work, but this keeps the point explicit.

        class _LegacySigner:
            address = "0x" + "1" * 40

            def sign_message(self, message: bytes) -> bytes:
                return b"\x00" * 65

        service.signer = _LegacySigner()  # type: ignore[assignment]

        with pytest.raises(ValueError, match="sign_safe_message"):
            service._sign_request_digest(
                ensure_checksummed_address("0x" + "5a" * 20), self._digest()
            )


class TestOffchainSenderResolution:
    """Tests for the requester address bound into offchain requests."""

    def test_client_mode_binds_signer_address(self) -> None:
        """Client mode uses the EOA as the offchain requester."""
        service = _build_offchain_service()
        service.signer = create_mock_signer(address="0x" + "1" * 40)

        sender = service.requester()

        assert sender == ensure_checksummed_address("0x" + "1" * 40)

    def test_agent_mode_binds_safe_address(self) -> None:
        """Agent mode uses the Safe as the offchain requester of record.

        This is the invariant that keeps the offchain flow consistent with
        the onchain flow — where the Safe is ``msg.sender`` and therefore
        the requester recorded by the marketplace and indexed by the
        subgraph. Binding the signer EOA in agent mode would split the two
        views of "who owns this request".
        """
        safe = "0x" + "5a" * 20
        service = _build_offchain_service(agent_mode=True, safe_address=safe)
        service.signer = create_mock_signer(address="0x" + "1" * 40)

        sender = service.requester()

        assert sender == ensure_checksummed_address(safe)
        # Assert the EOA is NOT bound — that would be the client-mode value
        # and would fail Safe.isValidSignature downstream.
        assert sender != ensure_checksummed_address("0x" + "1" * 40)

    def test_agent_mode_without_safe_address_raises(self) -> None:
        """Agent mode without a Safe address surfaces a clear configuration error."""
        service = _build_offchain_service(agent_mode=True)
        service.safe_address = None

        with pytest.raises(ValueError, match="require a Safe address"):
            service.requester()


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
            "deliveries": {},
            "receipt": None,
        }

        with patch.object(service, "marketplace_contract", return_value=MagicMock()):
            with patch.object(
                service,
                "mech_info",
                return_value=MechInfo(MECH_ADDRESS, 1, PaymentType.NATIVE, 10**17),
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


def _build_offchain_service(
    agent_mode: bool = False,
    safe_address: str = "0x" + "5a" * 20,
) -> MarketplaceService:
    """Build a MarketplaceService with its heavy init dependencies mocked.

    :param agent_mode: True to build an agent-mode (Safe-bound) service,
        False for the default client-mode (EOA) service
    :param safe_address: Safe address to bind as requester of record
        (agent mode only, ignored in client mode)
    :return: MarketplaceService instance
    """
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
        kwargs: Dict[str, Any] = {
            "chain_config": "gnosis",
            "agent_mode": agent_mode,
            "crypto": create_mock_crypto(),
        }
        if agent_mode:
            kwargs["safe_address"] = safe_address
            kwargs["ethereum_client"] = MagicMock()
        return MarketplaceService(**kwargs)


MECH_NAME = "9" * 40 + "-100.mech.valory.xyz"
OPERATOR_TERMS = "https://operator.test/terms"
IDENTIFICATION = "mech_client.domain.identification"
SERVICE = "mech_client.services.marketplace_service"


def _resolver(outcome: str) -> Any:
    """
    Build a getaddrinfo stand-in for one identification outcome.

    :param outcome: "valory", "not_valory" or "broken"
    :return: A side effect for socket.getaddrinfo
    """

    def getaddrinfo(name: str, _port: Any) -> list:
        if outcome == "broken":
            raise OSError("network unreachable")
        if outcome == "valory" and name == MECH_NAME:
            return [("ok",)]
        raise socket.gaierror(socket.EAI_NONAME, "not known")

    return getaddrinfo


class TestTermsNotice:
    """Before signing: the Valory notice for a Valory mech, else the operator's own link."""

    @staticmethod
    def _service() -> MarketplaceService:
        """Build a service whose tool manager runs the real terms report."""
        service = _build_offchain_service()
        service.tool_manager = MagicMock()
        service.tool_manager.offchain_url_from_metadata = (
            ToolManager.offchain_url_from_metadata
        )
        manager = ToolManager.__new__(ToolManager)
        manager.mech_config = service.mech_config
        service.tool_manager.terms_report = manager.terms_report
        return service

    def _notice(self, outcome: str, metadata: Any) -> tuple:
        """
        Run the notice for one DNS outcome and document.

        :param outcome: The identification outcome to simulate
        :param metadata: The mech's metadata document
        :return: The info and warning mocks
        """
        service = self._service()
        # mech_client sets propagate=False on its root logger, so patch the
        # module logger directly rather than relying on caplog.
        with (
            patch(
                f"{IDENTIFICATION}.socket.getaddrinfo", side_effect=_resolver(outcome)
            ),
            patch(f"{IDENTIFICATION}.logger"),
            patch(f"{SERVICE}.logger.info") as info,
            patch(f"{SERVICE}.logger.warning") as warning,
        ):
            service._log_terms_notice(
                MECH_ADDRESS, metadata
            )  # pylint: disable=protected-access
        return info, warning

    def test_valory_mech_gets_the_fixed_notice(self) -> None:
        """A Valory operated mech shows the approved wording, verbatim, and nothing else."""
        info, warning = self._notice("valory", {"termsUrl": OPERATOR_TERMS})
        info.assert_called_once_with(VALORY_TERMS_NOTICE)
        warning.assert_not_called()
        message = info.call_args[0][0]
        # The wording is fixed: a requester agrees by submitting the request,
        # so the notice must not read as asking them to accept anything.
        assert "By submitting a request to this Mech" in message
        assert "Valory AG's Mech Terms (v1.0)" in message
        assert "https://www.valory.xyz/terms/mechs" in message
        assert "proceeding" not in message

    def test_another_operator_s_link_is_passed_on_as_published(self) -> None:
        """A mech Valory does not operate shows its operator's link, stating no terms."""
        info, warning = self._notice("not_valory", {"termsUrl": OPERATOR_TERMS})
        info.assert_called_once_with(
            f"The operator of this Mech publishes terms at {OPERATOR_TERMS}"
        )
        warning.assert_not_called()
        message = info.call_args[0][0]
        assert "agree" not in message
        assert "Valory" not in message

    def test_a_failed_check_warns_and_still_passes_on_the_link(self) -> None:
        """A resolver hiccup is visible, and the published link still reaches the user."""
        info, warning = self._notice("broken", {"termsUrl": OPERATOR_TERMS})
        warning.assert_called_once_with(IDENTIFICATION_NOTE)
        info.assert_called_once_with(
            f"The operator of this Mech publishes terms at {OPERATOR_TERMS}"
        )

    @pytest.mark.parametrize(
        "metadata",
        [None, {}, {"termsUrl": "http://operator.test/terms"}],
        ids=["no_document", "no_link", "invalid_link"],
    )
    def test_another_operator_without_a_valid_link_gets_no_notice(
        self, metadata: Any
    ) -> None:
        """No valid published link means nothing to pass on, and nothing is said."""
        info, warning = self._notice("not_valory", metadata)
        info.assert_not_called()
        warning.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_request_states_the_terms_before_the_offchain_send(self) -> None:
        """The notice precedes the offchain send, for the priority mech and its document."""
        service = self._service()
        document = {"url": "https://mech.example"}
        service.tool_manager.read_tools_metadata.return_value = MetadataRead(
            document, None
        )
        calls: list = []

        async def fake_offchain(**_kwargs: Any) -> Dict[str, Any]:
            calls.append("send")
            return {
                "tx_hash": None,
                "request_ids": [],
                "deliveries": {},
                "receipt": None,
            }

        def record_notice(mech_address: str, metadata: Any) -> Dict[str, Any]:
            calls.append(("terms", mech_address, metadata))
            return {"valory_operated": True, "terms": VALORY_TERMS_NOTICE}

        service.tool_manager.terms_report = record_notice
        with (
            patch.object(service, "marketplace_contract", return_value=MagicMock()),
            patch.object(
                service,
                "mech_info",
                return_value=MechInfo(MECH_ADDRESS, 7, PaymentType.NATIVE, 1),
            ),
            patch.object(service, "_validate_tools"),
            patch.object(service, "_send_offchain_request", side_effect=fake_offchain),
            patch(f"{SERVICE}.logger.info"),
        ):
            await service.send_request(
                prompts=("hello",),
                tools=("tool",),
                priority_mech=MECH_ADDRESS,
                use_offchain=True,
            )
        assert calls == [("terms", MECH_ADDRESS, document), "send"]

    @pytest.mark.asyncio
    @patch("mech_client.services.marketplace_service.PaymentStrategyFactory")
    @patch("mech_client.services.marketplace_service.push_metadata_to_ipfs")
    async def test_send_request_states_the_terms_before_the_onchain_upload_and_send(
        self, mock_push: MagicMock, _mock_factory: MagicMock
    ) -> None:
        """On-chain: the notice precedes the IPFS upload and the marketplace send."""
        service = self._service()
        service.tool_manager.read_tools_metadata.return_value = MetadataRead({}, None)
        calls: list = []

        def fake_push(*_args: Any, **_kwargs: Any) -> tuple:
            calls.append("ipfs")
            return "0x" + "b" * 64, "ipfs://hash"

        def fake_send(*_args: Any, **_kwargs: Any) -> str:
            calls.append("send")
            raise RuntimeError("stop after send")

        def record_notice(*_args: Any) -> Dict[str, Any]:
            calls.append("terms")
            return {"valory_operated": False}

        mock_push.side_effect = fake_push
        service.tool_manager.terms_report = record_notice
        with (
            patch.object(service, "marketplace_contract", return_value=MagicMock()),
            patch.object(
                service,
                "mech_info",
                return_value=MechInfo(MECH_ADDRESS, 7, PaymentType.NATIVE, 1),
            ),
            patch.object(service, "_validate_tools"),
            patch.object(service, "_send_marketplace_request", side_effect=fake_send),
            patch(f"{SERVICE}.logger.info"),
        ):
            with pytest.raises(RuntimeError, match="stop after send"):
                await service.send_request(
                    prompts=("hello",), tools=("tool",), priority_mech=MECH_ADDRESS
                )
        assert calls == ["terms", "ipfs", "send"]


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

    @pytest.fixture(autouse=True)
    def confirmed_deposits(self) -> Any:
        """Report every auto-deposit transaction as mined successfully."""
        with patch(f"{SERVICE}.wait_for_receipt", return_value={"status": 1}):
            yield

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
        with patch("mech_client.services.marketplace_service.logger.info") as mock_info:
            MarketplaceService._log_payment_receipt(resp)
        mock_info.assert_called_once()
        assert "abc123" in mock_info.call_args[0][0]

    def test_log_payment_receipt_absent_emits_no_record(self) -> None:
        """No Payment-Receipt header means no log line written."""
        resp = _mock_http_response(200, headers={})
        with patch("mech_client.services.marketplace_service.logger.info") as mock_info:
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
            # The child service must inherit the signer (external-signer path
            # has no crypto to fall back on)
            mock_ds.assert_called_once_with(
                chain_config=service.chain_config,
                agent_mode=service.agent_mode,
                safe_address=service.safe_address,
                ethereum_client=service.ethereum_client,
                signer=service.signer,
                rpc_url=None,
            )
            mock_ds.return_value.deposit_native.assert_called_once_with(70)

    def test_auto_deposit_adds_a_negative_balance_to_the_shortfall(self) -> None:
        """A balance reported net of reservations may be negative; it raises the deposit."""
        service = _build_offchain_service()
        resp = _mock_http_response(
            402, {"required": "100", "currentBalance": "-30", "payTo": "0xbt"}
        )
        challenge = MarketplaceService._parse_402_challenge(resp)
        assert challenge.current_balance == -30
        assert challenge.shortfall == 130
        with patch("mech_client.services.deposit_service.DepositService") as mock_ds:
            service._auto_deposit_for_402(
                PaymentType.NATIVE, challenge, max_delivery_rate=100
            )
            mock_ds.return_value.deposit_native.assert_called_once_with(130)

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
            with pytest.raises(ValueError, match=r"refused.*1001.*safety cap of 1000"):
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
        """A 402 whose ``required`` is above the signed cap is refused, no retry, no deposit."""
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
            with pytest.raises(ValueError, match=r"more than the signed cap of 1000"):
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


# ---------------------------------------------------------------------------
# Offchain nonce modes: an explicit request (the default) signs a nonce the
# requester chooses; a sequential request is the wire payload every mech
# accepts today, and what an explicit request falls back to.
# ---------------------------------------------------------------------------

# Above the 0.01 default in mechs.json: the maximum a mech advertises is what
# gets signed, whatever the chain-wide default says.
MECH_MAX_RATE = 15 * 10**16
CONTENT_HASH = "0x" + "b" * 64
CONTENT_DATA = '{"prompt":"hello"}'
MARKETPLACE_NONCE = 5
# what the deployed marketplace answers for the first sequential request
SEQUENTIAL_REQUEST_ID = _derived_id(
    MARKETPLACE_NONCE, data=CONTENT_HASH, rate=MECH_MAX_RATE
)
# Chain time the contract stub reports; explicit deadlines are measured from it.
LATEST_BLOCK_TIMESTAMP = 1_700_000_000
EXPECTED_DEADLINE = LATEST_BLOCK_TIMESTAMP + EXPLICIT_NONCE_DEADLINE_SECONDS
CHOSEN_NONCE = 0xC0FFEE
# what the deployed marketplace answers for the first explicit request
EXPLICIT_REQUEST_ID = _explicit_id(
    CHOSEN_NONCE, EXPECTED_DEADLINE, data=CONTENT_HASH, rate=MECH_MAX_RATE
)
PAYMENT_TYPE_HEX = "0x" + PaymentType.NATIVE.value
FETCH_IPFS_HASH = "mech_client.infrastructure.ipfs.metadata.fetch_ipfs_hash"
# Every field of the payload a sequential request has always sent, in order.
SEQUENTIAL_PAYLOAD_FIELDS = [
    "sender",
    "signature",
    "ipfs_hash",
    "request_id",
    "delivery_rate",
    "nonce",
    "ipfs_data",
]


def _nonce_mode_contract() -> MagicMock:
    """Marketplace contract stub answering the counter and both request-id views.

    :return: the contract mock
    """
    contract = _honest(MagicMock())
    contract.functions.mapNonces.return_value.call.return_value = MARKETPLACE_NONCE
    _honest_explicit(contract)
    contract.w3.eth.get_block.return_value = {"timestamp": LATEST_BLOCK_TIMESTAMP}
    return contract


def _accepted() -> MagicMock:
    """The mech's 200 for an accepted request.

    :return: a mock response
    """
    return _mock_http_response(200, {"status": "ok"})


def _refused(status_code: int, reason: str) -> MagicMock:
    """The mech's rejection body for ``status_code``.

    :param status_code: HTTP status of the rejection
    :param reason: the ``reason`` field of the JSON body
    :return: a mock response
    """
    response = _mock_http_response(status_code, {"reason": reason})
    response.reason = "Service Unavailable"
    return response


async def _send_offchain_in_mode(
    service: MarketplaceService,
    contract: MagicMock,
    responses: List[MagicMock],
    nonce_mode: Any = NONCE_MODE_EXPLICIT,
    prompts: Tuple[str, ...] = ("hello",),
    fallback_rate: Optional[int] = None,
    deadline_seconds: int = EXPLICIT_NONCE_DEADLINE_SECONDS,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Send ``prompts`` offchain against canned HTTP responses.

    :param service: the service under test
    :param contract: the marketplace contract stub
    :param responses: what each successive POST answers
    :param nonce_mode: the nonce mode to send with
    :param prompts: one prompt per request
    :param fallback_rate: the advertised maximum passed for a derived cap
    :param deadline_seconds: the settlement window to sign
    :return: the result and every payload POSTed, in order
    """
    watcher = AsyncMock()
    watcher.watch.return_value = {}
    with (
        patch(FETCH_IPFS_HASH, return_value=(CONTENT_HASH, "full-hash", CONTENT_DATA)),
        patch(f"{SERVICE}.OffchainDeliveryWatcher", return_value=watcher),
        patch(f"{SERVICE}.requests") as mock_requests,
    ):
        mock_requests.post.side_effect = responses
        mock_requests.exceptions.RequestException = (
            requests.exceptions.RequestException
        )
        result = await service._send_offchain_request(  # pylint: disable=protected-access
            marketplace_contract=contract,
            prompts=prompts,
            tools=("some-tool",) * len(prompts),
            priority_mech_address=MECH_ADDRESS,
            max_delivery_rate=MECH_MAX_RATE,
            payment_type=PaymentType.NATIVE,
            response_timeout=300,
            mech_offchain_url="https://mech.example.com",
            extra_attributes=None,
            timeout=30.0,
            nonce_mode=nonce_mode,
            fallback_rate=fallback_rate,
            deadline_seconds=deadline_seconds,
        )
        payloads = [call.kwargs["data"] for call in mock_requests.post.call_args_list]
    return dict(result), payloads


# A request-id vector produced by the mech's own reimplementation of the
# marketplace views (``task_execution/utils/request_id.py``,
# ``compute_request_id_with_nonce`` / ``compute_request_id``) for these
# inputs. The stub views below encode whatever the client passes them in
# the marketplace's field order (the explicit one as the EIP-712
# ``ExplicitNonceDelivery`` struct), so the payload only reproduces the
# vector if the client passes the fields in that order.
VECTOR_MARKETPLACE = "0x4554fE75c1f5576c1d7F765B2A036c199Adae329"
VECTOR_MECH = "0x77af31De935740567Cf4fF1986D04B2c964A786a"
VECTOR_DATA = "0x" + "b" * 64
VECTOR_RATE = 10**16
VECTOR_PAYMENT_TYPE = "0xba699a34be8fe0e7725e93dcbce1701b0211a8ca61330aaeb8a05bf2ec7abed1"
VECTOR_NONCE = 0xDEADBEEF
VECTOR_DEADLINE = 1_900_000_000
VECTOR_DOMAIN_SEPARATOR = bytes.fromhex("5a" * 32)
# getDomainSeparatorWithNonce() for VECTOR_MARKETPLACE on chain 100 (the
# service's configured chain): EIP-712 domain "MechMarketplace", version "2".
VECTOR_EXPLICIT_DOMAIN_SEPARATOR = keccak(
    eth_abi.encode(
        ["bytes32", "bytes32", "bytes32", "uint256", "address"],
        [
            keccak(
                text="EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"
            ),
            keccak(text="MechMarketplace"),
            keccak(text="2"),
            100,
            VECTOR_MARKETPLACE,
        ],
    )
)
VECTOR_EXPLICIT_REQUEST_ID = "736a7469974e4d5c87b33155d2999ba961fd4c60d26a9bdc25a7cc626cdecfa6"
VECTOR_SEQUENTIAL_REQUEST_ID = "fd5fd4b72cc0d1964c4ce14ae2764ab978a20cdb48fa65c3a00b80c0e1d41800"
EXPLICIT_NONCE_TYPE_HASH = keccak(
    text=(
        "ExplicitNonceDelivery(address mech,address requester,bytes data,"
        "uint256 maxDeliveryRate,bytes32 paymentType,uint256 nonce,uint256 deadline)"
    )
)


def _marketplace_request_id(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    explicit: bool,
    mech: str,
    requester: str,
    data: Any,
    rate: int,
    payment_type: Any,
    nonce: int,
    deadline: Optional[int] = None,
) -> bytes:
    """Mirror ``getRequestId`` / ``getRequestIdWithNonce`` over the client's view arguments.

    :param explicit: whether to hash the EIP-712 ``ExplicitNonceDelivery`` struct
        (the explicit view) rather than the sequential layout
    :param mech: the mech address as the client passed it
    :param requester: the requester address as the client passed it
    :param data: the request data as the client passed it (hex string or bytes)
    :param rate: the signed cap
    :param payment_type: the payment type as the client passed it (hex string or bytes)
    :param nonce: the nonce
    :param deadline: the settlement deadline (explicit view only)
    :return: the 32-byte request id
    """
    data_bytes = bytes.fromhex(data[2:]) if isinstance(data, str) else bytes(data)
    pt_bytes = (
        bytes.fromhex(payment_type[2:])
        if isinstance(payment_type, str)
        else bytes(payment_type)
    )
    if explicit:
        fields = eth_abi.encode(
            ["bytes32", "address", "address", "bytes32", "uint256", "bytes32", "uint256", "uint256"],
            [EXPLICIT_NONCE_TYPE_HASH, mech, requester, keccak(data_bytes), rate, pt_bytes, nonce, deadline],
        )
    else:
        fields = eth_abi.encode(
            ["address", "address", "address", "bytes32", "uint256", "bytes32", "uint256"],
            [VECTOR_MARKETPLACE, mech, requester, keccak(data_bytes), rate, pt_bytes, nonce],
        )
    domain = VECTOR_EXPLICIT_DOMAIN_SEPARATOR if explicit else VECTOR_DOMAIN_SEPARATOR
    return keccak(b"\x19\x01" + domain + keccak(fields))


def _vector_contract() -> MagicMock:
    """Marketplace contract stub whose request-id views really hash their arguments.

    :return: the contract mock
    """
    contract = MagicMock()

    def _view(explicit: bool) -> Any:
        def view(*args: Any) -> MagicMock:
            call = MagicMock()
            call.call.return_value = _marketplace_request_id(explicit, *args)
            return call

        return view

    contract.functions.getRequestIdWithNonce.side_effect = _view(True)
    contract.functions.getRequestId.side_effect = _view(False)
    return contract


class TestOffchainNonceModes:
    """How an offchain request is numbered, signed and, when refused, resent."""

    @pytest.mark.parametrize(
        "nonce_mode, expected",
        [
            (NONCE_MODE_EXPLICIT, VECTOR_EXPLICIT_REQUEST_ID),
            (NONCE_MODE_SEQUENTIAL, VECTOR_SEQUENTIAL_REQUEST_ID),
        ],
    )
    @pytest.mark.asyncio
    async def test_request_id_reproduces_the_mech_s_vector(
        self, nonce_mode: Any, expected: str
    ) -> None:
        """The view gets the fields in the marketplace's order and the explicit path carries the tag."""
        service = _build_offchain_service()
        service.signer = _real_signing_signer()
        contract = _vector_contract()
        contract.address = VECTOR_MARKETPLACE
        contract.functions.domainSeparator.return_value.call.return_value = (
            VECTOR_DOMAIN_SEPARATOR
        )
        contract.functions.mapNonces.return_value.call.return_value = VECTOR_NONCE
        contract.w3.eth.get_block.return_value = {
            "timestamp": VECTOR_DEADLINE - EXPLICIT_NONCE_DEADLINE_SECONDS
        }

        with (
            patch(
                FETCH_IPFS_HASH,
                return_value=(VECTOR_DATA, "full-hash", CONTENT_DATA),
            ),
            patch(f"{SERVICE}.secrets.randbits", return_value=VECTOR_NONCE),
            patch(f"{SERVICE}.OffchainDeliveryWatcher", return_value=AsyncMock()),
            patch(f"{SERVICE}.requests") as mock_requests,
        ):
            mock_requests.post.return_value = _accepted()
            await service._send_offchain_request(  # pylint: disable=protected-access
                marketplace_contract=contract,
                prompts=("hello",),
                tools=("some-tool",),
                priority_mech_address=VECTOR_MECH,
                max_delivery_rate=VECTOR_RATE,
                payment_type=PaymentType.NATIVE,
                response_timeout=300,
                mech_offchain_url="https://mech.example.com",
                extra_attributes=None,
                timeout=30.0,
                nonce_mode=nonce_mode,
            )
        payload = mock_requests.post.call_args.kwargs["data"]

        assert payload["request_id"] == int(expected, 16)
        assert payload["nonce"] == VECTOR_NONCE
        explicit = nonce_mode == NONCE_MODE_EXPLICIT
        assert payload.get("nonce_mode") == (nonce_mode if explicit else None)
        assert payload.get("deadline") == (VECTOR_DEADLINE if explicit else None)

    @pytest.mark.asyncio
    async def test_an_unreadable_deadline_is_refused_before_signing(
        self,
    ) -> None:
        """The deadline is part of the signed digest, so a failed block read stops the request."""
        service = _build_offchain_service()
        service.signer = _real_signing_signer()
        contract = _nonce_mode_contract()
        contract.w3.eth.get_block.side_effect = OSError("rpc down")

        with pytest.raises(ValueError, match="Failed to derive the request id"):
            await _send_offchain_in_mode(service, contract, [_accepted()])

        service.signer.sign_message.assert_not_called()
        contract.functions.getRequestIdWithNonce.assert_not_called()

    def setup_method(self) -> None:
        """Build a client-mode service whose signatures really recover."""
        self.service = _build_offchain_service()
        self.service.signer = _real_signing_signer()
        self.sender = ensure_checksummed_address(_TEST_ACCOUNT.address)

    @pytest.mark.asyncio
    async def test_explicit_is_the_default_and_signs_a_chosen_nonce(self) -> None:
        """Without a mode, the id comes from ``getRequestIdWithNonce`` and the payload says so."""
        contract = _nonce_mode_contract()

        with patch(f"{SERVICE}.secrets.randbits", return_value=CHOSEN_NONCE) as randbits:
            result, payloads = await _send_offchain_in_mode(self.service, contract, [_accepted()])

        randbits.assert_called_once_with(EXPLICIT_NONCE_BITS)
        (payload,) = payloads
        assert list(payload) == SEQUENTIAL_PAYLOAD_FIELDS + ["nonce_mode", "deadline"]
        assert payload["nonce_mode"] == "explicit"
        assert payload["nonce"] == CHOSEN_NONCE
        assert payload["deadline"] == EXPECTED_DEADLINE
        assert payload["request_id"] == int.from_bytes(EXPLICIT_REQUEST_ID, "big")
        assert payload["delivery_rate"] == MECH_MAX_RATE
        assert payload["sender"] == self.sender
        assert payload["ipfs_hash"] == CONTENT_HASH
        assert payload["ipfs_data"] == CONTENT_DATA
        contract.functions.getRequestIdWithNonce.assert_called_once_with(
            MECH_ADDRESS, self.sender, CONTENT_HASH, MECH_MAX_RATE, PAYMENT_TYPE_HEX, CHOSEN_NONCE, EXPECTED_DEADLINE
        )
        contract.w3.eth.get_block.assert_called_once_with("latest")
        contract.functions.getRequestId.assert_not_called()
        contract.functions.mapNonces.assert_not_called()
        # The signature is over the explicit id, which the sequential path rejects.
        self.service.signer.sign_message.assert_called_once_with(EXPLICIT_REQUEST_ID)
        assert result["request_ids"] == [EXPLICIT_REQUEST_ID.hex()]

    @pytest.mark.asyncio
    async def test_a_chosen_deadline_is_the_one_signed(self) -> None:
        """A non-default window moves the signed deadline and so the signed id."""
        chosen = EXPLICIT_NONCE_DEADLINE_SECONDS * 2
        contract = _nonce_mode_contract()

        with patch(f"{SERVICE}.secrets.randbits", return_value=CHOSEN_NONCE):
            result, (payload,) = await _send_offchain_in_mode(
                self.service, contract, [_accepted()], deadline_seconds=chosen
            )

        signed = _explicit_id(
            CHOSEN_NONCE, LATEST_BLOCK_TIMESTAMP + chosen, data=CONTENT_HASH, rate=MECH_MAX_RATE
        )
        assert payload["deadline"] == LATEST_BLOCK_TIMESTAMP + chosen
        assert payload["request_id"] == int.from_bytes(signed, "big")
        assert result["request_ids"] == [signed.hex()]

    @pytest.mark.asyncio
    async def test_an_explicit_id_the_view_does_not_confirm_is_never_signed(
        self,
    ) -> None:
        """The explicit id is derived locally; a view answering anything else stops the request."""
        contract = _nonce_mode_contract()
        contract.functions.getRequestIdWithNonce.side_effect = None
        contract.functions.getRequestIdWithNonce.return_value.call.return_value = (
            b"\x66" * 32
        )
        hook = MagicMock()

        with (
            patch(f"{SERVICE}.secrets.randbits", return_value=CHOSEN_NONCE),
            patch(FETCH_IPFS_HASH, return_value=(CONTENT_HASH, "full-hash", CONTENT_DATA)),
            patch(f"{SERVICE}.requests") as mock_requests,
            pytest.raises(RequestIdMismatch) as e,
        ):
            await self.service._send_offchain_request(  # pylint: disable=protected-access
                marketplace_contract=contract,
                prompts=("hello",),
                tools=("some-tool",),
                priority_mech_address=MECH_ADDRESS,
                max_delivery_rate=MECH_MAX_RATE,
                payment_type=PaymentType.NATIVE,
                response_timeout=300,
                mech_offchain_url="https://mech.example.com",
                extra_attributes=None,
                timeout=30.0,
                on_request_id=hook,
            )

        assert (e.value.expected, e.value.reported, e.value.nonce) == (
            EXPLICIT_REQUEST_ID.hex(),
            "66" * 32,
            CHOSEN_NONCE,
        )
        hook.assert_not_called()
        self.service.signer.sign_message.assert_not_called()
        mock_requests.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_explicit_nonces_are_drawn_fresh_per_request(self) -> None:
        """Each request in a batch gets its own 256-bit nonce."""
        _, payloads = await _send_offchain_in_mode(
            self.service, _nonce_mode_contract(), [_accepted(), _accepted()], prompts=("one", "two")
        )

        nonces = [payload["nonce"] for payload in payloads]
        assert nonces[0] != nonces[1]
        assert all(0 <= nonce < 2**EXPLICIT_NONCE_BITS for nonce in nonces)

    @pytest.mark.asyncio
    async def test_sequential_request_is_the_payload_every_mech_accepts(self) -> None:
        """Opting into sequential sends exactly today's fields, in today's order."""
        contract = _nonce_mode_contract()

        result, payloads = await _send_offchain_in_mode(
            self.service, contract, [_accepted()], nonce_mode=NONCE_MODE_SEQUENTIAL
        )

        (payload,) = payloads
        assert list(payload) == SEQUENTIAL_PAYLOAD_FIELDS
        assert payload["sender"] == self.sender
        assert payload["ipfs_hash"] == CONTENT_HASH
        assert payload["request_id"] == int.from_bytes(SEQUENTIAL_REQUEST_ID, "big")
        assert payload["delivery_rate"] == MECH_MAX_RATE
        assert payload["nonce"] == MARKETPLACE_NONCE
        assert payload["ipfs_data"] == CONTENT_DATA
        assert payload["signature"] == (
            "0x" + bytes(_TEST_ACCOUNT.unsafe_sign_hash(SEQUENTIAL_REQUEST_ID).signature).hex()
        )
        contract.functions.mapNonces.assert_called_once_with(self.sender)
        contract.functions.getRequestId.assert_called_once_with(
            MECH_ADDRESS, self.sender, CONTENT_HASH, MECH_MAX_RATE, PAYMENT_TYPE_HEX, MARKETPLACE_NONCE
        )
        contract.functions.getRequestIdWithNonce.assert_not_called()
        assert result["request_ids"] == [SEQUENTIAL_REQUEST_ID.hex()]

    @pytest.mark.asyncio
    async def test_sequential_batch_numbers_its_requests_from_one_counter_read(self) -> None:
        """A sequential batch reads ``mapNonces`` once and numbers requests contiguously."""
        contract = _nonce_mode_contract()

        _, payloads = await _send_offchain_in_mode(
            self.service,
            contract,
            [_accepted(), _accepted()],
            nonce_mode=NONCE_MODE_SEQUENTIAL,
            prompts=("one", "two"),
        )

        assert [payload["nonce"] for payload in payloads] == [MARKETPLACE_NONCE, MARKETPLACE_NONCE + 1]
        contract.functions.mapNonces.assert_called_once_with(self.sender)

    @pytest.mark.asyncio
    async def test_the_mech_maximum_is_signed_even_above_the_chain_default(self) -> None:
        """The advertised maximum is the cap, not the 0.01 default in mechs.json."""
        assert MECH_MAX_RATE > self.service.mech_config.price

        _, payloads = await _send_offchain_in_mode(self.service, _nonce_mode_contract(), [_accepted()])

        assert payloads[0]["delivery_rate"] == MECH_MAX_RATE

    @pytest.mark.asyncio
    async def test_a_mech_without_explicit_nonces_gets_the_sequential_request(self) -> None:
        """The disabled-path 503 resends the same content with the marketplace counter."""
        contract = _nonce_mode_contract()

        with patch(f"{SERVICE}.logger.warning") as warning:
            result, payloads = await _send_offchain_in_mode(
                self.service,
                contract,
                [_refused(503, EXPLICIT_NONCE_DISABLED_REASON), _accepted()],
            )

        explicit, sequential = payloads
        assert explicit["nonce_mode"] == "explicit"
        assert list(sequential) == SEQUENTIAL_PAYLOAD_FIELDS
        assert sequential["nonce"] == MARKETPLACE_NONCE
        assert sequential["ipfs_data"] == CONTENT_DATA
        assert sequential["request_id"] == int.from_bytes(SEQUENTIAL_REQUEST_ID, "big")
        # The counter is read only once the mech has turned explicit nonces away
        contract.functions.mapNonces.assert_called_once_with(self.sender)
        assert self.service.signer.sign_message.call_args.args[0] == SEQUENTIAL_REQUEST_ID
        assert result["request_ids"] == [SEQUENTIAL_REQUEST_ID.hex()]
        assert result["nonces"] == [MARKETPLACE_NONCE]
        warning.assert_called_once()

    @pytest.mark.parametrize(
        "fallback_rate, resent_rate",
        [
            (MECH_MAX_RATE // 10, MECH_MAX_RATE // 10),
            (MECH_MAX_RATE - 1, MECH_MAX_RATE - 1),
            (MECH_MAX_RATE, MECH_MAX_RATE),
            (MECH_MAX_RATE * 2, MECH_MAX_RATE),
            (None, MECH_MAX_RATE),
        ],
    )
    @pytest.mark.asyncio
    async def test_the_sequential_resend_signs_the_lower_of_cap_and_advertised_maximum(
        self, fallback_rate: Optional[int], resent_rate: int
    ) -> None:
        """A derived cap falls to the advertised maximum on the resend; a chosen cap is kept."""
        contract = _nonce_mode_contract()

        _, (explicit, sequential) = await _send_offchain_in_mode(
            self.service,
            contract,
            [_refused(503, EXPLICIT_NONCE_DISABLED_REASON), _accepted()],
            fallback_rate=fallback_rate,
        )

        assert explicit["delivery_rate"] == MECH_MAX_RATE
        assert sequential["delivery_rate"] == resent_rate
        assert sequential["request_id"] == int.from_bytes(
            _derived_id(MARKETPLACE_NONCE, data=CONTENT_HASH, rate=resent_rate), "big"
        )

    @pytest.mark.asyncio
    async def test_the_fallback_covers_the_rest_of_the_batch(self) -> None:
        """After one refusal the remaining requests go sequential straight away."""
        contract = _nonce_mode_contract()

        _, payloads = await _send_offchain_in_mode(
            self.service,
            contract,
            [_refused(503, EXPLICIT_NONCE_DISABLED_REASON), _accepted(), _accepted()],
            prompts=("one", "two"),
        )

        assert [payload.get("nonce_mode") for payload in payloads] == ["explicit", None, None]
        assert [payload["nonce"] for payload in payloads[1:]] == [MARKETPLACE_NONCE, MARKETPLACE_NONCE + 1]
        contract.functions.mapNonces.assert_called_once_with(self.sender)
        assert contract.functions.getRequestIdWithNonce.call_count == 1

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "status_code, reason",
        [
            (503, "ledger unavailable"),
            (503, ""),
            (401, "request id already recorded on-chain"),
            (400, EXPLICIT_NONCE_DISABLED_REASON),
        ],
    )
    async def test_other_rejections_of_an_explicit_request_are_reported_not_retried(
        self, status_code: int, reason: str
    ) -> None:
        """Only the disabled-path 503 triggers the fallback; anything else is an error."""
        contract = _nonce_mode_contract()

        with pytest.raises(ValueError, match=f"Offchain request rejected: .*HTTP {status_code}"):
            await _send_offchain_in_mode(self.service, contract, [_refused(status_code, reason)])

        contract.functions.mapNonces.assert_not_called()
        contract.functions.getRequestId.assert_not_called()

    @pytest.mark.asyncio
    async def test_a_sequential_request_the_mech_refuses_is_an_error(self) -> None:
        """A disabled-path 503 can only mean a fallback for an explicit request."""
        contract = _nonce_mode_contract()

        with pytest.raises(ValueError, match="HTTP 503"):
            await _send_offchain_in_mode(
                self.service,
                contract,
                [_refused(503, EXPLICIT_NONCE_DISABLED_REASON)],
                nonce_mode=NONCE_MODE_SEQUENTIAL,
            )

        assert contract.functions.getRequestId.call_count == 1


class TestSendRequestNonceMode:
    """``send_request`` checks the nonce mode before touching the chain and passes it on."""

    @pytest.mark.asyncio
    async def test_an_unknown_mode_is_refused_before_any_chain_read(self) -> None:
        """A typo in the mode is an error, not a request in the default mode."""
        service = _build_offchain_service()

        with patch.object(service, "marketplace_contract") as contract:
            with pytest.raises(ValueError, match="Unknown nonce_mode 'random'"):
                await service.send_request(
                    prompts=("p",), tools=("t",), use_offchain=True, nonce_mode="random"  # type: ignore[arg-type]
                )

        contract.assert_not_called()

    @pytest.mark.asyncio
    async def test_explicit_mode_with_caller_nonces_is_refused_before_any_chain_read(
        self,
    ) -> None:
        """Caller nonces are marketplace counter values, so they cannot be explicit."""
        service = _build_offchain_service()

        with patch.object(service, "marketplace_contract") as contract:
            with pytest.raises(ValueError, match="need nonce_mode='sequential'"):
                await service.send_request(
                    prompts=("p",),
                    tools=("t",),
                    use_offchain=True,
                    nonces=[MARKETPLACE_NONCE],
                    nonce_mode=NONCE_MODE_EXPLICIT,
                )

        contract.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "kwargs, expected",
        [
            ({}, NONCE_MODE_EXPLICIT),
            ({"nonce_mode": NONCE_MODE_SEQUENTIAL}, NONCE_MODE_SEQUENTIAL),
            ({"nonces": [MARKETPLACE_NONCE]}, NONCE_MODE_SEQUENTIAL),
        ],
    )
    async def test_the_mode_reaches_the_offchain_sender(
        self, kwargs: Dict[str, Any], expected: str
    ) -> None:
        """Explicit unless the caller opts into sequential or brings its own nonces."""
        service = _build_offchain_service()
        service.tool_manager = MagicMock()

        with (
            patch.object(service, "marketplace_contract", return_value=MagicMock()),
            patch.object(
                service,
                "mech_info",
                return_value=MechInfo(MECH_ADDRESS, 1, PaymentType.NATIVE, MECH_MAX_RATE),
            ),
            patch.object(service, "_validate_tools"),
            patch.object(service, "_send_offchain_request", new_callable=AsyncMock) as offchain,
        ):
            await service.send_request(prompts=("p",), tools=("t",), use_offchain=True, **kwargs)

        assert offchain.call_args.kwargs["nonce_mode"] == expected
        assert offchain.call_args.kwargs["max_delivery_rate"] == MECH_MAX_RATE


EXPECTED_COST = 12 * 10**15
EXPECTED_COST_B = 30 * 10**15
OWN_CAP = 7 * 10**15
COSTED_MANIFEST = {
    "toolMetadata": {
        "tool-a": {"expectedCost": {"asset": "native", "amount": str(EXPECTED_COST)}},
        "tool-b": {"expectedCost": {"asset": "native", "amount": str(EXPECTED_COST_B)}},
        "tool-usdc": {"expectedCost": {"asset": "usdc", "amount": "25000"}},
    }
}


class TestResolveSignedRate:
    """The rate signed into a batch: the requester's cap off-chain, the mech's charge on-chain."""

    def setup_method(self) -> None:
        """Build a client-mode service."""
        self.service = _build_offchain_service()

    def _resolve(self, tools: Tuple[str, ...], **overrides: Any) -> int:
        """
        Resolve the signed rate for ``tools`` against the costed manifest.

        :param tools: the tool of each request
        :param overrides: any of the resolver's keyword arguments
        :return: the rate the batch signs
        """
        kwargs: Dict[str, Any] = {
            "tools": tools,
            "metadata": COSTED_MANIFEST,
            "payment_type": PaymentType.NATIVE,
            "advertised_max": MECH_MAX_RATE,
            "max_cost": None,
            "use_offchain": True,
        }
        kwargs.update(overrides)
        return self.service._resolve_signed_rate(**kwargs)  # pylint: disable=protected-access

    def test_a_chosen_cap_is_signed_as_given_offchain(self) -> None:
        """``max_cost`` wins over the manifest and the advertised maximum, even below both."""
        assert OWN_CAP < EXPECTED_COST < MECH_MAX_RATE
        assert self._resolve(("tool-a",), max_cost=OWN_CAP) == OWN_CAP

    def test_without_a_cap_the_default_is_a_multiple_of_the_expected_cost(self) -> None:
        """The manifest's expected cost, times the default factor, replaces the advertised maximum."""
        with patch(f"{SERVICE}.logger.warning") as warning:
            rate = self._resolve(("tool-a",))
        assert rate == DEFAULT_CAP_FACTOR * EXPECTED_COST
        assert rate != MECH_MAX_RATE
        warning.assert_not_called()

    def test_a_batch_signs_the_largest_cap_among_its_tools(self) -> None:
        """One rate per batch, so it is the one that covers every request in it."""
        rate = self._resolve(("tool-a", "tool-b", "tool-a"))
        assert rate == DEFAULT_CAP_FACTOR * EXPECTED_COST_B

    @pytest.mark.parametrize(
        "metadata",
        [{}, {"toolMetadata": {"other": {"expectedCost": {"asset": "native", "amount": "1"}}}}],
        ids=["empty_manifest", "another_tool_only"],
    )
    def test_a_tool_without_an_expected_cost_falls_back_to_the_advertised_maximum(
        self, metadata: Any
    ) -> None:
        """No published cost for the tool means the mech's own maximum is signed, with a warning."""
        with patch(f"{SERVICE}.logger.warning") as warning:
            rate = self._resolve(("tool-a",), metadata=metadata)
        assert rate == MECH_MAX_RATE
        warning.assert_called_once()
        assert "no usable expected cost for tool-a" in warning.call_args.args[0]
        assert str(MECH_MAX_RATE) in warning.call_args.args[0]

    @pytest.mark.parametrize("metadata", [None, "manifest", 7], ids=["none", "string", "int"])
    def test_an_unreadable_manifest_signs_the_advertised_maximum_with_one_warning(
        self, metadata: Any
    ) -> None:
        """A manifest that could not be read says so once; it is not a statement about the mech's costs."""
        with patch(f"{SERVICE}.logger.warning") as warning:
            rate = self._resolve(("tool-a", "tool-b"), metadata=metadata)
        assert rate == MECH_MAX_RATE
        warning.assert_called_once()
        message = warning.call_args.args[0]
        assert "manifest could not be read" in message
        assert "expected cost for" not in message
        assert str(MECH_MAX_RATE) in message

    def test_a_derived_cap_above_the_limit_is_refused(self) -> None:
        """One base unit over the limit needs the buyer's own cap; nothing is signed."""
        over = MAX_DERIVED_CAP_FACTOR * MECH_MAX_RATE + 2
        high = {"toolMetadata": {"tool-a": {"expectedCost": {"asset": "native", "amount": str(over // 2)}}}}
        with pytest.raises(ValueError, match=f"more than {MAX_DERIVED_CAP_FACTOR}x its advertised maximum"):
            self._resolve(("tool-a",), metadata=high)

    def test_a_derived_cap_at_the_limit_is_signed_quietly(self) -> None:
        """Exactly the limit is not above it."""
        at = {"toolMetadata": {"tool-a": {"expectedCost": {"asset": "native", "amount": str(5 * MECH_MAX_RATE)}}}}
        with patch(f"{SERVICE}.logger.warning") as warning:
            rate = self._resolve(("tool-a",), metadata=at)
        assert rate == MAX_DERIVED_CAP_FACTOR * MECH_MAX_RATE
        warning.assert_not_called()

    def test_a_chosen_cap_above_the_limit_is_signed(self) -> None:
        """The limit is on the manifest's number, not on what the buyer chooses."""
        high = {"toolMetadata": {"tool-a": {"expectedCost": {"asset": "native", "amount": str(6 * MECH_MAX_RATE)}}}}
        chosen = MAX_DERIVED_CAP_FACTOR * MECH_MAX_RATE * 3
        assert self._resolve(("tool-a",), metadata=high, max_cost=chosen) == chosen

    def test_the_derived_cap_never_exceeds_what_a_contract_can_carry(self) -> None:
        """Doubling the largest publishable amount stays at the uint256 ceiling."""
        top = {"toolMetadata": {"tool-a": {"expectedCost": {"asset": "native", "amount": str(UINT256_MAX)}}}}
        rate = self._resolve(("tool-a",), metadata=top, advertised_max=UINT256_MAX)
        assert rate == UINT256_MAX

    def test_an_expected_cost_in_another_asset_is_ignored(self) -> None:
        """A cost stated in an asset the mech is not paid in cannot size a cap in that asset."""
        with patch(f"{SERVICE}.logger.warning") as warning:
            rate = self._resolve(("tool-usdc",))
        assert rate == MECH_MAX_RATE
        messages = [call.args[0] for call in warning.call_args_list]
        assert any("stated in usdc, not the mech's payment asset native" in m for m in messages)

    def test_the_asset_check_follows_the_mechs_payment_type(self) -> None:
        """The same manifest entry is usable once the mech is paid in that asset."""
        rate = self._resolve(("tool-usdc",), payment_type=PaymentType.USDC_TOKEN)
        assert rate == DEFAULT_CAP_FACTOR * 25000

    def test_a_mixed_batch_covers_the_tool_without_a_cost_too(self) -> None:
        """A tool falling back to the advertised maximum raises the batch rate when that is larger."""
        assert MECH_MAX_RATE > DEFAULT_CAP_FACTOR * EXPECTED_COST
        rate = self._resolve(("tool-a", "unknown-tool"))
        assert rate == MECH_MAX_RATE

    def test_onchain_signs_the_advertised_maximum_whatever_the_manifest_says(self) -> None:
        """On-chain the marketplace records the mech's maximum as the charge; the manifest is not consulted."""
        rate = self._resolve(("tool-a",), use_offchain=False)
        assert rate == MECH_MAX_RATE

    def test_onchain_accepts_a_cap_at_or_above_the_advertised_charge(self) -> None:
        """A cap the charge fits under changes nothing about what is signed."""
        assert self._resolve(("tool-a",), use_offchain=False, max_cost=MECH_MAX_RATE) == MECH_MAX_RATE
        assert self._resolve(("tool-a",), use_offchain=False, max_cost=MECH_MAX_RATE + 1) == MECH_MAX_RATE

    def test_onchain_refuses_a_cap_below_the_advertised_charge(self) -> None:
        """The request would revert with a lower maximum, so it is stopped here with the price."""
        with pytest.raises(ValueError, match=f"charges {MECH_MAX_RATE} per on-chain request"):
            self._resolve(("tool-a",), use_offchain=False, max_cost=MECH_MAX_RATE - 1)


class TestSendRequestDeadlineSeconds:
    """``send_request`` refuses a deadline that cannot be signed, before any chain read."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "deadline_seconds",
        [0, -1, MAX_DEADLINE_SECONDS + 1, True, 1.5],
        ids=["zero", "negative", "past_uint256", "bool", "fraction"],
    )
    async def test_a_deadline_that_cannot_be_signed_is_refused_before_any_chain_read(
        self, deadline_seconds: Any
    ) -> None:
        """An expired, oversized or non-integer window raises before anything is fetched."""
        service = _build_offchain_service()

        with patch.object(service, "marketplace_contract") as contract:
            with pytest.raises(ValueError, match="deadline_seconds must be a whole number"):
                await service.send_request(
                    prompts=("p",), tools=("tool-a",), use_offchain=True, deadline_seconds=deadline_seconds
                )

        contract.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("deadline_seconds", [1, MAX_DEADLINE_SECONDS], ids=["one", "largest"])
    async def test_the_bounds_are_accepted(self, deadline_seconds: int) -> None:
        """The shortest and longest windows reach the off-chain sender unchanged."""
        service = _build_offchain_service()
        service.tool_manager = MagicMock()
        service.tool_manager.read_tools_metadata.return_value = MetadataRead(COSTED_MANIFEST, None)

        with (
            patch.object(service, "marketplace_contract", return_value=MagicMock()),
            patch.object(
                service,
                "mech_info",
                return_value=MechInfo(MECH_ADDRESS, 1, PaymentType.NATIVE, MECH_MAX_RATE),
            ),
            patch.object(service, "_validate_tools"),
            patch.object(service, "_send_offchain_request", new_callable=AsyncMock) as offchain,
        ):
            await service.send_request(
                prompts=("p",), tools=("tool-a",), use_offchain=True, deadline_seconds=deadline_seconds
            )

        assert offchain.call_args.kwargs["deadline_seconds"] == deadline_seconds


class TestSendRequestMaxCost:
    """``send_request`` validates ``max_cost`` first and signs the resolved rate."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("max_cost", [0, -1, UINT256_MAX + 1], ids=["zero", "negative", "above_uint256"])
    async def test_a_cap_a_contract_cannot_carry_is_refused_before_any_chain_read(
        self, max_cost: int
    ) -> None:
        """A cap of nothing, or one wider than a uint256, cannot be signed, so nothing is fetched."""
        service = _build_offchain_service()

        with patch.object(service, "marketplace_contract") as contract:
            with pytest.raises(ValueError, match="max_cost must be a positive amount"):
                await service.send_request(prompts=("p",), tools=("tool-a",), use_offchain=True, max_cost=max_cost)

        contract.assert_not_called()

    @pytest.mark.asyncio
    async def test_the_default_cap_from_the_manifest_reaches_the_offchain_sender(self) -> None:
        """The advertised maximum is no longer what an off-chain request signs when a cost is published."""
        service = _build_offchain_service()
        service.tool_manager = MagicMock()
        service.tool_manager.read_tools_metadata.return_value = MetadataRead(
            COSTED_MANIFEST, None
        )

        with (
            patch.object(service, "marketplace_contract", return_value=MagicMock()),
            patch.object(
                service,
                "mech_info",
                return_value=MechInfo(MECH_ADDRESS, 1, PaymentType.NATIVE, MECH_MAX_RATE),
            ),
            patch.object(service, "_validate_tools"),
            patch.object(service, "_send_offchain_request", new_callable=AsyncMock) as offchain,
        ):
            await service.send_request(prompts=("p",), tools=("tool-a",), use_offchain=True)

        assert offchain.call_args.kwargs["max_delivery_rate"] == DEFAULT_CAP_FACTOR * EXPECTED_COST
        assert offchain.call_args.kwargs["fallback_rate"] == MECH_MAX_RATE

    @pytest.mark.asyncio
    async def test_a_chosen_cap_reaches_the_offchain_sender(self) -> None:
        """``max_cost`` is the signed rate, approvals and deposits included."""
        service = _build_offchain_service()
        service.tool_manager = MagicMock()
        service.tool_manager.read_tools_metadata.return_value = MetadataRead(
            COSTED_MANIFEST, None
        )

        with (
            patch.object(service, "marketplace_contract", return_value=MagicMock()),
            patch.object(
                service,
                "mech_info",
                return_value=MechInfo(MECH_ADDRESS, 1, PaymentType.NATIVE, MECH_MAX_RATE),
            ),
            patch.object(service, "_validate_tools"),
            patch.object(service, "_send_offchain_request", new_callable=AsyncMock) as offchain,
        ):
            await service.send_request(prompts=("p",), tools=("tool-a",), use_offchain=True, max_cost=OWN_CAP)

        assert offchain.call_args.kwargs["max_delivery_rate"] == OWN_CAP
        assert offchain.call_args.kwargs["fallback_rate"] is None

    @pytest.mark.asyncio
    async def test_an_onchain_request_above_the_cap_is_refused_before_upload_or_send(self) -> None:
        """Nothing is uploaded or sent for a request the marketplace would refuse anyway."""
        service = _build_offchain_service()
        service.tool_manager = MagicMock()
        service.tool_manager.read_tools_metadata.return_value = MetadataRead(
            COSTED_MANIFEST, None
        )

        with (
            patch.object(service, "marketplace_contract", return_value=MagicMock()),
            patch.object(
                service,
                "mech_info",
                return_value=MechInfo(MECH_ADDRESS, 1, PaymentType.NATIVE, MECH_MAX_RATE),
            ),
            patch.object(service, "_validate_tools"),
            patch(f"{SERVICE}.push_metadata_to_ipfs") as push,
            patch.object(service, "_send_marketplace_request") as send,
        ):
            with pytest.raises(ValueError, match="per on-chain request"):
                await service.send_request(prompts=("p",), tools=("tool-a",), max_cost=OWN_CAP)

        push.assert_not_called()
        send.assert_not_called()


VALID_PROMPTS = ("Will it rain tomorrow?",)
VALID_TOOLS = ("prediction-online",)


class TestValidateRequestShape:
    """A request every mech would fail is refused locally, before it is sent."""

    @pytest.mark.parametrize(
        ("prompts", "tools", "extras", "error"),
        [
            (VALID_PROMPTS, VALID_TOOLS, None, None),
            (VALID_PROMPTS, VALID_TOOLS, {}, None),
            (VALID_PROMPTS, VALID_TOOLS, {"model": "gpt-4.1"}, None),
            (("a", "b"), ("t1", "t2"), None, None),
            (("",), VALID_TOOLS, None, None),
            (("ok", "  \n"), ("t1", "t2"), None, None),
            (("",), ("propose-question",), {"num_questions": 3}, None),
            ((None,), VALID_TOOLS, None, "Prompt 1 is not a string"),
            (("ok", 7), ("t1", "t2"), None, "Prompt 2 is not a string"),
            (VALID_PROMPTS, ("",), None, "Tool 1 is empty"),
            (VALID_PROMPTS, (" ",), None, "Tool 1 is empty"),
            (VALID_PROMPTS, VALID_TOOLS, {"tool": "other"}, "may not set tool"),
            (VALID_PROMPTS, VALID_TOOLS, {"nonce": "pinned-salt"}, None),
            (
                VALID_PROMPTS,
                VALID_TOOLS,
                {"tool": "x", "prompt": "p", "model": "m"},
                "may not set prompt, tool",
            ),
        ],
    )
    @patch("mech_client.services.marketplace_service.requests")
    def test_validate_request_shape(
        self,
        mock_requests: MagicMock,
        prompts: Tuple[Any, ...],
        tools: Tuple[Any, ...],
        extras: Optional[Dict[str, Any]],
        error: Optional[str],
    ) -> None:
        """Each check passes a well-formed request and names what a bad one lacks, offline."""
        if error is None:
            validate_request_shape(prompts, tools, extras)
        else:
            with pytest.raises(ValueError, match=error):
                validate_request_shape(prompts, tools, extras)
        assert mock_requests.mock_calls == []

    @pytest.mark.parametrize("use_offchain", [True, False])
    @patch("mech_client.services.marketplace_service.push_metadata_to_ipfs")
    @patch("mech_client.services.marketplace_service.requests")
    def test_send_request_refuses_before_any_read_or_send(
        self,
        mock_requests: MagicMock,
        mock_push: MagicMock,
        use_offchain: bool,
    ) -> None:
        """An empty tool stops send_request before the chain, the manifest or the mech is touched."""
        service = MagicMock(spec=MarketplaceService)
        service.send_request = MarketplaceService.send_request.__get__(
            service, MarketplaceService
        )

        with pytest.raises(ValueError, match="Tool 1 is empty"):
            asyncio.run(
                service.send_request(
                    prompts=VALID_PROMPTS, tools=("",), use_offchain=use_offchain
                )
            )

        service.marketplace_contract.assert_not_called()
        service.mech_info.assert_not_called()
        service._send_offchain_request.assert_not_called()
        mock_push.assert_not_called()
        assert mock_requests.mock_calls == []

    def test_send_request_sends_an_empty_prompt(self) -> None:
        """A tool reading its inputs from extra attributes is sent an empty prompt."""
        service = MagicMock(spec=MarketplaceService)
        service.send_request = MarketplaceService.send_request.__get__(
            service, MarketplaceService
        )
        service.tool_manager = MagicMock()
        service.mech_info.return_value = MechInfo("0xmech", 1, MagicMock(), 100)
        extras = {"num_questions": 3}

        asyncio.run(
            service.send_request(
                prompts=("",),
                tools=("propose-question",),
                priority_mech="0xmech",
                use_offchain=True,
                extra_attributes=extras,
            )
        )

        sent = service._send_offchain_request.await_args.kwargs
        assert sent["prompts"] == ("",)
        assert sent["extra_attributes"] == extras


SIGNED_CAP = 1000
MINIMUM_CAP = 2500


class TestOffchainCapRefusals:
    """A cap below the mech's minimum is refused without a deposit; a 402 shortfall is required minus balance."""

    @pytest.mark.parametrize(
        ("status", "body", "match"),
        [
            (
                400,
                {"reason": MINIMUM_CAP_REASON, "minimum_cap": MINIMUM_CAP},
                rf"cap {SIGNED_CAP} is below .*minimum cap: {MINIMUM_CAP}",
            ),
            (
                400,
                {"reason": MINIMUM_CAP_REASON},
                rf"cap {SIGNED_CAP} is below .*minimum cap: not reported",
            ),
            (
                400,
                {"reason": MINIMUM_CAP_REASON, "minimum_cap": "lots"},
                "minimum cap: not reported",
            ),
        ],
    )
    def test_minimum_cap_refusal_is_explained(
        self, status: int, body: Dict[str, Any], match: str
    ) -> None:
        """The refusal names the minimum and never triggers a deposit or a retry."""
        response = _mock_http_response(status, body)
        message = MarketplaceService._below_minimum_cap(response, SIGNED_CAP)
        assert message is not None
        assert re.search(match, message)

    @pytest.mark.parametrize(
        "response",
        [
            _mock_http_response(200, {}),
            _mock_http_response(400, {"reason": "invalid signature"}),
            _mock_http_response(400, ["not", "a", "dict"]),  # type: ignore[arg-type]
            _mock_http_response(402, {"reason": MINIMUM_CAP_REASON}),
        ],
    )
    def test_other_responses_are_not_a_minimum_cap_refusal(
        self, response: MagicMock
    ) -> None:
        """Only a 400 with the exact reason counts."""
        assert MarketplaceService._below_minimum_cap(response, SIGNED_CAP) is None

    def test_a_non_json_400_is_not_a_minimum_cap_refusal(self) -> None:
        """An unreadable body is left to the generic rejection path."""
        response = _mock_http_response(400)
        response.json.side_effect = ValueError("not json")
        assert MarketplaceService._below_minimum_cap(response, SIGNED_CAP) is None

    @pytest.mark.asyncio
    async def test_a_minimum_cap_refusal_is_a_structured_rejection(self) -> None:
        """The send raises the mech's rejection, carrying the explained message."""
        service = _build_offchain_service()
        service.signer = _real_signing_signer()
        refusal = _mock_http_response(
            400, {"reason": MINIMUM_CAP_REASON, "minimum_cap": MINIMUM_CAP}
        )

        with pytest.raises(OffchainRequestRejected) as e:
            await _send_offchain_in_mode(
                service, _nonce_mode_contract(), [refusal], NONCE_MODE_SEQUENTIAL
            )

        assert f"minimum cap: {MINIMUM_CAP}" in str(e.value)
        assert (e.value.status, e.value.reason) == (400, MINIMUM_CAP_REASON)
        assert e.value.nonce == MARKETPLACE_NONCE

    def test_minimum_cap_400_with_auto_deposit_does_not_deposit(self) -> None:
        """_post_offchain_request passes the 400 back untouched: one POST, no deposit."""
        service = _build_offchain_service()
        refusal = _mock_http_response(
            400, {"reason": MINIMUM_CAP_REASON, "minimum_cap": MINIMUM_CAP}
        )
        with (
            patch(
                "mech_client.services.marketplace_service.requests.post",
                return_value=refusal,
            ) as mock_post,
            patch("mech_client.services.deposit_service.DepositService") as mock_ds,
        ):
            response = service._post_offchain_request(
                "http://mech/send_signed_requests",
                {},
                PaymentType.NATIVE,
                True,
                max_delivery_rate=SIGNED_CAP,
            )
        assert response is refusal
        assert mock_post.call_count == 1
        mock_ds.assert_not_called()

    def test_auto_deposit_tops_up_required_minus_reported_balance(self) -> None:
        """The deposit is the cap less the balance the mech reports after in-flight reservations."""
        service = _build_offchain_service()
        responses = [
            _mock_http_response(
                402,
                {"required": str(SIGNED_CAP), "currentBalance": "400", "payTo": "0xbt"},
            ),
            _mock_http_response(200, {}),
        ]
        with (
            patch(
                "mech_client.services.marketplace_service.requests.post",
                side_effect=responses,
            ),
            patch("mech_client.services.deposit_service.DepositService") as mock_ds,
            patch(f"{SERVICE}.wait_for_receipt", return_value={"status": 1}),
        ):
            service._post_offchain_request(
                "http://mech/send_signed_requests",
                {},
                PaymentType.NATIVE,
                True,
                max_delivery_rate=SIGNED_CAP,
            )
        mock_ds.return_value.deposit_native.assert_called_once_with(SIGNED_CAP - 400)

    def test_auto_deposit_above_the_safety_cap_is_refused(self) -> None:
        """The deposit helper still refuses a shortfall above its safety multiple."""
        service = _build_offchain_service()
        challenge = PaymentChallenge(
            required=SIGNED_CAP * 20,
            current_balance=0,
            pay_to="0xbt",
            asset="",
            chain_id=100,
            error="",
        )
        with patch("mech_client.services.deposit_service.DepositService") as mock_ds:
            with pytest.raises(ValueError, match=r"refused.*safety cap"):
                service._auto_deposit_for_402(PaymentType.NATIVE, challenge, SIGNED_CAP)
        mock_ds.assert_not_called()
def _request_id_for(nonce: int, requester: str = _TEST_ACCOUNT.address) -> bytes:
    """Return the request id of prompt "a" to MECH_ADDRESS at rate 100."""
    return _derived_id(nonce, requester=requester)


def _nonce_contract(map_nonces: int) -> MagicMock:
    """Build an honest marketplace mock at the given mapNonces."""
    contract = _honest(MagicMock())
    contract.functions.mapNonces.return_value.call.return_value = map_nonces
    return contract


async def _send_offchain(
    service: MarketplaceService,
    contract: MagicMock,
    prompts: tuple = ("a",),
    **kwargs: Any,
) -> Any:
    """Run _send_offchain_request for ``prompts``, sequential unless told otherwise."""
    return await service._send_offchain_request(  # pylint: disable=protected-access
        marketplace_contract=contract,
        prompts=prompts,
        tools=("t",) * len(prompts),
        priority_mech_address="0x" + "9" * 40,
        max_delivery_rate=100,
        payment_type=PaymentType.NATIVE,
        response_timeout=300,
        mech_offchain_url="https://mech.example.com",
        extra_attributes=None,
        timeout=30.0,
        **{"nonce_mode": NONCE_MODE_SEQUENTIAL, **kwargs},
    )


class TestCallerOwnedNonces:
    """Caller-chosen nonces, the pre-sign hook and structured rejections."""

    @pytest.fixture
    def service(self) -> MarketplaceService:
        """Client-mode service with a real signer."""
        service = _build_offchain_service()
        service.signer = _real_signing_signer()
        return service

    @pytest.fixture
    def mech_post(self) -> Any:
        """Patch the mech's POST endpoint; tests set its responses."""
        watcher = AsyncMock()
        watcher.watch.return_value = {}
        with (
            patch(
                "mech_client.infrastructure.ipfs.metadata.fetch_ipfs_hash",
                return_value=("0x" + "b" * 64, "full-hash", '{"prompt":"a"}'),
            ),
            patch(f"{SERVICE}.requests.post") as post,
            patch(f"{SERVICE}.OffchainDeliveryWatcher", return_value=watcher),
        ):
            yield post

    @pytest.mark.asyncio
    async def test_given_nonces_are_signed_posted_and_reported(
        self, service: MarketplaceService, mech_post: MagicMock
    ) -> None:
        """Each prompt uses its own nonce, and the hook sees the id before signing."""
        mech_post.side_effect = [_mock_http_response(200), _mock_http_response(200)]
        seen = []

        def hook(request_id: bytes, nonce: int) -> None:
            seen.append((request_id, nonce, service.signer.sign_message.call_count))

        result = await _send_offchain(
            service,
            _nonce_contract(5),
            prompts=("a", "b"),
            nonces=[7, 9],
            on_request_id=hook,
        )

        assert result["nonces"] == [7, 9]
        assert result["request_ids"] == [
            _request_id_for(7).hex(),
            _request_id_for(9).hex(),
        ]
        assert seen == [(_request_id_for(7), 7, 0), (_request_id_for(9), 9, 1)]
        assert [c.kwargs["data"]["nonce"] for c in mech_post.call_args_list] == [7, 9]

    @pytest.mark.asyncio
    async def test_without_nonces_counts_up_from_map_nonces(
        self, service: MarketplaceService, mech_post: MagicMock
    ) -> None:
        """No nonces keeps the mapNonces + i behaviour."""
        mech_post.side_effect = [_mock_http_response(200), _mock_http_response(200)]
        hook = MagicMock()

        result = await _send_offchain(
            service, _nonce_contract(5), prompts=("a", "b"), on_request_id=hook
        )

        assert hook.call_args_list == [
            call(_request_id_for(5), 5),
            call(_request_id_for(6), 6),
        ]
        assert result["nonces"] == [5, 6]
        assert result["request_ids"] == [
            _request_id_for(5).hex(),
            _request_id_for(6).hex(),
        ]
        assert [c.kwargs["data"]["nonce"] for c in mech_post.call_args_list] == [5, 6]

    @pytest.mark.asyncio
    async def test_agent_mode_hook_gets_the_raw_id_before_the_safe_signs(
        self, mech_post: MagicMock
    ) -> None:
        """In agent mode the hook sees the unwrapped id, and mapNonces keys on the Safe."""
        safe = "0x" + "5a" * 20
        service = _build_offchain_service(agent_mode=True, safe_address=safe)
        service.signer = create_mock_signer(
            address="0x" + "e0" * 20, safe_signature=b"\xdd" * 64 + b"\x1b"
        )
        contract = _nonce_contract(5)
        mech_post.side_effect = [_mock_http_response(200)]
        seen = []

        def hook(request_id: bytes, nonce: int) -> None:
            seen.append(
                (request_id, nonce, service.signer.sign_safe_message.call_count)
            )

        await _send_offchain(service, contract, nonces=[7], on_request_id=hook)

        assert seen == [(_request_id_for(7, requester=safe), 7, 0)]
        contract.functions.mapNonces.assert_called_once_with(
            ensure_checksummed_address(safe)
        )

    @pytest.mark.asyncio
    async def test_stale_nonce_is_refused_before_signing(
        self, service: MarketplaceService, mech_post: MagicMock
    ) -> None:
        """A nonce below mapNonces raises before anything is signed or sent."""
        with pytest.raises(ValueError, match=r"\[4\] are below .* nonce 5"):
            await _send_offchain(service, _nonce_contract(5), nonces=[4])

        service.signer.sign_message.assert_not_called()
        mech_post.assert_not_called()

    @pytest.mark.asyncio
    async def test_hook_failure_stops_the_request(
        self, service: MarketplaceService, mech_post: MagicMock
    ) -> None:
        """A raising hook leaves the request unsigned and unsent."""

        def hook(request_id: bytes, nonce: int) -> None:
            raise RuntimeError("not allowed")

        with pytest.raises(RuntimeError, match="not allowed"):
            await _send_offchain(
                service, _nonce_contract(5), nonces=[5], on_request_id=hook
            )

        service.signer.sign_message.assert_not_called()
        mech_post.assert_not_called()

    @pytest.mark.asyncio
    async def test_rejection_reports_nonce_status_reason_and_unsent(
        self, service: MarketplaceService, mech_post: MagicMock
    ) -> None:
        """A 503 mid-call names the request, keeps the mech's reason and lists the rest."""
        mech_post.side_effect = [
            _mock_http_response(200),
            _mock_http_response(
                503, {"reason": "wire nonce above sender's next expected slot"}
            ),
        ]

        with pytest.raises(OffchainRequestRejected) as exc_info:
            await _send_offchain(
                service, _nonce_contract(5), prompts=("a", "b", "c"), nonces=[5, 6, 7]
            )

        err = exc_info.value
        assert isinstance(err, ValueError)
        assert err.request_id == _request_id_for(6).hex()
        assert err.nonce == 6
        assert err.status == 503
        assert err.reason == "wire nonce above sender's next expected slot"
        assert err.retryable
        assert err.unsent == [7]
        assert f"{_request_id_for(5).hex()} (nonce 5)" in str(err)

    @pytest.mark.asyncio
    async def test_rejection_without_json_reason_uses_http_reason(
        self, service: MarketplaceService, mech_post: MagicMock
    ) -> None:
        """A 4xx without a JSON body is final and falls back to the HTTP reason."""
        resp = _mock_http_response(401)
        resp.reason = "Unauthorized"
        resp.json.side_effect = ValueError("no json")
        mech_post.side_effect = [resp]

        with pytest.raises(OffchainRequestRejected) as exc_info:
            await _send_offchain(service, _nonce_contract(5), nonces=[5])

        err = exc_info.value
        assert err.reason == "Unauthorized"
        assert not err.retryable
        assert err.unsent == []
        assert str(err) == "Offchain request rejected: Unauthorized (HTTP 401)"

    @pytest.mark.asyncio
    async def test_non_string_reason_is_stringified(
        self, service: MarketplaceService, mech_post: MagicMock
    ) -> None:
        """A mech that sends a non-string reason still yields a str."""
        mech_post.side_effect = [_mock_http_response(400, {"reason": 42})]

        with pytest.raises(OffchainRequestRejected) as exc_info:
            await _send_offchain(service, _nonce_contract(5))

        assert exc_info.value.reason == "42"

    @pytest.mark.asyncio
    async def test_402_mid_call_reports_unsent_and_accepted(
        self, service: MarketplaceService, mech_post: MagicMock
    ) -> None:
        """A 402 after an accepted request carries the same call context as other errors."""
        mech_post.side_effect = [
            _mock_http_response(200),
            _mock_http_response(402, {"required": "100", "currentBalance": "0"}),
        ]

        with pytest.raises(OffchainRequestRejected, match="requires payment") as e:
            await _send_offchain(
                service, _nonce_contract(5), prompts=("a", "b", "c"), nonces=[5, 6, 7]
            )

        assert e.value.status == 402
        assert e.value.nonce == 6
        assert e.value.unsent == [7]
        assert f"{_request_id_for(5).hex()} (nonce 5)" in str(e.value)

    @pytest.mark.asyncio
    async def test_402_without_shortfall_is_a_rejection(
        self, service: MarketplaceService, mech_post: MagicMock
    ) -> None:
        """A 402 reporting no shortfall is a 402 rejection."""
        mech_post.side_effect = [
            _mock_http_response(402, {"required": "100", "currentBalance": "100"})
        ]

        with pytest.raises(OffchainRequestRejected, match="no shortfall") as e:
            await _send_offchain(service, _nonce_contract(5), auto_deposit=True)

        assert e.value.status == 402

    @pytest.mark.asyncio
    async def test_a_top_up_failure_never_carries_a_keyed_url(
        self, service: MarketplaceService, mech_post: MagicMock
    ) -> None:
        """A deposit failing on a keyed RPC is reported redacted, in full otherwise."""
        mech_post.side_effect = [
            _mock_http_response(402, {"required": "100", "currentBalance": "0"})
        ]
        failure = ValueError("deposit failed on https://rpc.example/v3/SECRETKEY")

        with patch.object(service, "_auto_deposit_for_402", side_effect=failure):
            with pytest.raises(OffchainTopUpFailed) as e:
                await _send_offchain(service, _nonce_contract(5), auto_deposit=True)

        assert str(e.value) == "deposit failed on https://rpc.example/..."
        assert e.value.__cause__.__cause__ is failure  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_refused_top_up_is_its_own_error(
        self, service: MarketplaceService, mech_post: MagicMock
    ) -> None:
        """A top-up refused on our side is neither the mech's 402 nor a transport error."""
        mech_post.side_effect = [
            _mock_http_response(200),
            _mock_http_response(402, {"required": "100", "currentBalance": "-99900"}),
        ]

        with pytest.raises(OffchainTopUpFailed, match="safety cap") as e:
            await _send_offchain(
                service,
                _nonce_contract(5),
                prompts=("a", "b", "c"),
                nonces=[5, 6, 7],
                auto_deposit=True,
            )

        assert not isinstance(e.value, OffchainRequestRejected)
        assert (e.value.request_id, e.value.nonce) == (_request_id_for(6).hex(), 6)
        assert e.value.unsent == [7]
        assert f"{_request_id_for(5).hex()} (nonce 5)" in str(e.value)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(("shortfall", "deposited"), [(501, False), (500, True)])
    async def test_an_auto_deposit_never_exceeds_max_price(
        self,
        service: MarketplaceService,
        mech_post: MagicMock,
        shortfall: int,
        deposited: bool,
    ) -> None:
        """With a rate (100) below max_price, a top-up above max_price is never sent."""
        mech_post.side_effect = [
            _mock_http_response(
                402, {"required": "100", "currentBalance": str(100 - shortfall)}
            ),
            _mock_http_response(200),
        ]

        with (
            patch("mech_client.services.deposit_service.DepositService") as deposits,
            patch(f"{SERVICE}.wait_for_receipt", return_value={"status": 1}),
        ):
            if deposited:
                await _send_offchain(
                    service, _nonce_contract(5), auto_deposit=True, max_price=500
                )
            else:
                with pytest.raises(OffchainTopUpFailed, match="max_price of 500"):
                    await _send_offchain(
                        service, _nonce_contract(5), auto_deposit=True, max_price=500
                    )

        if deposited:
            deposits.return_value.deposit_native.assert_called_once_with(500)
        else:
            deposits.assert_not_called()
            assert mech_post.call_count == 1

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("second", "deposits"), [(201, [300]), (200, [300, 200])]
    )
    async def test_the_deposits_of_one_call_together_never_exceed_max_price(
        self,
        service: MarketplaceService,
        mech_post: MagicMock,
        second: int,
        deposits: list,
    ) -> None:
        """Each request's 402 draws on one max_price shared by the whole call."""
        mech_post.side_effect = [
            _mock_http_response(402, {"required": "100", "currentBalance": "-200"}),
            _mock_http_response(200),
            _mock_http_response(
                402, {"required": "100", "currentBalance": str(100 - second)}
            ),
            _mock_http_response(200),
        ]

        with (
            patch("mech_client.services.deposit_service.DepositService") as service_cls,
            patch(f"{SERVICE}.wait_for_receipt", return_value={"status": 1}),
        ):
            if len(deposits) == 2:
                await _send_offchain(
                    service,
                    _nonce_contract(5),
                    prompts=("a", "b"),
                    auto_deposit=True,
                    max_price=500,
                )
            else:
                with pytest.raises(
                    OffchainTopUpFailed, match="300 already deposited for these requests"
                ):
                    await _send_offchain(
                        service,
                        _nonce_contract(5),
                        prompts=("a", "b"),
                        auto_deposit=True,
                        max_price=500,
                    )

        sent = [c.args[0] for c in service_cls.return_value.deposit_native.call_args_list]
        assert sent == deposits

    @pytest.mark.asyncio
    @pytest.mark.parametrize(("shortfall", "deposited"), [(1001, False), (1000, True)])
    async def test_an_auto_deposit_without_max_price_is_bounded_by_the_ratio(
        self,
        service: MarketplaceService,
        mech_post: MagicMock,
        shortfall: int,
        deposited: bool,
    ) -> None:
        """max_price=None leaves the bound at _MAX_AUTO_DEPOSIT_RATIO x the rate."""
        mech_post.side_effect = [
            _mock_http_response(
                402, {"required": "100", "currentBalance": str(100 - shortfall)}
            ),
            _mock_http_response(200),
        ]

        with (
            patch("mech_client.services.deposit_service.DepositService") as deposits,
            patch(f"{SERVICE}.wait_for_receipt", return_value={"status": 1}),
        ):
            if deposited:
                await _send_offchain(
                    service, _nonce_contract(5), auto_deposit=True, max_price=None
                )
            else:
                with pytest.raises(OffchainTopUpFailed, match="safety cap of 1000"):
                    await _send_offchain(
                        service, _nonce_contract(5), auto_deposit=True, max_price=None
                    )

        if deposited:
            deposits.return_value.deposit_native.assert_called_once_with(1000)
        else:
            deposits.assert_not_called()

    @pytest.mark.asyncio
    async def test_reverted_top_up_is_a_top_up_failure(
        self, service: MarketplaceService, mech_post: MagicMock
    ) -> None:
        """A mined but reverted deposit is not reported as deposited."""
        mech_post.side_effect = [
            _mock_http_response(402, {"required": "100", "currentBalance": "0"})
        ]

        with (
            patch("mech_client.services.deposit_service.DepositService"),
            patch(f"{SERVICE}.wait_for_receipt", return_value={"status": 0}),
        ):
            with pytest.raises(OffchainTopUpFailed, match="reverted"):
                await _send_offchain(service, _nonce_contract(5), auto_deposit=True)

        assert mech_post.call_count == 1

    @pytest.mark.asyncio
    async def test_second_402_after_deposit_is_a_rejection(
        self, service: MarketplaceService, mech_post: MagicMock
    ) -> None:
        """A 402 that survives the top-up is a 402 rejection naming the shortfall."""
        mech_post.side_effect = [
            _mock_http_response(402, {"required": "100", "currentBalance": "0"}),
            _mock_http_response(402, {"required": "150", "currentBalance": "100"}),
        ]

        with (
            patch("mech_client.services.deposit_service.DepositService"),
            patch(f"{SERVICE}.wait_for_receipt", return_value={"status": 1}),
        ):
            with pytest.raises(OffchainRequestRejected, match="did not clear") as e:
                await _send_offchain(service, _nonce_contract(5), auto_deposit=True)

        assert e.value.status == 402
        assert e.value.nonce == 5
        assert e.value.deposited == 100
        assert "remaining shortfall 50" in str(e.value)

    @pytest.mark.asyncio
    async def test_json_body_without_reason_uses_http_reason(
        self, service: MarketplaceService, mech_post: MagicMock
    ) -> None:
        """A JSON error body with no usable reason falls back to the HTTP reason."""
        resp = _mock_http_response(400, {"error": "x", "reason": None})
        resp.reason = "Bad Request"
        mech_post.side_effect = [resp]

        with pytest.raises(OffchainRequestRejected) as exc_info:
            await _send_offchain(service, _nonce_contract(5))

        assert exc_info.value.reason == "Bad Request"
        assert "Bad Request (HTTP 400)" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_transport_error_mid_call_names_the_accepted_requests(
        self, service: MarketplaceService, mech_post: MagicMock
    ) -> None:
        """A transport failure after an accepted request still names that request."""
        mech_post.side_effect = [
            _mock_http_response(200),
            requests.exceptions.ConnectionError("reset"),
        ]

        with pytest.raises(ValueError, match="Failed to send") as e:
            await _send_offchain(
                service, _nonce_contract(5), prompts=("a", "b"), nonces=[5, 6]
            )

        assert not isinstance(e.value, OffchainRequestRejected)
        assert f"{_request_id_for(5).hex()} (nonce 5)" in str(e.value)

    @pytest.mark.asyncio
    async def test_transport_error_stays_a_plain_value_error(
        self, service: MarketplaceService, mech_post: MagicMock
    ) -> None:
        """No HTTP answer means the outcome is unknown, so it is not a rejection."""
        mech_post.side_effect = requests.exceptions.ConnectionError(
            "HTTPSConnectionPool(host='mech.example', port=443): Max retries "
            "exceeded with url: /send_signed_requests?key=SECRETKEY"
        )

        with patch(
            "mech_client.services.marketplace_service.logger.warning"
        ) as mock_warn, pytest.raises(ValueError, match="Failed to send") as e:
            await _send_offchain(service, _nonce_contract(5))

        assert not isinstance(e.value, OffchainRequestRejected)
        assert "(ConnectionError)" in str(e.value)
        assert "SECRETKEY" not in str(e.value)
        assert isinstance(e.value.__cause__, requests.exceptions.ConnectionError)
        (warning,) = mock_warn.call_args[0]
        assert f"nonce 5 (request {_request_id_for(5).hex()})" in warning
        assert "ConnectionError" in warning
        assert "SECRETKEY" not in warning

    @pytest.mark.asyncio
    async def test_send_request_refuses_a_nonce_count_mismatch_early(
        self, service: MarketplaceService
    ) -> None:
        """A nonce count that differs from the prompts fails before any chain read."""
        with patch.object(service, "marketplace_contract") as mock_contract:
            with pytest.raises(ValueError, match="nonces \\(1\\) must match"):
                await service.send_request(
                    prompts=("a", "b"), tools=("t", "t"), use_offchain=True, nonces=[1]
                )

        mock_contract.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_request_forwards_nonces_and_hook(
        self, service: MarketplaceService
    ) -> None:
        """send_request passes nonces and the hook to the offchain path."""
        hook = MagicMock()
        service.tool_manager = MagicMock()
        service.tool_manager.terms_report.return_value = {"valory_operated": False}

        with (
            patch.object(service, "marketplace_contract"),
            patch.object(
                service,
                "mech_info",
                return_value=MechInfo(MECH_ADDRESS, 1, PaymentType.NATIVE, 1),
            ),
            patch.object(service, "_validate_tools"),
            patch.object(
                service, "_send_offchain_request", new_callable=AsyncMock
            ) as mock_offchain,
        ):
            await service.send_request(
                prompts=("a",),
                tools=("t",),
                priority_mech="0x" + "9" * 40,
                use_offchain=True,
                nonces=[3],
                on_request_id=hook,
            )

        assert mock_offchain.call_args.kwargs["nonces"] == [3]
        assert mock_offchain.call_args.kwargs["on_request_id"] is hook

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "kwargs", [{"nonces": [1]}, {"on_request_id": lambda request_id, nonce: None}]
    )
    async def test_onchain_path_refuses_nonces_and_hook(
        self, service: MarketplaceService, kwargs: Dict[str, Any]
    ) -> None:
        """Offchain-only arguments fail fast on-chain instead of being ignored."""
        with patch.object(service, "marketplace_contract") as mock_contract:
            with pytest.raises(ValueError, match="only to offchain"):
                await service.send_request(prompts=("a",), tools=("t",), **kwargs)

        mock_contract.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("nonces", "match"),
        [
            ([5, 5], "strictly increasing"),
            ([7, 5], "strictly increasing"),
            ([5, "6"], "integers"),
            ([True, 2], "integers"),
        ],
    )
    async def test_send_request_refuses_bad_nonce_lists(
        self, service: MarketplaceService, nonces: List[Any], match: str
    ) -> None:
        """Repeated, decreasing or non-integer nonces fail before any chain read."""
        with patch.object(service, "marketplace_contract") as mock_contract:
            with pytest.raises(ValueError, match=match):
                await service.send_request(
                    prompts=("a", "b"),
                    tools=("t", "t"),
                    use_offchain=True,
                    nonces=nonces,
                )

        mock_contract.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_hook_is_refused_before_signing(
        self, service: MarketplaceService, mech_post: MagicMock
    ) -> None:
        """An async hook would never run, so it is refused before anything is signed."""

        async def hook(request_id: bytes, nonce: int) -> None:
            raise AssertionError("never awaited")

        with pytest.raises(TypeError, match="synchronous"):
            await _send_offchain(service, _nonce_contract(5), on_request_id=hook)

        service.signer.sign_message.assert_not_called()
        mech_post.assert_not_called()

    @pytest.mark.asyncio
    async def test_hook_failure_mid_call_stops_the_rest(
        self, service: MarketplaceService, mech_post: MagicMock
    ) -> None:
        """A hook raising on the second request leaves only the first signed and sent."""
        mech_post.side_effect = [_mock_http_response(200)]

        def hook(request_id: bytes, nonce: int) -> None:
            if nonce == 6:
                raise RuntimeError("not allowed")

        with pytest.raises(RuntimeError, match="not allowed"):
            await _send_offchain(
                service,
                _nonce_contract(5),
                prompts=("a", "b"),
                nonces=[5, 6],
                on_request_id=hook,
            )

        assert service.signer.sign_message.call_count == 1
        assert mech_post.call_count == 1

    @pytest.mark.parametrize(
        ("status", "retryable"),
        [(400, False), (402, False), (429, False), (500, False), (503, True)],
    )
    def test_only_503_is_retryable(self, status: int, retryable: bool) -> None:
        """retryable follows HTTP 503 alone."""
        err = OffchainRequestRejected(
            "x", request_id="ab", nonce=1, status=status, reason="r", unsent=[]
        )

        assert err.retryable is retryable

    def test_rejection_survives_pickle_and_copy(self) -> None:
        """Every field comes back after a round trip."""
        err = OffchainRequestRejected(
            "rejected",
            request_id="ab",
            nonce=6,
            status=503,
            reason="busy",
            unsent=[7],
            deposited=9,
        )

        for clone in (pickle.loads(pickle.dumps(err)), copy.copy(err)):
            assert str(clone) == "rejected"
            assert (clone.request_id, clone.nonce, clone.status) == ("ab", 6, 503)
            assert (clone.reason, clone.unsent, clone.retryable) == ("busy", [7], True)
            assert clone.deposited == 9

    def test_top_up_failure_survives_pickle_and_copy(self) -> None:
        """Every field comes back after a round trip."""
        err = OffchainTopUpFailed("failed", request_id="ab", nonce=6, unsent=[7])

        for clone in (pickle.loads(pickle.dumps(err)), copy.copy(err)):
            assert str(clone) == "failed"
            assert (clone.request_id, clone.nonce, clone.unsent) == ("ab", 6, [7])

    def _through_allocator(
        self,
        service: MarketplaceService,
        tmp_path: Path,
        contract: MagicMock,
        request: Optional[Dict[str, Any]] = None,
        gap_retries: int = 0,
        **kwargs: Any,
    ) -> Tuple[NonceAllocator, Any]:
        """Send one request through send_with_nonce and the real send_request.

        ``request`` adds keyword arguments to ``send_request``.
        """
        allocator = NonceAllocator(
            tmp_path, settle_timeout=60, gap_retries=gap_retries, sleep=lambda _: None
        )

        service.tool_manager = MagicMock()
        service.tool_manager.terms_report.return_value = {"valory_operated": False}
        service.tool_manager.read_tools_metadata.return_value = MetadataRead(
            {"url": "https://mech.example.com"}, None
        )
        service.tool_manager.offchain_url_from_metadata = (
            ToolManager.offchain_url_from_metadata
        )

        def send(nonce: int, hook: PreSignHook) -> Any:
            with (
                patch.object(service, "marketplace_contract", return_value=contract),
                patch.object(
                    service,
                    "mech_info",
                    return_value=MechInfo(MECH_ADDRESS, 1, PaymentType.NATIVE, 100),
                ),
                patch.object(service, "_validate_tools"),
            ):
                return asyncio.run(
                    service.send_request(
                        prompts=("a",),
                        tools=("t",),
                        priority_mech=MECH_ADDRESS,
                        use_offchain=True,
                        nonces=[nonce],
                        on_request_id=hook,
                        **(request or {}),
                    )
                )

        try:
            result = send_with_nonce(
                allocator,
                chain="gnosis",
                sender=service.requester(),
                mech=MECH_ADDRESS,
                salt="",
                read_map_nonces=lambda: 5,
                send=send,
                not_sent=(),
                timeout=1,
                **kwargs,
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            return allocator, e
        return allocator, result

    @staticmethod
    def _next_nonce(allocator: NonceAllocator, service: MarketplaceService) -> int:
        """Return the nonce the allocator would hand out next."""
        with allocator.reserve(
            "gnosis", service.requester(), MECH_ADDRESS, lambda: 5, timeout=1
        ) as slot:
            slot.answered("not_accepted", mech=MECH_ADDRESS, salt="", posted=False)
            return slot.nonce

    def test_an_async_hook_through_send_with_nonce_is_refused_unsigned(
        self, service: MarketplaceService, mech_post: MagicMock, tmp_path: Path
    ) -> None:
        """The tracking hook hands the awaitable back, so send_request refuses it."""

        async def record(request_id: bytes, nonce: int) -> None:
            raise AssertionError("never awaited")

        allocator, raised = self._through_allocator(
            service, tmp_path, _nonce_contract(5), on_request_id=record
        )

        assert isinstance(raised, TypeError)
        service.signer.sign_message.assert_not_called()
        mech_post.assert_not_called()
        assert self._next_nonce(allocator, service) == 5  # freed: nothing was sent

    def test_a_pre_sign_failure_through_send_with_nonce_frees_the_nonce(
        self, service: MarketplaceService, mech_post: MagicMock, tmp_path: Path
    ) -> None:
        """A nonce below mapNonces fails in send_request before the hook: freed."""
        allocator, raised = self._through_allocator(
            service, tmp_path, _nonce_contract(7)
        )

        assert isinstance(raised, ValueError)
        mech_post.assert_not_called()
        assert self._next_nonce(allocator, service) == 5

    def test_a_signer_failure_through_send_with_nonce_frees_the_nonce(
        self, service: MarketplaceService, mech_post: MagicMock, tmp_path: Path
    ) -> None:
        """The signer fails after the hook ran but before the POST: freed."""
        service.signer.sign_message.side_effect = RuntimeError("signer offline")
        hooked: List[int] = []

        allocator, raised = self._through_allocator(
            service,
            tmp_path,
            _nonce_contract(5),
            on_request_id=lambda request_id, nonce: hooked.append(nonce),
        )

        assert isinstance(raised, RuntimeError)
        assert hooked == [5]
        mech_post.assert_not_called()
        assert self._next_nonce(allocator, service) == 5

    def test_a_lying_rpc_through_send_with_nonce_frees_the_nonce(
        self, service: MarketplaceService, mech_post: MagicMock, tmp_path: Path
    ) -> None:
        """RequestIdMismatch comes before the hook: nothing signed, n free."""
        contract = TestLocalRequestId._lying(_nonce_contract(5), 5, b"\x66" * 32)
        hooked: List[int] = []

        allocator, raised = self._through_allocator(
            service,
            tmp_path,
            contract,
            on_request_id=lambda request_id, nonce: hooked.append(nonce),
        )

        assert isinstance(raised, RequestIdMismatch)
        assert hooked == []
        service.signer.sign_message.assert_not_called()
        mech_post.assert_not_called()
        assert self._next_nonce(allocator, service) == 5

    def test_a_transport_error_through_send_with_nonce_holds_the_nonce(
        self, service: MarketplaceService, mech_post: MagicMock, tmp_path: Path
    ) -> None:
        """After the hook the mech may hold the request: the slot stays held."""
        mech_post.side_effect = requests.ConnectionError("reset")

        allocator, raised = self._through_allocator(
            service, tmp_path, _nonce_contract(5)
        )

        assert isinstance(raised, ValueError)
        assert self._next_nonce(allocator, service) == 6

    @pytest.mark.parametrize(("second", "deposits"), [(201, [300]), (200, [300, 200])])
    def test_one_request_s_deposits_across_its_resends_never_exceed_max_price(
        self,
        service: MarketplaceService,
        mech_post: MagicMock,
        tmp_path: Path,
        second: int,
        deposits: list,
    ) -> None:
        """A 503 resend of the request draws on the max_price its first send drew on."""
        mech_post.side_effect = [
            _mock_http_response(402, {"required": "100", "currentBalance": "-200"}),
            _mock_http_response(503, {"error": "gap"}),
            _mock_http_response(
                402, {"required": "100", "currentBalance": str(100 - second)}
            ),
            _mock_http_response(200),
        ]

        with (
            patch("mech_client.services.deposit_service.DepositService") as service_cls,
            patch(f"{SERVICE}.wait_for_receipt", return_value={"status": 1}),
        ):
            _, raised = self._through_allocator(
                service,
                tmp_path,
                _nonce_contract(5),
                request={"auto_deposit": True, "max_price": 500},
                gap_retries=1,
            )

        sent = [c.args[0] for c in service_cls.return_value.deposit_native.call_args_list]
        assert sent == deposits
        if len(deposits) == 1:
            assert isinstance(raised, NonceRefused)
            assert "300 already deposited for these requests" in str(raised.__cause__)

    def test_an_auto_deposit_above_max_price_keeps_the_posted_nonce_held(
        self, service: MarketplaceService, mech_post: MagicMock, tmp_path: Path
    ) -> None:
        """The refused top-up follows the POST, so the slot stays held."""
        mech_post.side_effect = [
            _mock_http_response(402, {"required": "100", "currentBalance": "-500"})
        ]

        with patch("mech_client.services.deposit_service.DepositService") as deposits:
            allocator, raised = self._through_allocator(
                service,
                tmp_path,
                _nonce_contract(5),
                request={"auto_deposit": True, "max_price": 500},
            )

        assert isinstance(raised, NonceRefused)
        assert isinstance(raised.__cause__, OffchainTopUpFailed)
        assert "max_price of 500" in str(raised)
        deposits.assert_not_called()
        assert mech_post.call_count == 1
        assert self._next_nonce(allocator, service) == 6

    def test_a_pre_sign_hook_only_moves_forward(self) -> None:
        """Its stage is read-only, posting requires received, and it serves one send."""
        hook = PreSignHook()
        with pytest.raises(ValueError, match="before it is received"):
            hook.mark_posting()
        with pytest.raises(AttributeError):
            hook.received = True  # type: ignore[misc]
        hook.mark_received()
        hook.mark_posting()
        hook.mark_posting()  # a later request of the call
        with pytest.raises(ValueError, match="serves one send_request"):
            hook.mark_received()
        assert (hook.received, hook.posting) == (True, True)
        assert hook(b"id", 5) is None  # no inner hook

    def test_errors_are_exported(self) -> None:
        """Both exceptions are part of the public API."""
        assert mech_client.OffchainRequestRejected is OffchainRequestRejected
        assert mech_client.OffchainTopUpFailed is OffchainTopUpFailed


class TestLocalRequestId:
    """The signed id is derived locally; an RPC that disagrees is refused."""

    @pytest.fixture
    def service(self) -> MarketplaceService:
        """Client-mode service with a real signer."""
        service = _build_offchain_service()
        service.signer = _real_signing_signer()
        return service

    @pytest.fixture
    def mech_post(self) -> Any:
        """Patch the mech's POST endpoint; tests set its responses."""
        watcher = AsyncMock()
        watcher.watch.return_value = {}
        with (
            patch(
                "mech_client.infrastructure.ipfs.metadata.fetch_ipfs_hash",
                return_value=("0x" + "b" * 64, "full-hash", '{"prompt":"a"}'),
            ),
            patch(f"{SERVICE}.requests.post") as post,
            patch(f"{SERVICE}.OffchainDeliveryWatcher", return_value=watcher),
        ):
            yield post

    @staticmethod
    def _lying(contract: MagicMock, bad_nonce: int, answer: bytes) -> MagicMock:
        """Make getRequestId answer ``answer`` for ``bad_nonce`` only."""
        honest = contract.functions.getRequestId.side_effect

        def get_request_id(*args: Any) -> MagicMock:
            if args[-1] == bad_nonce:
                return MagicMock(call=MagicMock(return_value=answer))
            return honest(*args)

        contract.functions.getRequestId.side_effect = get_request_id
        return contract

    @pytest.mark.asyncio
    async def test_the_locally_derived_id_is_hooked_signed_and_sent(
        self, service: MarketplaceService, mech_post: MagicMock
    ) -> None:
        """The hook, the signature and the payload all carry request_digest's id."""
        mech_post.side_effect = [_mock_http_response(200)]
        hook = MagicMock()
        contract = _nonce_contract(5)

        result = await _send_offchain(service, contract, on_request_id=hook)

        expected = _request_id_for(5)
        hook.assert_called_once_with(expected, 5)
        service.signer.sign_message.assert_called_once_with(expected)
        payload = mech_post.call_args.kwargs["data"]
        assert payload["request_id"] == int.from_bytes(expected, "big")
        assert result["request_ids"] == [expected.hex()]
        contract.functions.getRequestId.assert_called_once()

    @pytest.mark.asyncio
    async def test_a_mismatch_is_refused_before_the_hook_and_signing(
        self, service: MarketplaceService, mech_post: MagicMock
    ) -> None:
        """A lying RPC can only cause a refusal: nothing is hooked, signed or sent."""
        hook = MagicMock()
        contract = self._lying(_nonce_contract(5), 5, b"\x66" * 32)

        with pytest.raises(RequestIdMismatch) as e:
            await _send_offchain(service, contract, on_request_id=hook)

        assert isinstance(e.value, ValueError)
        assert (e.value.expected, e.value.reported, e.value.nonce) == (
            _request_id_for(5).hex(),
            "66" * 32,
            5,
        )
        hook.assert_not_called()
        service.signer.sign_message.assert_not_called()
        mech_post.assert_not_called()

    @pytest.mark.asyncio
    async def test_a_mismatch_mid_call_names_the_accepted_requests(
        self, service: MarketplaceService, mech_post: MagicMock
    ) -> None:
        """The first request went out; the error says so, and the second is not signed."""
        mech_post.side_effect = [_mock_http_response(200)]
        contract = self._lying(_nonce_contract(5), 6, b"\x66" * 32)

        with pytest.raises(RequestIdMismatch) as e:
            await _send_offchain(service, contract, prompts=("a", "b"), nonces=[5, 6])

        assert f"{_request_id_for(5).hex()} (nonce 5)" in str(e.value)
        assert service.signer.sign_message.call_count == 1
        assert mech_post.call_count == 1

    @pytest.mark.asyncio
    async def test_an_rpc_failure_mid_call_names_the_accepted_requests(
        self, service: MarketplaceService, mech_post: MagicMock
    ) -> None:
        """getRequestId failing on request 2 is a plain ValueError naming request 1."""
        mech_post.side_effect = [_mock_http_response(200)]
        contract = _nonce_contract(5)
        honest = contract.functions.getRequestId.side_effect

        def get_request_id(*args: Any) -> MagicMock:
            if args[-1] == 6:
                raise Web3Exception("rpc down: https://rpc.example/v3/SECRETKEY")
            return honest(*args)

        contract.functions.getRequestId.side_effect = get_request_id

        with pytest.raises(ValueError) as e:
            await _send_offchain(service, contract, prompts=("a", "b"), nonces=[5, 6])

        assert type(e.value) is ValueError  # pylint: disable=unidiomatic-typecheck
        assert isinstance(e.value.__cause__, Web3Exception)
        assert "nonce 6 (Web3Exception)" in str(e.value)
        assert "SECRETKEY" not in str(e.value)
        assert f"{_request_id_for(5).hex()} (nonce 5)" in str(e.value)
        assert mech_post.call_count == 1

    @pytest.mark.asyncio
    async def test_an_rpc_failure_on_the_first_request_names_only_its_type(
        self, service: MarketplaceService, mech_post: MagicMock
    ) -> None:
        """The keyed RPC URL stays out of the error and the log on the first request too."""
        contract = _nonce_contract(5)
        contract.functions.getRequestId.side_effect = Web3Exception(
            "rpc down: https://rpc.example/v3/SECRETKEY"
        )

        with patch(
            "mech_client.services.marketplace_service.logger.warning"
        ) as mock_warn, pytest.raises(ValueError) as e:
            await _send_offchain(service, contract)

        assert type(e.value) is ValueError  # pylint: disable=unidiomatic-typecheck
        assert isinstance(e.value.__cause__, Web3Exception)
        assert "nonce 5 (Web3Exception)" in str(e.value)
        assert "SECRETKEY" not in str(e.value)
        assert "Accepted earlier" not in str(e.value)
        (warning,) = mock_warn.call_args[0]
        assert "nonce 5" in warning and "Web3Exception" in warning
        assert "SECRETKEY" not in warning
        mech_post.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("kwargs", "named"), [({"nonces": [7]}, "nonce 7"), ({}, "the next nonce")]
    )
    async def test_a_map_nonces_failure_names_only_its_type(
        self,
        service: MarketplaceService,
        mech_post: MagicMock,
        kwargs: Dict[str, Any],
        named: str,
    ) -> None:
        """The mapNonces read keeps the keyed RPC URL out of the error and the log."""
        contract = _nonce_contract(5)
        contract.functions.mapNonces.return_value.call.side_effect = Web3Exception(
            "rpc down: https://rpc.example/v3/SECRETKEY"
        )

        with patch(
            "mech_client.services.marketplace_service.logger.warning"
        ) as mock_warn, pytest.raises(ValueError) as e:
            await _send_offchain(service, contract, **kwargs)

        assert type(e.value) is ValueError  # pylint: disable=unidiomatic-typecheck
        assert isinstance(e.value.__cause__, Web3Exception)
        assert f"{named} (Web3Exception)" in str(e.value)
        assert "SECRETKEY" not in str(e.value)
        (warning,) = mock_warn.call_args[0]
        assert named in warning and "Web3Exception" in warning
        assert "SECRETKEY" not in warning
        mech_post.assert_not_called()

    @pytest.mark.asyncio
    async def test_a_domain_separator_failure_names_only_its_type(
        self, service: MarketplaceService, mech_post: MagicMock
    ) -> None:
        """The domainSeparator read keeps the keyed RPC URL out of the error and the log."""
        contract = _nonce_contract(5)
        contract.functions.domainSeparator.return_value.call.side_effect = OSError(
            "HTTPSConnectionPool(host='rpc.example'): Max retries exceeded with "
            "url: /v3/SECRETKEY"
        )

        with patch(
            "mech_client.services.marketplace_service.logger.warning"
        ) as mock_warn, pytest.raises(ValueError) as e:
            await _send_offchain(service, contract)

        assert type(e.value) is ValueError  # pylint: disable=unidiomatic-typecheck
        assert isinstance(e.value.__cause__, OSError)
        assert "nonce 5 (OSError)" in str(e.value)
        assert "SECRETKEY" not in str(e.value)
        (warning,) = mock_warn.call_args[0]
        assert "nonce 5" in warning and "OSError" in warning
        assert "SECRETKEY" not in warning
        service.signer.sign_message.assert_not_called()
        mech_post.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("read", ["mapNonces", "domainSeparator", "getRequestId"])
    @pytest.mark.parametrize(
        "cause",
        [
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.HTTPError,
        ],
    )
    async def test_an_unreachable_rpc_is_a_value_error_the_cli_points_at_the_rpc(
        self,
        service: MarketplaceService,
        mech_post: MagicMock,
        read: str,
        cause: type,
    ) -> None:
        """Library callers still catch ValueError; the CLI adds its MECHX_CHAIN_RPC hint."""
        contract = _nonce_contract(5)
        failing = getattr(contract.functions, read)
        failing.side_effect = None
        failing.return_value.call.side_effect = cause(
            "Max retries exceeded with url: /v3/SECRETKEY"
        )

        with pytest.raises(ValueError) as e:
            await _send_offchain(service, contract)

        assert isinstance(e.value, RpcError)
        assert isinstance(e.value.__cause__, cause)
        assert f"({cause.__name__})" in str(e.value)
        assert "SECRETKEY" not in str(e.value)
        mech_post.assert_not_called()

        @handle_cli_errors
        def command() -> None:
            raise e.value

        with pytest.raises(ClickException) as shown:
            command()
        assert "Failed to derive the request id" in shown.value.message
        assert "MECHX_CHAIN_RPC" in shown.value.message
        assert "SECRETKEY" not in shown.value.message

    def test_mismatch_survives_pickle_and_copy(self) -> None:
        """Every field comes back after a round trip."""
        err = RequestIdMismatch("bad", expected="aa", reported="bb", nonce=3)

        for clone in (pickle.loads(pickle.dumps(err)), copy.copy(err)):
            assert str(clone) == "bad"
            assert (clone.expected, clone.reported, clone.nonce) == ("aa", "bb", 3)


class TestPriceCap:
    """max_price refuses a mech above it before anything is paid or signed."""

    @pytest.fixture
    def service(self) -> MarketplaceService:
        """Client-mode service whose mech charges 10 per request."""
        service = _build_offchain_service()
        service.tool_manager = MagicMock()
        service.tool_manager.terms_report.return_value = {"valory_operated": False}
        return service

    async def _send(self, service: MarketplaceService, **kwargs: Any) -> MagicMock:
        """Send two prompts off-chain; return the patched offchain path."""
        with (
            patch.object(service, "marketplace_contract"),
            patch.object(
                service,
                "mech_info",
                return_value=MechInfo(MECH_ADDRESS, 1, PaymentType.NATIVE, 10),
            ),
            patch.object(service, "_validate_tools"),
            patch.object(
                service, "_send_offchain_request", new_callable=AsyncMock
            ) as mock_offchain,
        ):
            await service.send_request(
                prompts=("a", "b"),
                tools=("t", "t"),
                priority_mech=MECH_ADDRESS,
                use_offchain=True,
                **kwargs,
            )
        return mock_offchain

    @pytest.mark.asyncio
    @pytest.mark.parametrize("max_price", [19, 0])
    async def test_a_price_above_the_cap_is_refused_before_anything_is_sent(
        self, service: MarketplaceService, max_price: int
    ) -> None:
        """2 requests x 10 > 19 (or 0): refused with the price and the cap."""
        with patch(f"{SERVICE}.PaymentStrategyFactory") as payment_factory:
            with pytest.raises(MechPriceExceeded) as e:
                await self._send(service, max_price=max_price)

        assert isinstance(e.value, ValueError)
        assert (e.value.price, e.value.max_price) == (20, max_price)
        service.tool_manager.terms_report.assert_not_called()
        payment_factory.create.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(("max_price", "sent"), [(12, True), (11, False)])
    async def test_the_price_is_the_signed_cap_not_the_advertised_rate(
        self, service: MarketplaceService, max_price: int, sent: bool
    ) -> None:
        """Off-chain, 2 requests at a cap of 2 x 3 cost 12, under the advertised 2 x 10."""
        service.tool_manager.read_tools_metadata.return_value = MetadataRead(
            {"toolMetadata": {"t": {"expectedCost": {"asset": "native", "amount": "3"}}}},
            None,
        )

        if sent:
            mock_offchain = await self._send(service, max_price=max_price)
            assert mock_offchain.call_args.kwargs["max_delivery_rate"] == 6
        else:
            with pytest.raises(MechPriceExceeded) as e:
                await self._send(service, max_price=max_price)
            assert e.value.price == 12

    @pytest.mark.asyncio
    @pytest.mark.parametrize("max_price", [20, None])
    async def test_a_price_at_the_cap_or_no_cap_is_sent(
        self, service: MarketplaceService, max_price: Optional[int]
    ) -> None:
        """Exactly at the cap is within it; no cap keeps today's behaviour."""
        mock_offchain = await self._send(service, max_price=max_price)

        mock_offchain.assert_awaited_once()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("max_price", ["20", True, 2.5])
    async def test_a_non_integer_cap_is_refused_early(
        self, service: MarketplaceService, max_price: Any
    ) -> None:
        """A cap that is not an int fails before any chain read."""
        with patch.object(service, "marketplace_contract") as mock_contract:
            with pytest.raises(ValueError, match="max_price"):
                await service.send_request(
                    prompts=("a",), tools=("t",), max_price=max_price
                )

        mock_contract.assert_not_called()

    @pytest.mark.asyncio
    async def test_the_cap_also_binds_an_on_chain_request(
        self, service: MarketplaceService
    ) -> None:
        """On-chain, the cap refuses before the upload, the approve and the send."""
        with (
            patch.object(service, "marketplace_contract"),
            patch.object(
                service,
                "mech_info",
                return_value=MechInfo(MECH_ADDRESS, 1, PaymentType.OLAS_TOKEN, 10),
            ),
            patch.object(service, "_validate_tools"),
            patch(f"{SERVICE}.PaymentStrategyFactory") as payment_factory,
            patch(f"{SERVICE}.push_metadata_to_ipfs") as push,
            patch.object(service, "_send_marketplace_request") as send,
        ):
            with pytest.raises(MechPriceExceeded):
                await service.send_request(
                    prompts=("a", "b"),
                    tools=("t", "t"),
                    priority_mech=MECH_ADDRESS,
                    max_price=19,
                )

        payment_factory.create.assert_not_called()
        push.assert_not_called()
        send.assert_not_called()

    def test_price_exceeded_survives_pickle_and_copy(self) -> None:
        """Every field comes back after a round trip."""
        err = MechPriceExceeded("too much", price=20, max_price=19)

        for clone in (pickle.loads(pickle.dumps(err)), copy.copy(err)):
            assert str(clone) == "too much"
            assert (clone.price, clone.max_price) == (20, 19)


class TestRpcUrlArgument:
    """rpc_url reaches every RPC the service and its helpers open."""

    @patch("mech_client.services.marketplace_service.IPFSClient")
    @patch("mech_client.services.marketplace_service.ToolManager")
    @patch("mech_client.services.base_service.ExecutorFactory")
    @patch("mech_client.services.base_service.EthereumApi")
    @patch("mech_client.services.base_service.get_mech_config")
    def test_the_service_its_tool_manager_and_its_top_up_share_the_rpc(
        self,
        mock_config: MagicMock,
        mock_ledger_api: MagicMock,
        mock_executor_factory: MagicMock,
        mock_tool_manager: MagicMock,
        mock_ipfs_client: MagicMock,
    ) -> None:
        """The auto-deposit's DepositService uses the calling service's RPC."""
        mock_config.return_value = create_mock_mech_config()
        service = MarketplaceService(
            chain_config="gnosis",
            agent_mode=False,
            crypto=create_mock_crypto(),
            rpc_url="https://caller.example",
        )

        mock_config.assert_called_once_with(
            "gnosis", agent_mode=False, rpc_url="https://caller.example"
        )
        mock_tool_manager.assert_called_once_with(
            "gnosis", rpc_url="https://caller.example"
        )
        with (
            patch("mech_client.services.deposit_service.DepositService") as mock_ds,
            patch(f"{SERVICE}.wait_for_receipt", return_value={"status": 1}),
        ):
            service._auto_deposit_for_402(  # pylint: disable=protected-access
                PaymentType.NATIVE,
                PaymentChallenge(100, 30, "0xbt", "", 100, "ib"),
                max_delivery_rate=100,
            )
        assert mock_ds.call_args.kwargs["rpc_url"] == "https://caller.example"


class TestSendRequestMechAndMetadata:
    """Which mech send_request reads, and what it says when metadata is unreadable."""

    @pytest.fixture
    def service(self) -> MarketplaceService:
        """Client-mode service whose config names a priority mech."""
        service = _build_offchain_service()
        service.mech_config.priority_mech_address = "0x" + "c" * 40
        service.tool_manager = MagicMock()
        service.tool_manager.terms_report.return_value = {"valory_operated": False}
        service.tool_manager.offchain_url_from_metadata = (
            ToolManager.offchain_url_from_metadata
        )
        return service

    async def _send(
        self, service: MarketplaceService, read: MetadataRead, **kwargs: Any
    ) -> MagicMock:
        """Send one off-chain prompt; return the patched mech_info."""
        service.tool_manager.read_tools_metadata.return_value = read
        with (
            patch.object(service, "marketplace_contract"),
            patch.object(
                service,
                "mech_info",
                return_value=MechInfo(MECH_ADDRESS, 1, PaymentType.NATIVE, 1),
            ) as mech_info,
            patch.object(service, "_validate_tools"),
            patch.object(service, "_send_offchain_request", new_callable=AsyncMock),
        ):
            await service.send_request(
                prompts=("a",), tools=("t",), use_offchain=True, **kwargs
            )
        return mech_info

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("priority_mech", "expected"),
        [(None, "0x" + "c" * 40), ("0x" + "d" * 40, "0x" + "d" * 40)],
    )
    async def test_the_configured_mech_is_read_unless_one_is_given(
        self,
        service: MarketplaceService,
        priority_mech: Optional[str],
        expected: str,
    ) -> None:
        """priority_mech=None falls back to the config; an explicit one wins."""
        read = MetadataRead({"url": "https://mech.example"}, None)

        mech_info = await self._send(service, read, priority_mech=priority_mech)

        mech_info.assert_called_once_with(expected)

    @pytest.mark.asyncio
    async def test_an_unreadable_document_names_its_cause(
        self, service: MarketplaceService
    ) -> None:
        """A transient read failure is told apart from a mech that never published."""
        with pytest.raises(ValueError) as e:
            await self._send(service, MetadataRead(None, "Timeout: slow"))

        assert str(e.value) == (
            "Mech service 1: metadata unreadable (Timeout: slow); may be "
            "transient or never published"
        )

    @pytest.mark.asyncio
    async def test_a_document_without_a_usable_url_is_refused(
        self, service: MarketplaceService
    ) -> None:
        """A non-string url is as missing as no url."""
        with pytest.raises(ValueError, match="no 'url' in metadata"):
            await self._send(service, MetadataRead({"url": 42}, None))
