# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2026 Valory AG
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

"""Tests for infrastructure.ipfs.result_file."""

from unittest.mock import MagicMock, patch

import requests

from mech_client.infrastructure.ipfs.result_file import (
    RESULT_FILE_TIMEOUT,
    build_result_file_url,
    fetch_result_file,
)


class TestBuildResultFileUrl:
    """Tests for build_result_file_url."""

    def test_appends_decimal_request_id(self) -> None:
        """Test the request ID is appended to the delivery directory URL."""
        url = build_result_file_url("a" * 64, "12345")

        assert url == f"https://gateway.autonolas.tech/ipfs/f01701220{'a' * 64}/12345"

    def test_no_double_slash(self) -> None:
        """Test a trailing slash on the directory URL is not duplicated."""
        with patch(
            "mech_client.infrastructure.ipfs.result_file.IPFS_URL_TEMPLATE",
            "https://gateway.example.com/ipfs/{}/",
        ):
            url = build_result_file_url("abc", "1")

        assert url == "https://gateway.example.com/ipfs/abc/1"


class TestFetchResultFile:
    """Tests for fetch_result_file."""

    @patch("mech_client.infrastructure.ipfs.result_file.requests.get")
    def test_returns_parsed_json(self, mock_get: MagicMock) -> None:
        """Test a JSON result file is returned parsed."""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"result": '{"p_yes": 0.38}'}
        mock_get.return_value = mock_response

        data = fetch_result_file("https://gateway.example.com/ipfs/abc/1")

        assert data == {"result": '{"p_yes": 0.38}'}
        mock_get.assert_called_once_with(
            "https://gateway.example.com/ipfs/abc/1", timeout=RESULT_FILE_TIMEOUT
        )

    @patch("mech_client.infrastructure.ipfs.result_file.requests.get")
    def test_returns_text_when_not_json(self, mock_get: MagicMock) -> None:
        """Test a non-JSON result file falls back to its raw text."""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.side_effect = ValueError("not json")
        mock_response.text = "plain answer"
        mock_get.return_value = mock_response

        assert (
            fetch_result_file("https://gateway.example.com/ipfs/abc/1")
            == "plain answer"
        )

    @patch("mech_client.infrastructure.ipfs.result_file.requests.get")
    def test_returns_none_on_http_error(self, mock_get: MagicMock) -> None:
        """Test an unreachable or missing file yields None rather than raising."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "404 Not Found"
        )
        mock_get.return_value = mock_response

        assert fetch_result_file("https://gateway.example.com/ipfs/abc/1") is None

    @patch("mech_client.infrastructure.ipfs.result_file.requests.get")
    def test_returns_none_on_connection_error(self, mock_get: MagicMock) -> None:
        """Test a connection failure yields None rather than raising."""
        mock_get.side_effect = requests.exceptions.ConnectionError("refused")

        assert fetch_result_file("https://gateway.example.com/ipfs/abc/1") is None
