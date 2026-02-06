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

"""Tests for offchain delivery watcher."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import requests

from mech_client.domain.delivery.offchain_watcher import OffchainDeliveryWatcher


class TestOffchainDeliveryWatcherInitialization:
    """Tests for OffchainDeliveryWatcher initialization."""

    def test_initialization_with_trailing_slash(self) -> None:
        """Test initialization strips trailing slash from URL."""
        watcher = OffchainDeliveryWatcher(
            mech_offchain_url="https://mech.example.com/", timeout=60.0
        )

        assert watcher.mech_offchain_url == "https://mech.example.com"
        assert (
            watcher.deliver_url
            == "https://mech.example.com/fetch_offchain_info"
        )
        assert watcher.timeout == 60.0

    def test_initialization_without_trailing_slash(self) -> None:
        """Test initialization with URL without trailing slash."""
        watcher = OffchainDeliveryWatcher(
            mech_offchain_url="https://mech.example.com", timeout=30.0
        )

        assert watcher.mech_offchain_url == "https://mech.example.com"
        assert (
            watcher.deliver_url
            == "https://mech.example.com/fetch_offchain_info"
        )
        assert watcher.timeout == 30.0


class TestOffchainDeliveryWatcherWatch:
    """Tests for watch method."""

    @pytest.mark.anyio
    @patch("mech_client.domain.delivery.offchain_watcher.requests")
    async def test_watch_single_request_immediate_delivery(
        self, mock_requests: MagicMock
    ) -> None:
        """Test watching single request with immediate delivery."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": "response_data", "result": "success"}
        mock_response.raise_for_status.return_value = None
        mock_requests.get.return_value = mock_response

        # Create watcher
        watcher = OffchainDeliveryWatcher(
            mech_offchain_url="https://mech.example.com", timeout=60.0
        )

        # Watch for delivery
        request_ids = ["0x1a"]  # Hex request ID
        results = await watcher.watch(request_ids)

        # Verify
        assert len(results) == 1
        assert "0x1a" in results
        assert results["0x1a"]["data"] == "response_data"

        # Verify request was made with integer string
        mock_requests.get.assert_called_once()
        call_kwargs = mock_requests.get.call_args[1]
        assert call_kwargs["data"]["request_id"] == "26"  # hex 0x1a = 26

    @pytest.mark.anyio
    @patch("mech_client.domain.delivery.offchain_watcher.requests")
    async def test_watch_multiple_requests_all_delivered(
        self, mock_requests: MagicMock
    ) -> None:
        """Test watching multiple requests with all delivered."""
        # Setup mock responses - different data for each request
        def mock_get_response(*args, **kwargs):
            request_id = kwargs["data"]["request_id"]
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "data": f"response_for_{request_id}",
                "request_id": request_id,
            }
            mock_response.raise_for_status.return_value = None
            return mock_response

        mock_requests.get.side_effect = mock_get_response

        # Create watcher
        watcher = OffchainDeliveryWatcher(
            mech_offchain_url="https://mech.example.com", timeout=60.0
        )

        # Watch for multiple deliveries
        request_ids = ["0xa", "0x14", "0x1e"]  # 10, 20, 30 in decimal
        results = await watcher.watch(request_ids)

        # Verify all received
        assert len(results) == 3
        assert "0xa" in results
        assert "0x14" in results
        assert "0x1e" in results
        assert results["0xa"]["data"] == "response_for_10"
        assert results["0x14"]["data"] == "response_for_20"
        assert results["0x1e"]["data"] == "response_for_30"

    @pytest.mark.anyio
    @patch("mech_client.domain.delivery.offchain_watcher.asyncio.sleep")
    @patch("mech_client.domain.delivery.offchain_watcher.requests")
    async def test_watch_delayed_delivery(
        self, mock_requests: MagicMock, mock_sleep: AsyncMock
    ) -> None:
        """Test watching with delayed delivery (multiple polls)."""
        # Setup mock to return None first, then data
        call_count = 0

        def mock_get_response(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_response = MagicMock()

            # Return None on first call, data on second
            if call_count == 1:
                mock_response.json.return_value = None
            else:
                mock_response.json.return_value = {"data": "delayed_response"}

            mock_response.raise_for_status.return_value = None
            return mock_response

        mock_requests.get.side_effect = mock_get_response
        mock_sleep.return_value = None

        # Create watcher
        watcher = OffchainDeliveryWatcher(
            mech_offchain_url="https://mech.example.com", timeout=60.0
        )

        # Watch for delivery
        request_ids = ["0x1"]
        results = await watcher.watch(request_ids)

        # Verify delivery received after delay
        assert len(results) == 1
        assert results["0x1"]["data"] == "delayed_response"

        # Verify sleep was called (polling happened)
        assert mock_sleep.call_count >= 1

    @pytest.mark.anyio
    @patch("mech_client.domain.delivery.offchain_watcher.time.time")
    @patch("mech_client.domain.delivery.offchain_watcher.asyncio.sleep")
    @patch("mech_client.domain.delivery.offchain_watcher.requests")
    async def test_watch_timeout_no_responses(
        self, mock_requests: MagicMock, mock_sleep: AsyncMock, mock_time: MagicMock
    ) -> None:
        """Test watching with timeout and no responses."""
        # Setup mock time to simulate timeout
        mock_time.side_effect = [0.0, 70.0]  # Start at 0, then exceed 60s timeout

        # Setup mock to always return None
        mock_response = MagicMock()
        mock_response.json.return_value = None
        mock_response.raise_for_status.return_value = None
        mock_requests.get.return_value = mock_response
        mock_sleep.return_value = None

        # Create watcher
        watcher = OffchainDeliveryWatcher(
            mech_offchain_url="https://mech.example.com", timeout=60.0
        )

        # Watch for delivery
        request_ids = ["0x1"]
        results = await watcher.watch(request_ids)

        # Verify timeout with no results
        assert len(results) == 0

    @pytest.mark.anyio
    @patch("mech_client.domain.delivery.offchain_watcher.time.time")
    @patch("mech_client.domain.delivery.offchain_watcher.asyncio.sleep")
    @patch("mech_client.domain.delivery.offchain_watcher.requests")
    async def test_watch_timeout_partial_responses(
        self, mock_requests: MagicMock, mock_sleep: AsyncMock, mock_time: MagicMock
    ) -> None:
        """Test watching with timeout and partial responses."""
        # Setup mock time to simulate timeout after first response
        mock_time.side_effect = [0.0, 10.0, 70.0]  # Timeout on second poll

        # Setup mock to return data for first request, None for second
        def mock_get_response(*args, **kwargs):
            request_id = kwargs["data"]["request_id"]
            mock_response = MagicMock()
            if request_id == "10":
                mock_response.json.return_value = {"data": "response_1"}
            else:
                mock_response.json.return_value = None
            mock_response.raise_for_status.return_value = None
            return mock_response

        mock_requests.get.side_effect = mock_get_response
        mock_sleep.return_value = None

        # Create watcher
        watcher = OffchainDeliveryWatcher(
            mech_offchain_url="https://mech.example.com", timeout=60.0
        )

        # Watch for multiple deliveries
        request_ids = ["0xa", "0x14"]  # 10, 20 in decimal
        results = await watcher.watch(request_ids)

        # Verify partial results
        assert len(results) == 1
        assert "0xa" in results
        assert "0x14" not in results

    @pytest.mark.anyio
    @patch("mech_client.domain.delivery.offchain_watcher.requests")
    async def test_watch_http_error_retries(
        self, mock_requests: MagicMock
    ) -> None:
        """Test watching with HTTP errors continues to retry."""
        # Setup mock to fail first, then succeed
        call_count = 0

        def mock_get_response(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                # First call raises exception
                raise requests.exceptions.RequestException("Network error")
            else:
                # Second call succeeds
                mock_response = MagicMock()
                mock_response.json.return_value = {"data": "success_after_retry"}
                mock_response.raise_for_status.return_value = None
                return mock_response

        mock_requests.get.side_effect = mock_get_response

        # Create watcher
        watcher = OffchainDeliveryWatcher(
            mech_offchain_url="https://mech.example.com", timeout=60.0
        )

        # Watch for delivery
        request_ids = ["0x1"]
        results = await watcher.watch(request_ids)

        # Verify delivery received after error
        assert len(results) == 1
        assert results["0x1"]["data"] == "success_after_retry"

    @pytest.mark.anyio
    @patch("mech_client.domain.delivery.offchain_watcher.requests")
    async def test_watch_empty_response_treated_as_none(
        self, mock_requests: MagicMock
    ) -> None:
        """Test watching with empty response is treated as no data."""
        # Setup mock to return empty dict
        call_count = 0

        def mock_get_response(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_response = MagicMock()

            # Return empty dict first, then data
            if call_count == 1:
                mock_response.json.return_value = {}
            else:
                mock_response.json.return_value = {"data": "real_response"}

            mock_response.raise_for_status.return_value = None
            return mock_response

        mock_requests.get.side_effect = mock_get_response

        # Create watcher
        watcher = OffchainDeliveryWatcher(
            mech_offchain_url="https://mech.example.com", timeout=60.0
        )

        # Watch for delivery
        request_ids = ["0x1"]
        results = await watcher.watch(request_ids)

        # Verify non-empty response received
        assert len(results) == 1
        assert results["0x1"]["data"] == "real_response"

        # Verify multiple calls were made
        assert mock_requests.get.call_count >= 2


class TestOffchainDeliveryWatcherFetchData:
    """Tests for _fetch_offchain_data method."""

    @pytest.mark.anyio
    @patch("mech_client.domain.delivery.offchain_watcher.requests")
    async def test_fetch_offchain_data_success(
        self, mock_requests: MagicMock
    ) -> None:
        """Test successful data fetch."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": "test_data", "status": "delivered"}
        mock_response.raise_for_status.return_value = None
        mock_requests.get.return_value = mock_response

        # Create watcher
        watcher = OffchainDeliveryWatcher(
            mech_offchain_url="https://mech.example.com", timeout=60.0
        )

        # Fetch data
        data = await watcher._fetch_offchain_data("123")  # pylint: disable=protected-access

        # Verify
        assert data is not None
        assert data["data"] == "test_data"
        assert data["status"] == "delivered"

    @pytest.mark.anyio
    @patch("mech_client.domain.delivery.offchain_watcher.requests")
    async def test_fetch_offchain_data_empty_response(
        self, mock_requests: MagicMock
    ) -> None:
        """Test fetch with empty response returns None."""
        # Setup mock response with empty dict
        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_response.raise_for_status.return_value = None
        mock_requests.get.return_value = mock_response

        # Create watcher
        watcher = OffchainDeliveryWatcher(
            mech_offchain_url="https://mech.example.com", timeout=60.0
        )

        # Fetch data
        data = await watcher._fetch_offchain_data("123")  # pylint: disable=protected-access

        # Verify None returned
        assert data is None

    @pytest.mark.anyio
    @patch("mech_client.domain.delivery.offchain_watcher.requests.get")
    async def test_fetch_offchain_data_http_error(
        self, mock_get: MagicMock
    ) -> None:
        """Test fetch with HTTP error returns None."""
        # Setup mock response that raises on raise_for_status()
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "404 Not Found"
        )
        mock_get.return_value = mock_response

        # Create watcher
        watcher = OffchainDeliveryWatcher(
            mech_offchain_url="https://mech.example.com", timeout=60.0
        )

        # Fetch data
        data = await watcher._fetch_offchain_data("123")  # pylint: disable=protected-access

        # Verify None returned on error
        assert data is None

    @pytest.mark.anyio
    @patch("mech_client.domain.delivery.offchain_watcher.requests.get")
    async def test_fetch_offchain_data_timeout(
        self, mock_get: MagicMock
    ) -> None:
        """Test fetch with timeout returns None."""
        # Setup mock to raise timeout on get
        mock_get.side_effect = requests.exceptions.Timeout("Request timeout")

        # Create watcher
        watcher = OffchainDeliveryWatcher(
            mech_offchain_url="https://mech.example.com", timeout=60.0
        )

        # Fetch data
        data = await watcher._fetch_offchain_data("123")  # pylint: disable=protected-access

        # Verify None returned on timeout
        assert data is None

    @pytest.mark.anyio
    @patch("mech_client.domain.delivery.offchain_watcher.requests.get")
    async def test_fetch_offchain_data_connection_error(
        self, mock_get: MagicMock
    ) -> None:
        """Test fetch with connection error returns None."""
        # Setup mock to raise connection error
        mock_get.side_effect = requests.exceptions.ConnectionError(
            "Connection refused"
        )

        # Create watcher
        watcher = OffchainDeliveryWatcher(
            mech_offchain_url="https://mech.example.com", timeout=60.0
        )

        # Fetch data
        data = await watcher._fetch_offchain_data("123")  # pylint: disable=protected-access

        # Verify None returned on connection error
        assert data is None
