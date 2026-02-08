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

from mech_client.infrastructure.ipfs.client import IPFSClient
from mech_client.infrastructure.ipfs.metadata import push_metadata_to_ipfs
from mech_client.utils.errors.handlers import handle_cli_errors


@click.group()
def ipfs() -> None:
    """IPFS utility operations.

    Commands for uploading files and data to IPFS. IPFS is used to store
    request prompts and receive mech responses.
    """


@ipfs.command(name="upload")
@click.argument("file_path", metavar="<file-path>")
@handle_cli_errors
def ipfs_upload(file_path: str) -> None:
    """Upload a file to IPFS.

    Uploads any file to IPFS via the Olas IPFS gateway and returns the IPFS
    hash.

    Example: mechx ipfs upload ./myfile.json
    """
    client = IPFSClient()
    v1_file_hash, v1_file_hash_hex = client.upload(file_path)
    click.echo(f"IPFS file hash v1: {v1_file_hash}")
    click.echo(f"IPFS file hash v1 hex: {v1_file_hash_hex}")


@ipfs.command(name="upload-prompt")
@click.argument("prompt", metavar="<prompt>")
@click.argument("tool_name", metavar="<tool>")
@handle_cli_errors
def ipfs_upload_prompt(prompt: str, tool_name: str) -> None:
    """Upload prompt metadata to IPFS.

    Creates and uploads prompt metadata (prompt + tool) to IPFS for use in
    mech requests. Returns the IPFS hash that can be used in requests.

    Example: mechx ipfs upload-prompt "Summarize this text" "openai-gpt-4"
    """
    v1_file_hash_hex_truncated, v1_file_hash_hex = push_metadata_to_ipfs(
        prompt, tool_name
    )
    click.echo(f"Visit url: https://gateway.autonolas.tech/ipfs/{v1_file_hash_hex}")
    click.echo(f"Hash for Request method: {v1_file_hash_hex_truncated}")
