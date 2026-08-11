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

"""Access to the result files mechs deliver to IPFS.

A mech delivers by pinning a *directory* whose entries are named after the
request id **in decimal**. The hash carried by the on-chain ``Deliver`` event
(and returned by the offchain endpoint as ``task_result``) therefore addresses
that directory, not the result: fetching it yields an HTML directory listing,
and the hex form of the request id used everywhere else in this client 404s.
The helpers here build the one URL that resolves to the result file and read
its content.
"""

import logging
from typing import Any, Optional

import requests
from mech_client.infrastructure.config import IPFS_URL_TEMPLATE

logger = logging.getLogger(__name__)

# Gateway reads are small JSON files; the delivery watchers already enforce
# the overall wait budget, so this only guards a single hung request.
RESULT_FILE_TIMEOUT = 30.0


def build_result_file_url(ipfs_hash: str, request_id_decimal: str) -> str:
    """
    Build the gateway URL of a delivered result file.

    :param ipfs_hash: Hex-encoded IPFS hash of the delivery directory
    :param request_id_decimal: Request ID in decimal, the name of the file
        inside that directory
    :return: URL that resolves to the result file itself
    """
    directory_url = IPFS_URL_TEMPLATE.format(ipfs_hash).rstrip("/")
    return f"{directory_url}/{request_id_decimal}"


def fetch_result_file(url: str, timeout: float = RESULT_FILE_TIMEOUT) -> Optional[Any]:
    """
    Fetch and parse a delivered result file.

    :param url: URL of the result file, as built by :func:`build_result_file_url`
    :param timeout: HTTP timeout in seconds
    :return: Parsed JSON content, the raw text if the file is not JSON, or
        ``None`` if the gateway could not be read
    """
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.warning("Could not fetch delivery result from %s: %s", url, e)
        return None

    try:
        return response.json()
    except ValueError:
        return response.text
