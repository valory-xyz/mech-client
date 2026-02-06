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

"""Tests for IPFS client."""

import json
import os
from tempfile import gettempdir
from unittest.mock import MagicMock, mock_open, patch

import pytest

from mech_client.infrastructure.ipfs.client import IPFSClient


class TestIPFSClient:
    """Tests for IPFSClient."""

    @patch("mech_client.infrastructure.ipfs.client.IPFSTool")
    def test_initialization(self, mock_ipfs_tool: MagicMock) -> None:
        """Test IPFS client initialization."""
        client = IPFSClient()

        assert client is not None
        mock_ipfs_tool.assert_called_once()

    @patch("mech_client.infrastructure.ipfs.client.IPFSTool")
    @patch("mech_client.infrastructure.ipfs.client.to_v1")
    def test_upload_file(
        self, mock_to_v1: MagicMock, mock_ipfs_tool: MagicMock
    ) -> None:
        """Test uploading file to IPFS."""
        # Setup mocks
        mock_tool_instance = MagicMock()
        mock_ipfs_tool.return_value = mock_tool_instance
        mock_tool_instance.client.add.return_value = {
            "Hash": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"
        }
        mock_to_v1.return_value = "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"

        client = IPFSClient()
        v1_hash, v1_hex = client.upload("/path/to/file.txt")

        # Verify upload was called correctly
        mock_tool_instance.client.add.assert_called_once_with(
            "/path/to/file.txt",
            pin=True,
            recursive=True,
            wrap_with_directory=False,
        )

        # Verify hash conversion
        assert isinstance(v1_hash, str)
        assert isinstance(v1_hex, str)
        assert v1_hex.startswith("f01")

    @patch("mech_client.infrastructure.ipfs.client.IPFSTool")
    def test_download_file_default_dir(self, mock_ipfs_tool: MagicMock) -> None:
        """Test downloading file to default directory."""
        mock_tool_instance = MagicMock()
        mock_ipfs_tool.return_value = mock_tool_instance

        client = IPFSClient()
        ipfs_hash = "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"
        result = client.download(ipfs_hash)

        # Verify download was called
        mock_tool_instance.client.get.assert_called_once_with(
            cid=ipfs_hash,
            target=gettempdir(),
        )

        # Verify return path
        assert result == os.path.join(gettempdir(), ipfs_hash)

    @patch("mech_client.infrastructure.ipfs.client.IPFSTool")
    def test_download_file_custom_dir(self, mock_ipfs_tool: MagicMock) -> None:
        """Test downloading file to custom directory."""
        mock_tool_instance = MagicMock()
        mock_ipfs_tool.return_value = mock_tool_instance

        client = IPFSClient()
        ipfs_hash = "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"
        custom_dir = "/custom/path"
        result = client.download(ipfs_hash, target_dir=custom_dir)

        # Verify download was called with custom dir
        mock_tool_instance.client.get.assert_called_once_with(
            cid=ipfs_hash,
            target=custom_dir,
        )

        assert result == os.path.join(custom_dir, ipfs_hash)

    @patch("mech_client.infrastructure.ipfs.client.IPFSTool")
    @patch("builtins.open", new_callable=mock_open, read_data='{"result": {"key": "value"}}')
    def test_get_json_success(
        self, mock_file: mock_open, mock_ipfs_tool: MagicMock
    ) -> None:
        """Test getting JSON data from IPFS."""
        mock_tool_instance = MagicMock()
        mock_ipfs_tool.return_value = mock_tool_instance

        client = IPFSClient()
        ipfs_hash = "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"
        request_id = "12345"

        result = client.get_json(ipfs_hash, request_id)

        # Verify download was called
        mock_tool_instance.client.get.assert_called_once()

        # Verify result
        assert result == {"key": "value"}

    @patch("mech_client.infrastructure.ipfs.client.IPFSTool")
    @patch("builtins.open", new_callable=mock_open, read_data='{"result": "not a dict"}')
    def test_get_json_invalid_format(
        self, mock_file: mock_open, mock_ipfs_tool: MagicMock
    ) -> None:
        """Test get_json raises error for invalid data format."""
        mock_tool_instance = MagicMock()
        mock_ipfs_tool.return_value = mock_tool_instance

        client = IPFSClient()
        ipfs_hash = "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"
        request_id = "12345"

        with pytest.raises(ValueError, match="do not have the expected format"):
            client.get_json(ipfs_hash, request_id)


class TestIPFSLegacyFunctions:
    """Tests for legacy IPFS functions."""

    @patch("mech_client.infrastructure.ipfs.client.IPFSClient")
    def test_push_to_ipfs(self, mock_client: MagicMock) -> None:
        """Test legacy push_to_ipfs function."""
        from mech_client.infrastructure.ipfs.client import push_to_ipfs

        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        mock_instance.upload.return_value = ("v1_hash", "v1_hex")

        v1_hash, v1_hex = push_to_ipfs("/path/to/file.txt")

        mock_instance.upload.assert_called_once_with("/path/to/file.txt")
        assert v1_hash == "v1_hash"
        assert v1_hex == "v1_hex"

    @patch("mech_client.infrastructure.ipfs.client.IPFSClient")
    def test_get_from_ipfs(self, mock_client: MagicMock) -> None:
        """Test legacy get_from_ipfs function."""
        from mech_client.infrastructure.ipfs.client import get_from_ipfs

        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        mock_instance.get_json.return_value = {"key": "value"}

        result = get_from_ipfs("ipfs_hash", "request_id")

        mock_instance.get_json.assert_called_once_with("ipfs_hash", "request_id")
        assert result == {"key": "value"}
