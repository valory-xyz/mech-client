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

"""Tests for transaction receipt waiting utilities."""

from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from mech_client.infrastructure.blockchain.receipt_waiter import (
    wait_for_receipt,
    watch_for_marketplace_request_ids,
)


class TestWaitForReceipt:
    """Tests for wait_for_receipt function."""

    def test_successful_receipt_immediate(
        self, mock_ledger_api: MagicMock
    ) -> None:
        """Test getting receipt immediately on first try."""
        tx_hash = "0x1234567890abcdef"
        expected_receipt = {"transactionHash": tx_hash, "status": 1}

        mock_ledger_api._api.eth.get_transaction_receipt.return_value = (
            expected_receipt
        )

        result = wait_for_receipt(tx_hash, mock_ledger_api)

        assert result == expected_receipt
        mock_ledger_api._api.eth.get_transaction_receipt.assert_called_once_with(
            tx_hash
        )

    def test_successful_receipt_after_retries(
        self, mock_ledger_api: MagicMock
    ) -> None:
        """Test getting receipt after multiple retries."""
        tx_hash = "0x1234567890abcdef"
        expected_receipt = {"transactionHash": tx_hash, "status": 1}

        # First two calls raise exception, third succeeds
        mock_ledger_api._api.eth.get_transaction_receipt.side_effect = [
            Exception("Receipt not found"),
            Exception("Receipt not found"),
            expected_receipt,
        ]

        result = wait_for_receipt(tx_hash, mock_ledger_api, timeout=5.0)

        assert result == expected_receipt
        assert mock_ledger_api._api.eth.get_transaction_receipt.call_count == 3

    def test_timeout_exceeded(self, mock_ledger_api: MagicMock) -> None:
        """Test that timeout raises TimeoutError with detailed message."""
        tx_hash = "0x1234567890abcdef"

        # Mock provider endpoint for error message
        mock_provider = MagicMock()
        type(mock_provider).endpoint_uri = PropertyMock(
            return_value="https://rpc.example.com"
        )
        mock_ledger_api._api.provider = mock_provider

        # Always raise exception
        mock_ledger_api._api.eth.get_transaction_receipt.side_effect = Exception(
            "Receipt not found"
        )

        with pytest.raises(TimeoutError) as exc_info:
            wait_for_receipt(tx_hash, mock_ledger_api, timeout=2.0)

        error_msg = str(exc_info.value)
        assert "Timeout (2.0s) exceeded" in error_msg
        assert tx_hash in error_msg
        assert "https://rpc.example.com" in error_msg
        assert "Retries attempted:" in error_msg

    def test_timeout_without_endpoint_uri(
        self, mock_ledger_api: MagicMock
    ) -> None:
        """Test timeout error when provider has no endpoint_uri attribute."""
        tx_hash = "0x1234567890abcdef"

        # Mock provider without endpoint_uri attribute
        mock_provider = MagicMock(spec=[])
        mock_ledger_api._api.provider = mock_provider

        mock_ledger_api._api.eth.get_transaction_receipt.side_effect = Exception(
            "Receipt not found"
        )

        with pytest.raises(TimeoutError) as exc_info:
            wait_for_receipt(tx_hash, mock_ledger_api, timeout=1.0)

        error_msg = str(exc_info.value)
        assert "RPC endpoint: unknown" in error_msg


class TestWatchForMarketplaceRequestIds:
    """Tests for watch_for_marketplace_request_ids function."""

    def test_extract_single_request_id(
        self, mock_ledger_api: MagicMock, mock_web3_contract: MagicMock
    ) -> None:
        """Test extracting single request ID from transaction logs."""
        tx_hash = "0x1234567890abcdef"
        request_id_bytes = b"\x00\x01\x02\x03"

        # Mock receipt
        tx_receipt = {"transactionHash": tx_hash, "status": 1}
        mock_ledger_api._api.eth.get_transaction_receipt.return_value = (
            tx_receipt
        )

        # Mock event logs
        mock_event = MagicMock()
        mock_web3_contract.events.MarketplaceRequest.return_value = mock_event
        mock_event.process_receipt.return_value = [
            {"args": {"requestIds": [request_id_bytes]}}
        ]

        result = watch_for_marketplace_request_ids(
            mock_web3_contract, mock_ledger_api, tx_hash
        )

        assert len(result) == 1
        assert result[0] == request_id_bytes.hex()
        mock_event.process_receipt.assert_called_once_with(tx_receipt)

    def test_extract_multiple_request_ids(
        self, mock_ledger_api: MagicMock, mock_web3_contract: MagicMock
    ) -> None:
        """Test extracting multiple request IDs from batch transaction."""
        tx_hash = "0x1234567890abcdef"
        request_id_1 = b"\x00\x01\x02\x03"
        request_id_2 = b"\x04\x05\x06\x07"
        request_id_3 = b"\x08\x09\x0a\x0b"

        # Mock receipt
        tx_receipt = {"transactionHash": tx_hash, "status": 1}
        mock_ledger_api._api.eth.get_transaction_receipt.return_value = (
            tx_receipt
        )

        # Mock event logs
        mock_event = MagicMock()
        mock_web3_contract.events.MarketplaceRequest.return_value = mock_event
        mock_event.process_receipt.return_value = [
            {
                "args": {
                    "requestIds": [request_id_1, request_id_2, request_id_3]
                }
            }
        ]

        result = watch_for_marketplace_request_ids(
            mock_web3_contract, mock_ledger_api, tx_hash
        )

        assert len(result) == 3
        assert result[0] == request_id_1.hex()
        assert result[1] == request_id_2.hex()
        assert result[2] == request_id_3.hex()

    def test_empty_logs_returns_placeholder(
        self, mock_ledger_api: MagicMock, mock_web3_contract: MagicMock
    ) -> None:
        """Test that empty logs return 'Empty Logs' placeholder."""
        tx_hash = "0x1234567890abcdef"

        # Mock receipt
        tx_receipt = {"transactionHash": tx_hash, "status": 1}
        mock_ledger_api._api.eth.get_transaction_receipt.return_value = (
            tx_receipt
        )

        # Mock empty event logs
        mock_event = MagicMock()
        mock_web3_contract.events.MarketplaceRequest.return_value = mock_event
        mock_event.process_receipt.return_value = []

        result = watch_for_marketplace_request_ids(
            mock_web3_contract, mock_ledger_api, tx_hash
        )

        assert result == ["Empty Logs"]

    @patch(
        "mech_client.infrastructure.blockchain.receipt_waiter.wait_for_receipt"
    )
    def test_timeout_while_waiting_for_receipt(
        self,
        mock_wait_for_receipt: MagicMock,
        mock_ledger_api: MagicMock,
        mock_web3_contract: MagicMock,
    ) -> None:
        """Test that timeout during receipt wait propagates correctly."""
        tx_hash = "0x1234567890abcdef"

        # Mock wait_for_receipt to raise TimeoutError
        mock_wait_for_receipt.side_effect = TimeoutError(
            f"Timeout exceeded while waiting for transaction receipt. "
            f"Transaction hash: {tx_hash}."
        )

        with pytest.raises(TimeoutError) as exc_info:
            watch_for_marketplace_request_ids(
                mock_web3_contract, mock_ledger_api, tx_hash
            )

        error_msg = str(exc_info.value)
        assert "Timeout" in error_msg
        assert tx_hash in error_msg
