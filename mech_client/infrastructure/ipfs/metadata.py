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

"""IPFS metadata creation and upload utilities."""

import json
import shutil
import tempfile
import uuid
from typing import Any, Dict, Optional, Tuple

from mech_client.infrastructure.ipfs.client import IPFSClient
from mech_client.infrastructure.ipfs.local_cid import compute_cidv1_bytes


def fetch_ipfs_hash(
    prompt: str,
    tool: str,
    extra_attributes: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str, str]:
    """
    Build offchain request metadata and compute its content CID locally.

    Used for offchain requests where the offchain mech never publishes the
    content to public IPFS. The CID is computed entirely in-process via
    ``compute_cidv1`` — no IPFS daemon is contacted, so the prompt and any
    extra attributes never leave the requester's process. The returned CID
    is byte-identical to what the mech computes locally on receipt, so the
    requester's signature over the CID verifies against the mech's
    recomputed value.

    :param prompt: Prompt string
    :param tool: Tool string
    :param extra_attributes: Extra attributes to be included in the request metadata
    :return: Tuple containing (truncated_hash, full_hash, ipfs_data)
             - truncated_hash: Hash with "0x" prefix for on-chain requests
             - full_hash: Full v1 hex hash for IPFS gateway URLs
             - ipfs_data: JSON string of metadata for offchain transmission
    """
    metadata = {"prompt": prompt, "tool": tool, "nonce": str(uuid.uuid4())}
    if extra_attributes:
        metadata.update(extra_attributes)

    # Convert metadata to JSON string for offchain transmission. The exact
    # bytes hashed below MUST match the bytes the mech receives in ipfs_data,
    # otherwise the mech's local recomputation produces a different CID and
    # the request is rejected.
    ipfs_data = json.dumps(metadata)

    # Compute the CIDv1 in-process and emit the legacy ``f01...`` hex form
    # the downstream truncation math expects (multibase 'f' + version '01' +
    # dag-pb codec '70' + sha256 multihash code '12' + length '20' + 32 hex
    # bytes of digest). ``compute_cidv1_bytes`` returns the raw CID bytes so
    # we can hex-encode directly — no multibase / multicodec round-trip.
    cid_bytes = compute_cidv1_bytes(ipfs_data.encode("utf-8"))
    v1_file_hash_hex = "f" + cid_bytes.hex()

    # Truncate hash for on-chain use (remove first 9 chars and add 0x prefix)
    truncated_hash = "0x" + v1_file_hash_hex[9:]
    return truncated_hash, v1_file_hash_hex, ipfs_data


def push_metadata_to_ipfs(
    prompt: str,
    tool: str,
    extra_attributes: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str]:
    """
    Create and push metadata object to IPFS.

    Creates a JSON metadata file containing prompt, tool, nonce, and optional
    extra attributes, then uploads it to IPFS.

    :param prompt: Prompt string
    :param tool: Tool string
    :param extra_attributes: Extra attributes to be included in the request metadata
    :return: Tuple containing (truncated_hash, full_hash)
             - truncated_hash: Hash with "0x" prefix for on-chain requests
             - full_hash: Full v1 hex hash for IPFS gateway URLs
    """
    metadata = {"prompt": prompt, "tool": tool, "nonce": str(uuid.uuid4())}
    if extra_attributes:
        metadata.update(extra_attributes)

    dirpath = tempfile.mkdtemp()
    try:
        file_name = dirpath + "/metadata.json"
        with open(file_name, "w", encoding="utf-8") as f:
            json.dump(metadata, f)

        client = IPFSClient()
        _, v1_file_hash_hex = client.upload(file_name)

        # Truncate hash for on-chain use (remove first 9 chars and add 0x prefix)
        truncated_hash = "0x" + v1_file_hash_hex[9:]
        return truncated_hash, v1_file_hash_hex
    finally:
        shutil.rmtree(dirpath, ignore_errors=True)
