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

"""Tests for utils.errors module."""

from unittest.mock import MagicMock, patch

import pytest
import requests
from click import ClickException
from web3.exceptions import ContractLogicError, Web3ValidationError

from mech_client.utils.errors import (
    AgentModeError,
    ConfigurationError,
    ContractError,
    DeliveryTimeoutError,
    ErrorMessages,
    IPFSError,
    MechClientError,
    PaymentError,
    RpcError,
    SubgraphError,
    ToolError,
    TransactionError,
    ValidationError,
)


class TestMechClientError:
    """Tests for MechClientError base exception."""

    def test_error_with_message_only(self) -> None:
        """Test creating error with message only."""
        error = MechClientError("Test error")
        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.details is None

    def test_error_with_details(self) -> None:
        """Test creating error with message and details."""
        error = MechClientError("Test error", details="Additional context")
        expected = "Test error\n\nDetails: Additional context"
        assert str(error) == expected
        assert error.message == "Test error"
        assert error.details == "Additional context"


class TestRpcError:
    """Tests for RpcError exception."""

    def test_rpc_error_with_url(self) -> None:
        """Test creating RPC error with URL."""
        error = RpcError(
            "Connection failed", rpc_url="https://rpc.example.com"
        )
        assert error.message == "Connection failed"
        assert error.rpc_url == "https://rpc.example.com"

    def test_rpc_error_without_url(self) -> None:
        """Test creating RPC error without URL."""
        error = RpcError("Connection failed")
        assert error.rpc_url is None


class TestSubgraphError:
    """Tests for SubgraphError exception."""

    def test_subgraph_error_with_url(self) -> None:
        """Test creating subgraph error with URL."""
        error = SubgraphError(
            "Query failed", subgraph_url="https://subgraph.example.com"
        )
        assert error.message == "Query failed"
        assert error.subgraph_url == "https://subgraph.example.com"


class TestContractError:
    """Tests for ContractError exception."""

    def test_contract_error_with_address(self) -> None:
        """Test creating contract error with address."""
        error = ContractError(
            "Execution reverted", contract_address="0x1234"
        )
        assert error.message == "Execution reverted"
        assert error.contract_address == "0x1234"


class TestValidationError:
    """Tests for ValidationError exception."""

    def test_validation_error_with_field(self) -> None:
        """Test creating validation error with field name."""
        error = ValidationError("Invalid amount", field="amount")
        assert error.message == "Invalid amount"
        assert error.field == "amount"


class TestTransactionError:
    """Tests for TransactionError exception."""

    def test_transaction_error_with_hash(self) -> None:
        """Test creating transaction error with tx hash."""
        error = TransactionError("TX failed", tx_hash="0xabcd")
        assert error.message == "TX failed"
        assert error.tx_hash == "0xabcd"


class TestIPFSError:
    """Tests for IPFSError exception."""

    def test_ipfs_error_with_hash(self) -> None:
        """Test creating IPFS error with hash."""
        error = IPFSError("Upload failed", ipfs_hash="Qm123")
        assert error.message == "Upload failed"
        assert error.ipfs_hash == "Qm123"


class TestToolError:
    """Tests for ToolError exception."""

    def test_tool_error_with_id(self) -> None:
        """Test creating tool error with tool ID."""
        error = ToolError("Tool not found", tool_id="1-openai-gpt-4")
        assert error.message == "Tool not found"
        assert error.tool_id == "1-openai-gpt-4"


class TestPaymentError:
    """Tests for PaymentError exception."""

    def test_payment_error_with_type(self) -> None:
        """Test creating payment error with payment type."""
        error = PaymentError("Insufficient balance", payment_type="NATIVE")
        assert error.message == "Insufficient balance"
        assert error.payment_type == "NATIVE"


class TestDeliveryTimeoutError:
    """Tests for DeliveryTimeoutError exception."""

    def test_delivery_timeout_with_request_ids(self) -> None:
        """Test creating delivery timeout error with request IDs."""
        error = DeliveryTimeoutError(
            "Timeout waiting for delivery", request_ids=["1", "2"]
        )
        assert error.message == "Timeout waiting for delivery"
        assert error.request_ids == ["1", "2"]

    def test_delivery_timeout_without_request_ids(self) -> None:
        """Test creating delivery timeout error without request IDs."""
        error = DeliveryTimeoutError("Timeout waiting for delivery")
        assert error.request_ids == []


