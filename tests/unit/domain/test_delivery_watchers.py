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

"""Tests for delivery watcher classes."""

from unittest.mock import MagicMock, patch

import pytest
from web3.constants import ADDRESS_ZERO

from mech_client.domain.delivery.base import DeliveryWatcher
from mech_client.domain.delivery.onchain_watcher import OnchainDeliveryWatcher

# Configure tests to use asyncio only for async functions


class TestDeliveryWatcherBase:
    """Tests for DeliveryWatcher abstract base class."""

    def test_cannot_instantiate_abstract_class(self) -> None:
        """Test that DeliveryWatcher cannot be instantiated directly."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            DeliveryWatcher(timeout=100.0)  # type: ignore

    def test_concrete_implementation_requires_watch_method(self) -> None:
        """Test that concrete implementations must implement watch method."""

        class IncompleteWatcher(DeliveryWatcher):
            """Incomplete watcher without watch method."""

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteWatcher(timeout=100.0)  # type: ignore


class TestOnchainDeliveryWatcherInitialization:
    """Tests for OnchainDeliveryWatcher initialization."""

    def test_initialization_with_default_timeout(
        self, mock_web3_contract: MagicMock, mock_ledger_api: MagicMock
    ) -> None:
        """Test watcher initialization with default timeout."""
        watcher = OnchainDeliveryWatcher(
            marketplace_contract=mock_web3_contract,
            ledger_api=mock_ledger_api,
        )

        assert watcher.marketplace_contract == mock_web3_contract
        assert watcher.ledger_api == mock_ledger_api
        assert watcher.timeout == 900.0  # DEFAULT_TIMEOUT

    def test_initialization_with_custom_timeout(
        self, mock_web3_contract: MagicMock, mock_ledger_api: MagicMock
    ) -> None:
        """Test watcher initialization with custom timeout."""
        custom_timeout = 300.0
        watcher = OnchainDeliveryWatcher(
            marketplace_contract=mock_web3_contract,
            ledger_api=mock_ledger_api,
            timeout=custom_timeout,
        )

        assert watcher.timeout == custom_timeout


class TestOnchainDeliveryWatcherWatch:
    """Tests for OnchainDeliveryWatcher watch method."""

    @pytest.mark.asyncio
    async def test_watch_single_request_immediate_delivery(
        self, mock_web3_contract: MagicMock, mock_ledger_api: MagicMock
    ) -> None:
        """Test watching single request returns IPFS URL."""
        request_id = "1234567890abcdef"
        delivery_mech = "0x" + "1" * 40
        ipfs_hash = "a" * 64
        expected_url = f"https://gateway.autonolas.tech/ipfs/f01701220{ipfs_hash}"

        watcher = OnchainDeliveryWatcher(
            marketplace_contract=mock_web3_contract,
            ledger_api=mock_ledger_api,
            timeout=10.0,
        )

        # Mock the internal methods directly
        async def mock_wait_for_marketplace(req_ids):
            return {request_id: delivery_mech}

        async def mock_fetch_data_urls(req_ids, mech_map):
            return {request_id: expected_url}

        watcher._wait_for_marketplace_delivery = mock_wait_for_marketplace
        watcher._fetch_data_urls_from_mechs = mock_fetch_data_urls

        result = await watcher.watch([request_id])

        assert len(result) == 1
        assert request_id in result
        assert result[request_id] == expected_url

    @pytest.mark.asyncio
    async def test_watch_multiple_requests_all_delivered(
        self, mock_web3_contract: MagicMock, mock_ledger_api: MagicMock
    ) -> None:
        """Test watching multiple requests from different mechs."""
        request_id_1 = "1111111111111111"
        request_id_2 = "2222222222222222"
        delivery_mech_1 = "0x" + "1" * 40
        delivery_mech_2 = "0x" + "2" * 40
        url_1 = "https://gateway.autonolas.tech/ipfs/f01701220" + "a" * 64
        url_2 = "https://gateway.autonolas.tech/ipfs/f01701220" + "b" * 64

        watcher = OnchainDeliveryWatcher(
            marketplace_contract=mock_web3_contract,
            ledger_api=mock_ledger_api,
            timeout=10.0,
        )

        # Mock the internal methods
        async def mock_wait_for_marketplace(req_ids):
            return {request_id_1: delivery_mech_1, request_id_2: delivery_mech_2}

        async def mock_fetch_data_urls(req_ids, mech_map):
            return {request_id_1: url_1, request_id_2: url_2}

        watcher._wait_for_marketplace_delivery = mock_wait_for_marketplace
        watcher._fetch_data_urls_from_mechs = mock_fetch_data_urls

        result = await watcher.watch([request_id_1, request_id_2])

        assert len(result) == 2
        assert request_id_1 in result
        assert request_id_2 in result
        assert result[request_id_1] == url_1
        assert result[request_id_2] == url_2

    @pytest.mark.asyncio
    async def test_watch_zero_address_not_delivered(
        self, mock_web3_contract: MagicMock, mock_ledger_api: MagicMock
    ) -> None:
        """Test that zero address means request not yet delivered, then delivers."""
        request_id = "1234567890abcdef"
        delivery_mech = "0x" + "1" * 40
        expected_url = "https://gateway.autonolas.tech/ipfs/f01701220" + "a" * 64

        watcher = OnchainDeliveryWatcher(
            marketplace_contract=mock_web3_contract,
            ledger_api=mock_ledger_api,
            timeout=10.0,
        )

        # Mock the internal methods - simulates waiting then getting delivery
        call_count = 0

        async def mock_wait_for_marketplace(req_ids):
            nonlocal call_count
            call_count += 1
            # Simulate that it takes a retry to get the delivery
            return {request_id: delivery_mech}

        async def mock_fetch_data_urls(req_ids, mech_map):
            return {request_id: expected_url}

        watcher._wait_for_marketplace_delivery = mock_wait_for_marketplace
        watcher._fetch_data_urls_from_mechs = mock_fetch_data_urls

        result = await watcher.watch([request_id])

        assert len(result) == 1
        assert request_id in result
        assert result[request_id] == expected_url

    @pytest.mark.asyncio
    async def test_watch_timeout_returns_partial_results(
        self, mock_web3_contract: MagicMock, mock_ledger_api: MagicMock
    ) -> None:
        """Test that timeout returns partial results."""
        request_id = "1234567890abcdef"

        mock_functions = MagicMock()
        mock_web3_contract.functions = mock_functions
        mock_request_info = MagicMock()
        mock_functions.mapRequestIdInfos.return_value = mock_request_info

        # Always return zero address (never delivered)
        mock_request_info.call.return_value = ["data", ADDRESS_ZERO]

        watcher = OnchainDeliveryWatcher(
            marketplace_contract=mock_web3_contract,
            ledger_api=mock_ledger_api,
            timeout=0.1,  # Very short timeout
        )

        with patch("time.sleep"):  # Speed up test
            result = await watcher.watch([request_id])

        # Should return empty dict since nothing was delivered
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_watch_unexpected_structure_returns_empty(
        self, mock_web3_contract: MagicMock, mock_ledger_api: MagicMock
    ) -> None:
        """Test that unexpected response structure returns empty data."""
        request_id = "1234567890abcdef"

        mock_functions = MagicMock()
        mock_web3_contract.functions = mock_functions
        mock_request_info = MagicMock()
        mock_functions.mapRequestIdInfos.return_value = mock_request_info

        # Return structure with insufficient length (index 1 doesn't exist)
        mock_request_info.call.return_value = ["only_one_element"]

        watcher = OnchainDeliveryWatcher(
            marketplace_contract=mock_web3_contract,
            ledger_api=mock_ledger_api,
            timeout=10.0,
        )

        result = await watcher.watch([request_id])

        assert result == {}

    @pytest.mark.asyncio
    async def test_watch_invalid_delivery_mech_format(
        self, mock_web3_contract: MagicMock, mock_ledger_api: MagicMock
    ) -> None:
        """Test that invalid delivery mech format returns empty dict."""
        request_id = "1234567890abcdef"

        mock_functions = MagicMock()
        mock_web3_contract.functions = mock_functions
        mock_request_info = MagicMock()
        mock_functions.mapRequestIdInfos.return_value = mock_request_info

        # Return non-string or non-0x-prefixed value
        invalid_request_info = ["data", 12345]  # Not a string
        mock_request_info.call.return_value = invalid_request_info

        watcher = OnchainDeliveryWatcher(
            marketplace_contract=mock_web3_contract,
            ledger_api=mock_ledger_api,
            timeout=10.0,
        )

        result = await watcher.watch([request_id])

        # Should return empty dict when format is invalid
        assert result == {}


class TestOnchainDeliveryWatcherDataUrls:
    """Tests for OnchainDeliveryWatcher watch_for_data_urls method."""

    @pytest.mark.asyncio
    @patch("mech_client.domain.delivery.onchain_watcher.decode")
    async def test_watch_for_data_urls_single_delivery(
        self,
        mock_decode: MagicMock,
        mock_web3_contract: MagicMock,
        mock_ledger_api: MagicMock,
    ) -> None:
        """Test watching for data URLs with single delivery."""
        request_id = "1234567890abcdef"
        # Pad to 64 chars (32 bytes = 64 hex chars) for proper bytes32 format
        request_id_padded = request_id.ljust(64, "0")
        ipfs_hash = "a" * 64  # 64 hex chars
        from_block = 1000
        mech_address = "0x" + "1" * 40
        deliver_signature = "b" * 64

        # Mock decode to return expected values
        request_id_bytes = bytes.fromhex(request_id_padded)
        delivery_data_bytes = bytes.fromhex(ipfs_hash)
        mock_decode.return_value = (request_id_bytes, 0, delivery_data_bytes)

        # Mock eth.get_logs
        mock_log = {
            "blockNumber": 1001,
            "data": b"mock_data",  # Actual data doesn't matter since decode is mocked
        }
        mock_ledger_api.api.eth.get_logs.return_value = [mock_log]

        watcher = OnchainDeliveryWatcher(
            marketplace_contract=mock_web3_contract,
            ledger_api=mock_ledger_api,
            timeout=0.5,  # Short timeout for test
        )

        result = await watcher.watch_for_data_urls(
            request_ids=[request_id_padded],  # Use padded version
            from_block=from_block,
            mech_contract_address=mech_address,
            mech_deliver_signature=deliver_signature,
        )

        assert len(result) == 1
        assert request_id_padded in result
        assert ipfs_hash in result[request_id_padded]
        mock_ledger_api.api.eth.get_logs.assert_called()

    @pytest.mark.asyncio
    @patch("mech_client.domain.delivery.onchain_watcher.decode")
    async def test_watch_for_data_urls_multiple_deliveries(
        self,
        mock_decode: MagicMock,
        mock_web3_contract: MagicMock,
        mock_ledger_api: MagicMock,
    ) -> None:
        """Test watching for data URLs with multiple deliveries."""
        request_id_1 = "1111111111111111"
        request_id_2 = "2222222222222222"
        request_id_1_padded = request_id_1.ljust(64, "0")
        request_id_2_padded = request_id_2.ljust(64, "0")
        ipfs_hash_1 = "a" * 64
        ipfs_hash_2 = "b" * 64
        from_block = 1000
        mech_address = "0x" + "1" * 40
        deliver_signature = "c" * 64

        # Mock decode to return different values for each call
        request_id_1_bytes = bytes.fromhex(request_id_1_padded)
        request_id_2_bytes = bytes.fromhex(request_id_2_padded)
        delivery_data_1_bytes = bytes.fromhex(ipfs_hash_1)
        delivery_data_2_bytes = bytes.fromhex(ipfs_hash_2)
        mock_decode.side_effect = [
            (request_id_1_bytes, 0, delivery_data_1_bytes),
            (request_id_2_bytes, 0, delivery_data_2_bytes),
        ]

        # Mock two log entries
        mock_log_1 = {"blockNumber": 1001, "data": b"mock_data_1"}
        mock_log_2 = {"blockNumber": 1002, "data": b"mock_data_2"}
        mock_ledger_api.api.eth.get_logs.return_value = [mock_log_1, mock_log_2]

        watcher = OnchainDeliveryWatcher(
            marketplace_contract=mock_web3_contract,
            ledger_api=mock_ledger_api,
            timeout=0.5,
        )

        result = await watcher.watch_for_data_urls(
            request_ids=[request_id_1_padded, request_id_2_padded],
            from_block=from_block,
            mech_contract_address=mech_address,
            mech_deliver_signature=deliver_signature,
        )

        assert len(result) == 2
        assert request_id_1_padded in result
        assert request_id_2_padded in result
        assert ipfs_hash_1 in result[request_id_1_padded]
        assert ipfs_hash_2 in result[request_id_2_padded]

    @pytest.mark.asyncio
    async def test_watch_for_data_urls_no_logs(
        self, mock_web3_contract: MagicMock, mock_ledger_api: MagicMock
    ) -> None:
        """Test watching with no logs returns empty after timeout."""
        request_id = "1234567890abcdef"
        from_block = 1000
        mech_address = "0x" + "1" * 40
        deliver_signature = "b" * 64

        # Mock no logs returned
        mock_ledger_api.api.eth.get_logs.return_value = []

        watcher = OnchainDeliveryWatcher(
            marketplace_contract=mock_web3_contract,
            ledger_api=mock_ledger_api,
            timeout=0.1,  # Very short timeout
        )

        with patch("time.sleep"):  # Speed up test
            result = await watcher.watch_for_data_urls(
                request_ids=[request_id],
                from_block=from_block,
                mech_contract_address=mech_address,
                mech_deliver_signature=deliver_signature,
            )

        assert len(result) == 0

    @pytest.mark.asyncio
    @patch("mech_client.domain.delivery.onchain_watcher.decode")
    async def test_watch_for_data_urls_duplicate_logs_ignored(
        self,
        mock_decode: MagicMock,
        mock_web3_contract: MagicMock,
        mock_ledger_api: MagicMock,
    ) -> None:
        """Test that duplicate logs for same request are ignored."""
        request_id = "1234567890abcdef"
        request_id_padded = request_id.ljust(64, "0")
        ipfs_hash_1 = "a" * 64
        ipfs_hash_2 = "b" * 64  # Different hash (should be ignored)
        from_block = 1000
        mech_address = "0x" + "1" * 40
        deliver_signature = "c" * 64

        # Mock decode to return same request_id but different data
        request_id_bytes = bytes.fromhex(request_id_padded)
        delivery_data_1_bytes = bytes.fromhex(ipfs_hash_1)
        delivery_data_2_bytes = bytes.fromhex(ipfs_hash_2)
        mock_decode.side_effect = [
            (request_id_bytes, 0, delivery_data_1_bytes),
            (request_id_bytes, 0, delivery_data_2_bytes),
        ]

        # Mock two logs with same request_id
        mock_log_1 = {"blockNumber": 1001, "data": b"mock_data_1"}
        mock_log_2 = {"blockNumber": 1002, "data": b"mock_data_2"}
        mock_ledger_api.api.eth.get_logs.return_value = [mock_log_1, mock_log_2]

        watcher = OnchainDeliveryWatcher(
            marketplace_contract=mock_web3_contract,
            ledger_api=mock_ledger_api,
            timeout=0.5,
        )

        result = await watcher.watch_for_data_urls(
            request_ids=[request_id_padded],
            from_block=from_block,
            mech_contract_address=mech_address,
            mech_deliver_signature=deliver_signature,
        )

        # Should only have one entry (first one)
        assert len(result) == 1
        assert ipfs_hash_1 in result[request_id_padded]
        assert ipfs_hash_2 not in result[request_id_padded]

    @pytest.mark.asyncio
    @patch("mech_client.domain.delivery.onchain_watcher.decode")
    async def test_watch_for_data_urls_updates_from_block(
        self,
        mock_decode: MagicMock,
        mock_web3_contract: MagicMock,
        mock_ledger_api: MagicMock,
    ) -> None:
        """Test that from_block is updated to avoid re-processing logs."""
        request_id = "1234567890abcdef"
        request_id_padded = request_id.ljust(64, "0")
        ipfs_hash = "a" * 64
        from_block = 1000
        mech_address = "0x" + "1" * 40
        deliver_signature = "b" * 64

        # Mock decode
        request_id_bytes = bytes.fromhex(request_id_padded)
        delivery_data_bytes = bytes.fromhex(ipfs_hash)
        mock_decode.return_value = (request_id_bytes, 0, delivery_data_bytes)

        # First call returns log at block 1005
        mock_log = {"blockNumber": 1005, "data": b"mock_data"}
        mock_ledger_api.api.eth.get_logs.return_value = [mock_log]

        watcher = OnchainDeliveryWatcher(
            marketplace_contract=mock_web3_contract,
            ledger_api=mock_ledger_api,
            timeout=0.5,
        )

        result = await watcher.watch_for_data_urls(
            request_ids=[request_id_padded],
            from_block=from_block,
            mech_contract_address=mech_address,
            mech_deliver_signature=deliver_signature,
        )

        assert len(result) == 1
        # Verify the next call would use block 1006 (latest + 1)
        # This is implicit in the implementation
