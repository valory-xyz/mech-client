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

"""IPFS client for uploading and downloading files."""

import json
import os.path
from tempfile import gettempdir
from typing import Optional, Tuple

import multibase
import multicodec
from aea.helpers.cid import to_v1
from aea_cli_ipfs.ipfs_utils import IPFSTool


class IPFSClient:
    """Client for interacting with IPFS gateway.

    Provides methods for uploading files, downloading files, and converting
    between IPFS hash formats (v0/v1, hex encoding).
    """

    def __init__(self) -> None:
        """Initialize IPFS client."""
        self._ipfs_tool = IPFSTool()

    def upload(self, file_path: str, pin: bool = True) -> Tuple[str, str]:
        """
        Upload a file to IPFS.

        :param file_path: Path of the file to be pushed to IPFS
        :param pin: Whether to pin the file (default: True for persistence)
        :return: A tuple containing (v1_file_hash, v1_file_hash_hex)
        """
        response = self._ipfs_tool.client.add(
            file_path, pin=pin, recursive=True, wrap_with_directory=False
        )
        v1_file_hash = to_v1(response["Hash"])
        cid_bytes = multibase.decode(v1_file_hash)
        multihash_bytes = multicodec.remove_prefix(cid_bytes)
        v1_file_hash_hex = "f01" + multihash_bytes.hex()
        return v1_file_hash, v1_file_hash_hex

    def download(self, ipfs_hash: str, target_dir: Optional[str] = None) -> str:
        """
        Download a file from IPFS.

        :param ipfs_hash: The IPFS hash (CID) of the file
        :param target_dir: Target directory for download (default: temp dir)
        :return: Path to downloaded file
        """
        if target_dir is None:
            target_dir = gettempdir()

        self._ipfs_tool.client.get(cid=ipfs_hash, target=target_dir)
        return os.path.join(target_dir, ipfs_hash)

    def get_json(self, ipfs_hash: str, request_id: str) -> dict:
        """
        Download and parse JSON data from IPFS.

        :param ipfs_hash: The IPFS hash of the data
        :param request_id: The request ID (filename within IPFS directory)
        :return: Parsed JSON data
        :raises ValueError: If data format is invalid
        """
        temp_dir = gettempdir()
        self._ipfs_tool.client.get(cid=ipfs_hash, target=temp_dir)
        stored_data = os.path.join(temp_dir, ipfs_hash)

        with open(os.path.join(stored_data, request_id), encoding="utf-8") as f:
            data = json.loads(f.read()).get("result", {})

        if not isinstance(data, dict):
            raise ValueError("Data do not have the expected format!")

        return data


# Legacy functions for backward compatibility
def push_to_ipfs(file_path: str) -> Tuple[str, str]:
    """
    Push a file to IPFS (legacy function).

    Deprecated: Use IPFSClient.upload() instead.

    :param file_path: Path of the file to be pushed to IPFS
    :return: A tuple containing (v1_file_hash, v1_file_hash_hex)
    """
    client = IPFSClient()
    return client.upload(file_path)


def get_from_ipfs(ipfs_hash: str, request_id: str) -> dict:
    """
    Get JSON data from IPFS (legacy function).

    Deprecated: Use IPFSClient.get_json() instead.

    :param ipfs_hash: The IPFS hash of the data
    :param request_id: The request ID
    :return: Parsed JSON data
    """
    client = IPFSClient()
    return client.get_json(ipfs_hash, request_id)