class TestErrorMessages:
    """Tests for ErrorMessages template class."""

    def test_rpc_error_message(self) -> None:
        """Test RPC error message formatting."""
        msg = ErrorMessages.rpc_error(
            "https://rpc.example.com", "Connection refused"
        )
        assert "RPC endpoint error" in msg
        assert "https://rpc.example.com" in msg
        assert "Connection refused" in msg
        assert "MECHX_CHAIN_RPC" in msg

    def test_rpc_network_error_message(self) -> None:
        """Test RPC network error message formatting."""
        msg = ErrorMessages.rpc_network_error(
            "https://rpc.example.com", "Timeout"
        )
        assert "Network error" in msg
        assert "https://rpc.example.com" in msg

    def test_rpc_timeout_with_url(self) -> None:
        """Test RPC timeout message with URL."""
        msg = ErrorMessages.rpc_timeout(
            "https://rpc.example.com", "Timeout after 300s"
        )
        assert "Timeout while waiting" in msg
        assert "https://rpc.example.com" in msg

    def test_rpc_timeout_without_url(self) -> None:
        """Test RPC timeout message without URL."""
        msg = ErrorMessages.rpc_timeout(None, "Timeout after 300s")
        assert "default RPC endpoint" in msg

    def test_subgraph_error_message(self) -> None:
        """Test subgraph error message formatting."""
        msg = ErrorMessages.subgraph_error(
            "https://subgraph.example.com", "Query failed"
        )
        assert "Subgraph endpoint error" in msg
        assert "https://subgraph.example.com" in msg

    def test_contract_logic_error_message(self) -> None:
        """Test contract logic error message formatting."""
        msg = ErrorMessages.contract_logic_error("Execution reverted")
        assert "Smart contract error" in msg
        assert "Execution reverted" in msg

    def test_validation_error_message(self) -> None:
        """Test validation error message formatting."""
        msg = ErrorMessages.validation_error("Invalid amount")
        assert "validation error" in msg
        assert "Invalid amount" in msg

    def test_missing_env_var_message(self) -> None:
        """Test missing environment variable message formatting."""
        msg = ErrorMessages.missing_env_var("MECHX_CHAIN_RPC", "RPC access")
        assert "MECHX_CHAIN_RPC" in msg
        assert "RPC access" in msg

    def test_chain_not_supported_message(self) -> None:
        """Test chain not supported message formatting."""
        msg = ErrorMessages.chain_not_supported(
            "arbitrum", "marketplace", "gnosis, base"
        )
        assert "arbitrum" in msg
        assert "marketplace" in msg
        assert "gnosis, base" in msg

    def test_insufficient_balance_message(self) -> None:
        """Test insufficient balance message formatting."""
        msg = ErrorMessages.insufficient_balance("OLAS", "100", "50")
        assert "Insufficient OLAS balance" in msg
        assert "Required: 100" in msg
        assert "Available: 50" in msg

    def test_agent_mode_not_setup_message(self) -> None:
        """Test agent mode not setup message formatting."""
        msg = ErrorMessages.agent_mode_not_setup("gnosis")
        assert "not set up" in msg
        assert "gnosis" in msg
        assert "setup" in msg

    def test_tool_not_found_message(self) -> None:
        """Test tool not found message formatting."""
        msg = ErrorMessages.tool_not_found("1-gpt-4", 1)
        assert "1-gpt-4" in msg
        assert "mechx tool list 1" in msg

    def test_ipfs_error_message(self) -> None:
        """Test IPFS error message formatting."""
        msg = ErrorMessages.ipfs_error("upload", "Gateway unavailable")
        assert "IPFS upload error" in msg
        assert "Gateway unavailable" in msg

    def test_delivery_timeout_message(self) -> None:
        """Test delivery timeout message formatting."""
        msg = ErrorMessages.delivery_timeout(900.0, ["1", "2", "3"])
        assert "900" in msg
        assert "1, 2, 3" in msg

    def test_private_key_permission_error(self) -> None:
        """Test private key permission error message formatting."""
        msg = ErrorMessages.private_key_error(
            "permission", "Permission denied"
        )
        assert "Permission denied" in msg
        assert "chmod 600" in msg

    def test_private_key_decryption_error(self) -> None:
        """Test private key decryption error message formatting."""
        msg = ErrorMessages.private_key_error(
            "decryption", "Failed to decrypt"
        )
        assert "decrypt" in msg
        assert "password" in msg

    def test_private_key_not_found_error(self) -> None:
        """Test private key not found error message formatting."""
        msg = ErrorMessages.private_key_error("not_found", "File not found")
        assert "not found" in msg
        assert "--key" in msg


