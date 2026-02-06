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

"""IPFS data format converters."""

from base64 import b64decode

from mech_client.infrastructure.ipfs.client import IPFSClient


def to_png(data: dict, path: str) -> None:
    """
    Convert Stability AI diffusion model output to PNG file.

    Extracts base64-encoded image data from diffusion model API response
    and saves it as a PNG file.

    :param data: Diffusion model output data with "artifacts" key
    :param path: Path where the PNG file should be saved
    """
    for image in data["artifacts"]:
        with open(path, "wb") as f:
            f.write(b64decode(image["base64"]))

    print(f"Successfully created {path}.")


def ipfs_to_png(ipfs_hash: str, output_path: str, request_id: str) -> None:
    """
    Download diffusion model output from IPFS and convert to PNG.

    Convenience function that combines downloading from IPFS and PNG conversion.

    :param ipfs_hash: The IPFS hash of the diffusion model output
    :param output_path: Path where the PNG file should be saved
    :param request_id: The request ID (filename in IPFS directory)
    """
    client = IPFSClient()
    data = client.get_json(ipfs_hash, request_id)
    to_png(data, output_path)
