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

"""Chain configuration dataclasses."""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LedgerConfig:
    """Ledger configuration with environment variable override support.

    Attributes:
        address: RPC endpoint URL
        chain_id: Chain ID (e.g., 100 for Gnosis)
        poa_chain: Whether the chain uses Proof of Authority
        default_gas_price_strategy: Gas price strategy name
        is_gas_estimation_enabled: Whether to estimate gas automatically
        agent_mode: Whether running in agent mode (default: False)
        chain_config: Chain configuration name (e.g., 'gnosis')
    """

    address: str
    chain_id: int
    poa_chain: bool
    default_gas_price_strategy: str
    is_gas_estimation_enabled: bool
    agent_mode: bool = field(default=False)
    chain_config: Optional[str] = field(default=None)

    def __post_init__(self) -> None:
        """Post initialization to override with environment variables.

        Priority order for RPC address:
        1. MECHX_CHAIN_RPC environment variable (highest priority)
        2. Stored operate config (agent mode only)
        3. Default from mechs.json (lowest priority)
        """
        # In agent mode, try to load RPC from stored operate configuration first
        if self.agent_mode and self.chain_config:
            # Import here to avoid circular imports
            from mech_client.infrastructure.operate import (  # pylint: disable=import-outside-toplevel
                load_rpc_from_operate,
            )

            operate_rpc = load_rpc_from_operate(self.chain_config)
            if operate_rpc:
                self.address = operate_rpc

        # Environment variable overrides everything (including operate config)
        address = os.getenv("MECHX_CHAIN_RPC")
        if address:
            self.address = address

        chain_id = os.getenv("MECHX_LEDGER_CHAIN_ID")
        if chain_id:
            self.chain_id = int(chain_id)

        poa_chain = os.getenv("MECHX_LEDGER_POA_CHAIN")
        if poa_chain:
            self.poa_chain = bool(poa_chain)

        default_gas_price_strategy = os.getenv(
            "MECHX_LEDGER_DEFAULT_GAS_PRICE_STRATEGY"
        )
        if default_gas_price_strategy:
            self.default_gas_price_strategy = default_gas_price_strategy

        is_gas_estimation_enabled = os.getenv("MECHX_LEDGER_IS_GAS_ESTIMATION_ENABLED")
        if is_gas_estimation_enabled:
            self.is_gas_estimation_enabled = bool(is_gas_estimation_enabled)


@dataclass
class MechMarketplaceRequestConfig:
    """Configuration for marketplace requests.

    Attributes:
        mech_marketplace_contract: Marketplace contract address
        priority_mech_address: Priority mech address (optional)
        delivery_rate: Maximum delivery rate
        payment_type: Payment type identifier
        response_timeout: Timeout for response in seconds
        payment_data: Additional payment data
    """

    mech_marketplace_contract: Optional[str] = field(default=None)
    priority_mech_address: Optional[str] = field(default=None)
    delivery_rate: Optional[int] = field(default=None)
    payment_type: Optional[str] = field(default=None)
    response_timeout: Optional[int] = field(default=None)
    payment_data: Optional[str] = field(default=None)


@dataclass
class MechConfig:  # pylint: disable=too-many-instance-attributes
    """Chain-specific mech configuration with environment variable overrides.

    Attributes:
        complementary_metadata_hash_address: Metadata hash contract address
        rpc_url: HTTP RPC endpoint URL
        ledger_config: Ledger configuration
        gas_limit: Default gas limit for transactions
        transaction_url: Block explorer transaction URL template
        subgraph_url: Subgraph GraphQL endpoint URL
        price: Default price for requests
        mech_marketplace_contract: Marketplace contract address
        priority_mech_address: Priority mech address (optional)
        agent_mode: Whether running in agent mode (default: False)
        chain_config: Chain configuration name (e.g., 'gnosis')
    """

    complementary_metadata_hash_address: str
    rpc_url: str
    ledger_config: LedgerConfig
    gas_limit: int
    transaction_url: str
    subgraph_url: str
    price: int
    mech_marketplace_contract: str
    priority_mech_address: Optional[str] = field(default=None)
    agent_mode: bool = field(default=False)
    chain_config: Optional[str] = field(default=None)

    def __post_init__(self) -> None:
        """Post initialization to override with environment variables.

        Priority order for RPC URL:
        1. MECHX_CHAIN_RPC environment variable (highest priority)
        2. Stored operate config (agent mode only)
        3. Default from mechs.json (lowest priority)
        """
        # In agent mode, try to load RPC from stored operate configuration first
        if self.agent_mode and self.chain_config:
            # Import here to avoid circular imports
            from mech_client.infrastructure.operate import (  # pylint: disable=import-outside-toplevel
                load_rpc_from_operate,
            )

            operate_rpc = load_rpc_from_operate(self.chain_config)
            if operate_rpc:
                self.rpc_url = operate_rpc

        # Environment variable overrides everything (including operate config)
        rpc_url = os.getenv("MECHX_CHAIN_RPC")
        if rpc_url:
            self.rpc_url = rpc_url

        gas_limit = os.getenv("MECHX_GAS_LIMIT")
        if gas_limit:
            self.gas_limit = int(gas_limit)

        transaction_url = os.getenv("MECHX_TRANSACTION_URL")
        if transaction_url:
            self.transaction_url = transaction_url

        subgraph_url = os.getenv("MECHX_SUBGRAPH_URL")
        if subgraph_url:
            self.subgraph_url = subgraph_url
