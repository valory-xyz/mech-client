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

"""IPFS command for IPFS utility operations."""

import click

from mech_client.prompt_to_ipfs import main as prompt_to_ipfs_main
from mech_client.push_to_ipfs import main as push_to_ipfs_main
from mech_client.to_png import main as to_png_main


@click.group()
def ipfs() -> None:
    """IPFS utility operations.

    Commands for uploading files and data to IPFS, and converting responses
    to different formats. IPFS is used to store request prompts and receive
    mech responses.
    """


@ipfs.command(name="upload")
@click.argument("file_path", metavar="<file-path>")
def ipfs_upload(file_path: str) -> None:
    """Upload a file to IPFS.

    Uploads any file to IPFS via the Olas IPFS gateway and returns the IPFS
    hash.

    Example: mechx ipfs upload ./myfile.json
    """
    push_to_ipfs_main(file_path=file_path)


@ipfs.command(name="upload-prompt")
@click.argument("prompt", metavar="<prompt>")
@click.argument("tool_name", metavar="<tool>")
def ipfs_upload_prompt(prompt: str, tool_name: str) -> None:
    """Upload prompt metadata to IPFS.

    Creates and uploads prompt metadata (prompt + tool) to IPFS for use in
    mech requests. Returns the IPFS hash that can be used in requests.

    Example: mechx ipfs upload-prompt "Summarize this text" "openai-gpt-4"
    """
    prompt_to_ipfs_main(prompt=prompt, tool=tool_name)


@ipfs.command(name="to-png")
@click.argument("ipfs_hash", metavar="<ipfs-hash>")
@click.argument("path", metavar="<output-path>")
@click.argument("request_id", metavar="<request-id>")
def ipfs_to_png(ipfs_hash: str, path: str, request_id: str) -> None:
    """Convert diffusion model output to PNG.

    Downloads and converts Stability AI diffusion model output from IPFS
    to PNG image format. Used for image generation mech responses.

    Example: mechx ipfs to-png Qm... ./output.png 12345
    """
    to_png_main(ipfs_hash, path, request_id)