class TestHandleCliErrors:
    """Tests for handle_cli_errors decorator."""

    def _make_handler(self) -> None:
        """Import handler inside test to avoid circular import issues at module level."""
        from mech_client.utils.errors.handlers import (  # pylint: disable=import-outside-toplevel
            handle_cli_errors,
        )

        return handle_cli_errors

    def test_returns_value_on_success(self) -> None:
        """Test that normal function return values pass through."""
        handle_cli_errors = self._make_handler()

        @handle_cli_errors
        def func() -> str:
            return "success"

        assert func() == "success"

    def test_reraises_click_exception(self) -> None:
        """Test that existing ClickExceptions are re-raised unchanged."""
        handle_cli_errors = self._make_handler()

        @handle_cli_errors
        def func() -> None:
            raise ClickException("Original error")

        with pytest.raises(ClickException) as exc_info:
            func()
        assert exc_info.value.message == "Original error"

    @patch("mech_client.utils.errors.handlers.EnvironmentConfig.load")
    def test_handles_rpc_error_with_url(self, mock_env_load: MagicMock) -> None:
        """Test RpcError is converted to ClickException with rpc_url."""
        mock_env_load.return_value.mechx_chain_rpc = None
        handle_cli_errors = self._make_handler()

        @handle_cli_errors
        def func() -> None:
            raise RpcError("Connection failed", rpc_url="https://rpc.example.com")

        with pytest.raises(ClickException) as exc_info:
            func()
        assert "https://rpc.example.com" in exc_info.value.message

    @patch("mech_client.utils.errors.handlers.EnvironmentConfig.load")
    def test_handles_rpc_error_falls_back_to_env(self, mock_env_load: MagicMock) -> None:
        """Test RpcError without url falls back to env config."""
        mock_env_load.return_value.mechx_chain_rpc = "https://env-rpc.example.com"
        handle_cli_errors = self._make_handler()

        @handle_cli_errors
        def func() -> None:
            raise RpcError("Connection failed")  # no rpc_url

        with pytest.raises(ClickException) as exc_info:
            func()
        assert "https://env-rpc.example.com" in exc_info.value.message

    @patch("mech_client.utils.errors.handlers.EnvironmentConfig.load")
    def test_handles_subgraph_error(self, mock_env_load: MagicMock) -> None:
        """Test SubgraphError is converted to ClickException."""
        mock_env_load.return_value.mechx_subgraph_url = None
        handle_cli_errors = self._make_handler()

        @handle_cli_errors
        def func() -> None:
            raise SubgraphError(
                "Query failed", subgraph_url="https://subgraph.example.com"
            )

        with pytest.raises(ClickException) as exc_info:
            func()
        assert "https://subgraph.example.com" in exc_info.value.message

    def test_handles_contract_error(self) -> None:
        """Test ContractError is converted to ClickException."""
        handle_cli_errors = self._make_handler()

        @handle_cli_errors
        def func() -> None:
            raise ContractError("Execution reverted")

        with pytest.raises(ClickException) as exc_info:
            func()
        assert "Execution reverted" in exc_info.value.message

    def test_handles_validation_error(self) -> None:
        """Test ValidationError is converted to ClickException."""
        handle_cli_errors = self._make_handler()

        @handle_cli_errors
        def func() -> None:
            raise ValidationError("Invalid address")

        with pytest.raises(ClickException) as exc_info:
            func()
        assert "Invalid address" in exc_info.value.message

    def test_handles_transaction_error(self) -> None:
        """Test TransactionError is converted to ClickException."""
        handle_cli_errors = self._make_handler()

        @handle_cli_errors
        def func() -> None:
            raise TransactionError("TX failed")

        with pytest.raises(ClickException) as exc_info:
            func()
        assert "Transaction error" in exc_info.value.message

    def test_handles_payment_error(self) -> None:
        """Test PaymentError is converted to ClickException."""
        handle_cli_errors = self._make_handler()

        @handle_cli_errors
        def func() -> None:
            raise PaymentError("Insufficient balance")

        with pytest.raises(ClickException) as exc_info:
            func()
        assert "Payment error" in exc_info.value.message

    def test_handles_ipfs_error_upload(self) -> None:
        """Test IPFSError with 'upload' becomes upload operation in message."""
        handle_cli_errors = self._make_handler()

        @handle_cli_errors
        def func() -> None:
            raise IPFSError("IPFS upload failed: gateway unreachable")

        with pytest.raises(ClickException) as exc_info:
            func()
        assert "upload" in exc_info.value.message

    def test_handles_ipfs_error_download(self) -> None:
        """Test IPFSError with 'download' becomes download operation in message."""
        handle_cli_errors = self._make_handler()

        @handle_cli_errors
        def func() -> None:
            raise IPFSError("IPFS download failed: not found")

        with pytest.raises(ClickException) as exc_info:
            func()
        assert "download" in exc_info.value.message

    def test_handles_ipfs_error_generic(self) -> None:
        """Test IPFSError with no operation keyword defaults to 'operation'."""
        handle_cli_errors = self._make_handler()

        @handle_cli_errors
        def func() -> None:
            raise IPFSError("IPFS error: generic failure")

        with pytest.raises(ClickException) as exc_info:
            func()
        assert "operation" in exc_info.value.message

    def test_handles_tool_error(self) -> None:
        """Test ToolError is converted to ClickException."""
        handle_cli_errors = self._make_handler()

        @handle_cli_errors
        def func() -> None:
            raise ToolError("Tool not found")

        with pytest.raises(ClickException) as exc_info:
            func()
        assert "Tool error" in exc_info.value.message

    def test_handles_agent_mode_error(self) -> None:
        """Test AgentModeError is converted to ClickException."""
        handle_cli_errors = self._make_handler()

        @handle_cli_errors
        def func() -> None:
            raise AgentModeError("Agent not set up")

        with pytest.raises(ClickException) as exc_info:
            func()
        assert "Agent mode error" in exc_info.value.message

    def test_handles_configuration_error(self) -> None:
        """Test ConfigurationError is converted to ClickException."""
        handle_cli_errors = self._make_handler()

        @handle_cli_errors
        def func() -> None:
            raise ConfigurationError("Missing config")

        with pytest.raises(ClickException) as exc_info:
            func()
        assert "Configuration error" in exc_info.value.message

    def test_handles_delivery_timeout_error(self) -> None:
        """Test DeliveryTimeoutError is converted to ClickException."""
        handle_cli_errors = self._make_handler()

        @handle_cli_errors
        def func() -> None:
            raise DeliveryTimeoutError("Timeout after 900s")

        with pytest.raises(ClickException) as exc_info:
            func()
        assert "Timeout" in exc_info.value.message

    @patch("mech_client.utils.errors.handlers.EnvironmentConfig.load")
    def test_handles_http_error(self, mock_env_load: MagicMock) -> None:
        """Test requests.HTTPError is converted to ClickException."""
        mock_env_load.return_value.mechx_chain_rpc = "https://rpc.example.com"
        handle_cli_errors = self._make_handler()

        @handle_cli_errors
        def func() -> None:
            raise requests.exceptions.HTTPError("HTTP 503")

        with pytest.raises(ClickException) as exc_info:
            func()
        assert "RPC" in exc_info.value.message

    @patch("mech_client.utils.errors.handlers.EnvironmentConfig.load")
    def test_handles_connection_error(self, mock_env_load: MagicMock) -> None:
        """Test requests.ConnectionError is converted to ClickException."""
        mock_env_load.return_value.mechx_chain_rpc = "https://rpc.example.com"
        handle_cli_errors = self._make_handler()

        @handle_cli_errors
        def func() -> None:
            raise requests.exceptions.ConnectionError("Connection refused")

        with pytest.raises(ClickException) as exc_info:
            func()
        assert "Network error" in exc_info.value.message

    @patch("mech_client.utils.errors.handlers.EnvironmentConfig.load")
    def test_handles_timeout_error(self, mock_env_load: MagicMock) -> None:
        """Test TimeoutError is converted to ClickException."""
        mock_env_load.return_value.mechx_chain_rpc = "https://rpc.example.com"
        handle_cli_errors = self._make_handler()

        @handle_cli_errors
        def func() -> None:
            raise TimeoutError("Timed out waiting for receipt")

        with pytest.raises(ClickException) as exc_info:
            func()
        assert "Timeout" in exc_info.value.message

    def test_handles_contract_logic_error(self) -> None:
        """Test web3 ContractLogicError is converted to ClickException."""
        handle_cli_errors = self._make_handler()

        @handle_cli_errors
        def func() -> None:
            raise ContractLogicError("execution reverted: not enough balance")

        with pytest.raises(ClickException) as exc_info:
            func()
        assert "contract" in exc_info.value.message.lower()

    def test_handles_web3_validation_error(self) -> None:
        """Test web3 Web3ValidationError is converted to ClickException."""
        handle_cli_errors = self._make_handler()

        @handle_cli_errors
        def func() -> None:
            raise Web3ValidationError("invalid address")

        with pytest.raises(ClickException) as exc_info:
            func()
        assert "validation" in exc_info.value.message.lower()

    def test_handles_value_error(self) -> None:
        """Test ValueError is converted to ClickException."""
        handle_cli_errors = self._make_handler()

        @handle_cli_errors
        def func() -> None:
            raise ValueError("bad value")

        with pytest.raises(ClickException) as exc_info:
            func()
        assert "bad value" in exc_info.value.message

    def test_handles_file_not_found_error(self) -> None:
        """Test FileNotFoundError is converted to ClickException."""
        handle_cli_errors = self._make_handler()

        @handle_cli_errors
        def func() -> None:
            raise FileNotFoundError("key file missing")

        with pytest.raises(ClickException) as exc_info:
            func()
        assert "key file missing" in exc_info.value.message

    def test_handles_unexpected_exception(self) -> None:
        """Test unexpected exceptions are caught as a catch-all."""
        handle_cli_errors = self._make_handler()

        @handle_cli_errors
        def func() -> None:
            raise RuntimeError("something went wrong")

        with pytest.raises(ClickException) as exc_info:
            func()
        assert "Unexpected error" in exc_info.value.message


