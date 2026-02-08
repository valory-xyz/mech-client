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
