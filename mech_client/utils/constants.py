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

"""Shared application-level constants."""

# CLI and user-facing constants
OPERATE_FOLDER_NAME = ".operate_mech_client"
SETUP_MODE_COMMAND = "setup"

# Default values
DEFAULT_TIMEOUT = 900.0  # 15 minutes in seconds
DEFAULT_MAX_RETRIES = 3
DEFAULT_GAS_LIMIT = 500000

# Transaction timeouts
TRANSACTION_RECEIPT_TIMEOUT = 300.0  # 5 minutes
TRANSACTION_CONFIRMATION_BLOCKS = 1

# IPFS constants
IPFS_GATEWAY_URL = "https://gateway.autonolas.tech/ipfs/"
IPFS_CID_V0_PREFIX = "Qm"
IPFS_CID_V1_PREFIX = "bafy"
IPFS_HEX_PREFIX = "f01"

# Mech delivery constants
DELIVERY_MECH_INDEX = 1  # Index of mech address in Deliver event
DELIVERY_DATA_INDEX = 2  # Index of data in Deliver event


# Supported chains (marketplace enabled)
SUPPORTED_MARKETPLACE_CHAINS = [
    "gnosis",
    "base",
    "polygon",
    "optimism",
]

# Chains supporting NVM subscriptions
NVM_SUPPORTED_CHAINS = [
    "gnosis",
    "base",
]

# File paths (relative to project root)
TEMPLATES_DIR_NAME = "config"

# Private key file (default name)
DEFAULT_PRIVATE_KEY_FILE = "ethereum_private_key.txt"

# Service template file names
TEMPLATE_GNOSIS = "mech_client_gnosis.json"
TEMPLATE_BASE = "mech_client_base.json"
TEMPLATE_POLYGON = "mech_client_polygon.json"
TEMPLATE_OPTIMISM = "mech_client_optimism.json"


# Chain-specific constants
GNOSIS_CHAIN_ID = 100
BASE_CHAIN_ID = 8453
POLYGON_CHAIN_ID = 137
OPTIMISM_CHAIN_ID = 10

CHAIN_ID_TO_NAME = {
    GNOSIS_CHAIN_ID: "gnosis",
    BASE_CHAIN_ID: "base",
    POLYGON_CHAIN_ID: "polygon",
    OPTIMISM_CHAIN_ID: "optimism",
}

CHAIN_NAME_TO_ID = {
    "gnosis": GNOSIS_CHAIN_ID,
    "base": BASE_CHAIN_ID,
    "polygon": POLYGON_CHAIN_ID,
    "optimism": OPTIMISM_CHAIN_ID,
}

# Safe multisig constants
SAFE_VERSION = "1.3.0"
SAFE_TX_GAS_BUFFER = 1.2  # 20% buffer for gas estimation

# Marketplace request types
REQUEST_TYPE_SINGLE = "single"
REQUEST_TYPE_BATCH = "batch"

# Payment method display names
PAYMENT_METHOD_NAMES = {
    "NATIVE": "Native Token",
    "OLAS_TOKEN": "OLAS Token",
    "USDC_TOKEN": "USDC Token",
    "NATIVE_NVM": "Native Token (NVM Subscription)",
    "TOKEN_NVM_USDC": "USDC Token (NVM Subscription)",
}

# Tool schema field names
TOOL_FIELD_NAME = "name"
TOOL_FIELD_DESCRIPTION = "description"
TOOL_FIELD_INPUT = "input"
TOOL_FIELD_OUTPUT = "output"
TOOL_FIELD_TOOLS = "tools"
TOOL_FIELD_TOOL_NAME = "tool"

# Metadata field names
METADATA_FIELD_HASH = "metadata"
METADATA_FIELD_SERVICE_ID = "id"
METADATA_FIELD_DELIVERIES = "totalDeliveries"

# Event names
EVENT_DELIVER = "Deliver"
EVENT_REQUEST = "Request"
EVENT_DEPOSIT = "Deposit"