class TestHandleRpcErrors:
    """Tests for handle_rpc_errors decorator."""

    def _make_handler(self) -> None:
        """Import handler inside test to avoid circular import issues at module level."""
        from mech_client.utils.errors.handlers import (  # pylint: disable=import-outside-toplevel
            handle_rpc_errors,
        )

        return handle_rpc_errors

    def test_returns_value_on_success(self) -> None:
        """Test normal return values pass through."""
        handle_rpc_errors = self._make_handler()

        @handle_rpc_errors
        def func() -> int:
            return 42

        assert func() == 42

    @patch("mech_client.utils.errors.handlers.EnvironmentConfig.load")
    def test_handles_http_error(self, mock_env_load: MagicMock) -> None:
        """Test HTTP errors become RpcError."""
        mock_env_load.return_value.mechx_chain_rpc = "https://rpc.example.com"
        handle_rpc_errors = self._make_handler()

        @handle_rpc_errors
        def func() -> None:
            raise requests.exceptions.HTTPError("503 Service Unavailable")

        with pytest.raises(RpcError) as exc_info:
            func()
        assert "HTTP error" in str(exc_info.value)
        assert exc_info.value.rpc_url == "https://rpc.example.com"

    @patch("mech_client.utils.errors.handlers.EnvironmentConfig.load")
    def test_handles_connection_error(self, mock_env_load: MagicMock) -> None:
        """Test connection errors become RpcError."""
        mock_env_load.return_value.mechx_chain_rpc = None
        handle_rpc_errors = self._make_handler()

        @handle_rpc_errors
        def func() -> None:
            raise requests.exceptions.ConnectionError("Connection refused")

        with pytest.raises(RpcError) as exc_info:
            func()
        assert "Network error" in str(exc_info.value)
        assert exc_info.value.rpc_url == "default"

    @patch("mech_client.utils.errors.handlers.EnvironmentConfig.load")
    def test_handles_requests_timeout(self, mock_env_load: MagicMock) -> None:
        """Test requests.Timeout becomes RpcError."""
        mock_env_load.return_value.mechx_chain_rpc = None
        handle_rpc_errors = self._make_handler()

        @handle_rpc_errors
        def func() -> None:
            raise requests.exceptions.Timeout("read timeout")

        with pytest.raises(RpcError):
            func()

    @patch("mech_client.utils.errors.handlers.EnvironmentConfig.load")
    def test_handles_timeout_error(self, mock_env_load: MagicMock) -> None:
        """Test TimeoutError becomes RpcError."""
        mock_env_load.return_value.mechx_chain_rpc = "https://rpc.example.com"
        handle_rpc_errors = self._make_handler()

        @handle_rpc_errors
        def func() -> None:
            raise TimeoutError("timed out")

        with pytest.raises(RpcError) as exc_info:
            func()
        assert "Timeout" in str(exc_info.value)
        assert exc_info.value.rpc_url == "https://rpc.example.com"


