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

"""Configuration management for chain, contract, and payment settings."""

from mech_client.infrastructure.config.chain_config import (
    LedgerConfig,
    MechConfig,
    MechMarketplaceRequestConfig,
)
from mech_client.infrastructure.config.constants import (
    ABI_DIR_PATH,
    IPFS_URL_TEMPLATE,
    MAX_RETRIES,
    MECH_CONFIGS,
    PRIVATE_KEY_FILE_PATH,
    TIMEOUT,
    WAIT_SLEEP,
)
from mech_client.infrastructure.config.contract_addresses import (
    CHAIN_TO_NATIVE_BALANCE_TRACKER,
    CHAIN_TO_PRICE_TOKEN_OLAS,
    CHAIN_TO_PRICE_TOKEN_USDC,
    CHAIN_TO_TOKEN_BALANCE_TRACKER_OLAS,
    CHAIN_TO_TOKEN_BALANCE_TRACKER_USDC,
)
from mech_client.infrastructure.config.loader import get_mech_config
from mech_client.infrastructure.config.payment_config import PaymentType


__all__ = [
    # Dataclasses
    "LedgerConfig",
    "MechConfig",
    "MechMarketplaceRequestConfig",
    # Constants
    "ABI_DIR_PATH",
    "IPFS_URL_TEMPLATE",
    "MAX_RETRIES",
    "MECH_CONFIGS",
    "PRIVATE_KEY_FILE_PATH",
    "TIMEOUT",
    "WAIT_SLEEP",
    # Contract addresses
    "CHAIN_TO_NATIVE_BALANCE_TRACKER",
    "CHAIN_TO_PRICE_TOKEN_OLAS",
    "CHAIN_TO_PRICE_TOKEN_USDC",
    "CHAIN_TO_TOKEN_BALANCE_TRACKER_OLAS",
    "CHAIN_TO_TOKEN_BALANCE_TRACKER_USDC",
    # Loader
    "get_mech_config",
    # Payment
    "PaymentType",
]
