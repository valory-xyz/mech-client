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
This script facilitates the conversion of a stability AI API's diffusion model output into a PNG format.

Usage:

python push_to_ipfs.py <ipfs_hash> <path>
"""
import json
import os.path
from base64 import b64decode
from tempfile import gettempdir

from aea_cli_ipfs.ipfs_utils import IPFSTool


def to_png(data: dict, path: str) -> None:
    """Stores a stability AI API's diffusion model output into a PNG formatted file."""
    for i, image in enumerate(data["artifacts"]):
        with open(path, "wb") as f:
            f.write(b64decode(image["base64"]))

    print(f"Successfully created {path}.")


def get_from_ipfs(ipfs_hash: str, request_id: str) -> dict:
    """Get data from IPFS."""
    temp_dir = gettempdir()
    IPFSTool().client.get(cid=ipfs_hash, target=temp_dir)
    stored_data = os.path.join(temp_dir, ipfs_hash)

    with open(os.path.join(stored_data, request_id)) as f:
        data = json.loads(f.read()).get("result", {})

    if not isinstance(data, dict):
        raise ValueError("Data do not have the expected format!")

    return data


def main(ipfs_hash: str, path: str, request_id: str) -> None:
    data_ = get_from_ipfs(ipfs_hash, request_id)
    to_png(data_, path)