class TestHandleContractErrors:
    """Tests for handle_contract_errors decorator."""

    def _make_handler(self) -> None:
        """Import handler inside test to avoid circular import issues at module level."""
        from mech_client.utils.errors.handlers import (  # pylint: disable=import-outside-toplevel
            handle_contract_errors,
        )

        return handle_contract_errors

    def test_returns_value_on_success(self) -> None:
        """Test normal return values pass through."""
        handle_contract_errors = self._make_handler()

        @handle_contract_errors
        def func() -> str:
            return "tx_hash"

        assert func() == "tx_hash"

    def test_handles_contract_logic_error(self) -> None:
        """Test ContractLogicError becomes ContractError."""
        handle_contract_errors = self._make_handler()

        @handle_contract_errors
        def func() -> None:
            raise ContractLogicError("execution reverted")

        with pytest.raises(ContractError) as exc_info:
            func()
        assert "Contract logic error" in str(exc_info.value)

    def test_handles_web3_validation_error(self) -> None:
        """Test Web3ValidationError becomes ContractError."""
        handle_contract_errors = self._make_handler()

        @handle_contract_errors
        def func() -> None:
            raise Web3ValidationError("invalid checksum address")

        with pytest.raises(ContractError) as exc_info:
            func()
        assert "Contract validation error" in str(exc_info.value)


