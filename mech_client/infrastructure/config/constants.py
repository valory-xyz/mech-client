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

"""Shared constants for mech client configuration."""

from pathlib import Path


# File paths
PRIVATE_KEY_FILE_PATH = "ethereum_private_key.txt"
MECH_CONFIGS = Path(__file__).parent.parent.parent / "configs" / "mechs.json"
ABI_DIR_PATH = Path(__file__).parent.parent.parent / "abis"

# Retry and timeout settings
MAX_RETRIES = 3
WAIT_SLEEP = 3.0
TIMEOUT = 60.0

# Transaction receipt timeout (5 minutes)
TRANSACTION_RECEIPT_TIMEOUT = 300.0

# IPFS gateway
IPFS_GATEWAY_URL = "https://gateway.autonolas.tech/ipfs/"
IPFS_URL_TEMPLATE = "https://gateway.autonolas.tech/ipfs/f01701220{}"

# Chain IDs for supported networks
CHAIN_ID_GNOSIS = 100
CHAIN_ID_BASE = 8453
CHAIN_ID_POLYGON = 137
CHAIN_ID_OPTIMISM = 10

# Mapping from chain ID to chain name
CHAIN_ID_TO_NAME = {
    CHAIN_ID_GNOSIS: "gnosis",
    CHAIN_ID_BASE: "base",
    CHAIN_ID_POLYGON: "polygon",
    CHAIN_ID_OPTIMISM: "optimism",
}
