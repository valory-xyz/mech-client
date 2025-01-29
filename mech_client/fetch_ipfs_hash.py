# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2023 Valory AG
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

"""
This script allows fetching ipfs hash of data without uploading to IPFS.

Usage:

python fetch_ipfs_hash.py <data>
"""

import json
import shutil
import tempfile
import uuid
from typing import Any, Dict, Optional, Tuple

from aea.helpers.ipfs.base import IPFSHashOnly
from multibase import multibase
from multicodec import multicodec


def fetch_ipfs_hash(
    prompt: str, tool: str, extra_attributes: Optional[Dict[str, Any]] = None
) -> Tuple[Any, Any, bytes]:
    """
    Fetches IPFS hash of the data.

    :param prompt: Prompt string.
    :type prompt: str
    :param tool: Tool string.
    :type tool: str
    :param extra_attributes: Extra attributes to be included in the request metadata.
    :type extra_attributes: Optional[Dict[str,Any]]
    :return: Tuple containing the IPFS hash, truncated IPFS hash and the metadata for which the hash was calculated.
    :rtype: Tuple[str, str, bytes]
    """
    metadata = {"prompt": prompt, "tool": tool, "nonce": str(uuid.uuid4())}
    if extra_attributes:
        metadata.update(extra_attributes)

    dirpath = tempfile.mkdtemp()
    file_name = "metadata.json"
    with open(file_name, "w", encoding="utf-8") as f:
        json.dump(metadata, f, separators=(",", ":"))

    v1_file_hash = IPFSHashOnly.get(file_name, wrap=True)

    with open(file_name, "rb") as f:
        ipfs_data = f.read()

    shutil.rmtree(dirpath)

    cid_bytes = multibase.decode(v1_file_hash)
    multihash_bytes = multicodec.remove_prefix(cid_bytes)
    v1_file_hash_hex = "f01" + multihash_bytes.hex()

    return "0x" + v1_file_hash_hex[9:], v1_file_hash_hex, ipfs_data


def main(prompt: str, tool: str) -> None:
    """
    Prints the IPFS hash and truncated IPFS hash for the metadata object.

    :param prompt: Prompt string.
    :type prompt: str
    :param tool: Tool string.
    :type tool: str
    """

    v1_file_hash, _, _ = fetch_ipfs_hash(prompt, tool)
    print("IPFS file hash v1: {}".format(v1_file_hash))