class TestHandleSubgraphErrors:
    """Tests for handle_subgraph_errors decorator."""

    def _make_handler(self) -> None:
        """Import handler inside test to avoid circular import issues at module level."""
        from mech_client.utils.errors.handlers import (  # pylint: disable=import-outside-toplevel
            handle_subgraph_errors,
        )

        return handle_subgraph_errors

    def test_returns_value_on_success(self) -> None:
        """Test normal return values pass through."""
        handle_subgraph_errors = self._make_handler()

        @handle_subgraph_errors
        def func() -> dict:
            return {"data": []}

        assert func() == {"data": []}

    @patch("mech_client.utils.errors.handlers.EnvironmentConfig.load")
    def test_handles_http_error(self, mock_env_load: MagicMock) -> None:
        """Test HTTP errors become SubgraphError."""
        mock_env_load.return_value.mechx_subgraph_url = "https://subgraph.example.com"
        handle_subgraph_errors = self._make_handler()

        @handle_subgraph_errors
        def func() -> None:
            raise requests.exceptions.HTTPError("503")

        with pytest.raises(SubgraphError) as exc_info:
            func()
        assert "HTTP error" in str(exc_info.value)
        assert exc_info.value.subgraph_url == "https://subgraph.example.com"

    @patch("mech_client.utils.errors.handlers.EnvironmentConfig.load")
    def test_handles_connection_error(self, mock_env_load: MagicMock) -> None:
        """Test connection errors become SubgraphError."""
        mock_env_load.return_value.mechx_subgraph_url = None
        handle_subgraph_errors = self._make_handler()

        @handle_subgraph_errors
        def func() -> None:
            raise requests.exceptions.ConnectionError("refused")

        with pytest.raises(SubgraphError) as exc_info:
            func()
        assert "Network error" in str(exc_info.value)
        assert exc_info.value.subgraph_url == "not set"
