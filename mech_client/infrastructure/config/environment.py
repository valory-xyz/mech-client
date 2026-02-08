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

"""Centralized environment variable configuration.

This module provides a single source of truth for all environment variables
used throughout the mech-client application. All environment variable access
should go through this module rather than calling os.getenv() directly.
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class EnvironmentConfig:  # pylint: disable=too-many-instance-attributes
    """Centralized environment variable configuration.

    This class loads all MECHX_* and OPERATE_* environment variables at
    initialization time, providing a single source of truth for environment
    configuration throughout the application.

    **Design Principles:**
    - Single Responsibility: All env var loading happens here
    - Explicit over Implicit: All env vars are explicitly defined as fields
    - Testability: Easy to mock and test by passing a custom instance
    - Documentation: Self-documenting via type hints and docstrings

    **MECHX_* Variables (User Configuration):**
    - MECHX_CHAIN_RPC: Chain RPC endpoint URL
    - MECHX_SUBGRAPH_URL: Subgraph GraphQL endpoint URL
    - MECHX_MECH_OFFCHAIN_URL: Offchain mech endpoint URL
    - MECHX_GAS_LIMIT: Gas limit for transactions
    - MECHX_TRANSACTION_URL: Block explorer transaction URL template
    - MECHX_LEDGER_CHAIN_ID: Override chain ID
    - MECHX_LEDGER_POA_CHAIN: Enable POA chain mode
    - MECHX_LEDGER_DEFAULT_GAS_PRICE_STRATEGY: Gas price strategy
    - MECHX_LEDGER_IS_GAS_ESTIMATION_ENABLED: Enable gas estimation

    **OPERATE_* Variables (Internal Agent Mode):**
    - OPERATE_PASSWORD: Password for agent mode keyfile decryption

    **Usage:**
    ```python
    # Load environment config once
    env_config = EnvironmentConfig()

    # Access env vars through the config object
    if env_config.mechx_chain_rpc:
        use_custom_rpc(env_config.mechx_chain_rpc)
    ```
    """

    # MECHX_* user configuration variables
    mechx_chain_rpc: Optional[str] = None
    mechx_subgraph_url: Optional[str] = None
    mechx_mech_offchain_url: Optional[str] = None
    mechx_gas_limit: Optional[int] = None
    mechx_transaction_url: Optional[str] = None
    mechx_ledger_chain_id: Optional[int] = None
    mechx_ledger_poa_chain: Optional[bool] = None
    mechx_ledger_default_gas_price_strategy: Optional[str] = None
    mechx_ledger_is_gas_estimation_enabled: Optional[bool] = None

    # OPERATE_* internal agent mode variables
    operate_password: Optional[str] = None

    def __post_init__(self) -> None:
        """Load all environment variables at initialization time."""
        # MECHX_CHAIN_RPC - Chain RPC endpoint (most critical)
        chain_rpc = os.getenv("MECHX_CHAIN_RPC")
        if chain_rpc:
            self.mechx_chain_rpc = chain_rpc

        # MECHX_SUBGRAPH_URL - Subgraph endpoint for mech list
        subgraph_url = os.getenv("MECHX_SUBGRAPH_URL")
        if subgraph_url:
            self.mechx_subgraph_url = subgraph_url

        # MECHX_MECH_OFFCHAIN_URL - Offchain mech endpoint
        offchain_url = os.getenv("MECHX_MECH_OFFCHAIN_URL")
        if offchain_url:
            self.mechx_mech_offchain_url = offchain_url

        # MECHX_GAS_LIMIT - Gas limit override
        gas_limit_str = os.getenv("MECHX_GAS_LIMIT")
        if gas_limit_str:
            self.mechx_gas_limit = int(gas_limit_str)

        # MECHX_TRANSACTION_URL - Block explorer URL template
        transaction_url = os.getenv("MECHX_TRANSACTION_URL")
        if transaction_url:
            self.mechx_transaction_url = transaction_url

        # MECHX_LEDGER_CHAIN_ID - Chain ID override
        chain_id_str = os.getenv("MECHX_LEDGER_CHAIN_ID")
        if chain_id_str:
            self.mechx_ledger_chain_id = int(chain_id_str)

        # MECHX_LEDGER_POA_CHAIN - POA chain mode
        poa_chain_str = os.getenv("MECHX_LEDGER_POA_CHAIN")
        if poa_chain_str:
            self.mechx_ledger_poa_chain = poa_chain_str.lower() in ("true", "1", "yes")

        # MECHX_LEDGER_DEFAULT_GAS_PRICE_STRATEGY - Gas price strategy
        gas_strategy = os.getenv("MECHX_LEDGER_DEFAULT_GAS_PRICE_STRATEGY")
        if gas_strategy:
            self.mechx_ledger_default_gas_price_strategy = gas_strategy

        # MECHX_LEDGER_IS_GAS_ESTIMATION_ENABLED - Gas estimation flag
        gas_estimation_str = os.getenv("MECHX_LEDGER_IS_GAS_ESTIMATION_ENABLED")
        if gas_estimation_str:
            self.mechx_ledger_is_gas_estimation_enabled = (
                gas_estimation_str.lower()
                in (
                    "true",
                    "1",
                    "yes",
                )
            )

        # OPERATE_PASSWORD - Agent mode password
        password = os.getenv("OPERATE_PASSWORD")
        if password:
            self.operate_password = password

    @classmethod
    def load(cls) -> "EnvironmentConfig":
        """
        Factory method to create and load environment configuration.

        This is the preferred way to create an EnvironmentConfig instance.

        :return: Loaded EnvironmentConfig instance
        """
        return cls()
