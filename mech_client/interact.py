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
Shared configuration and utilities for mech interactions.

This module provides common dataclasses, configuration loading, and contract
interaction utilities used by both marketplace and other mech operations.
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from aea_ledger_ethereum import EthereumApi
from web3.contract import Contract as Web3Contract


PRIVATE_KEY_FILE_PATH = "ethereum_private_key.txt"
MECH_CONFIGS = Path(__file__).parent / "configs" / "mechs.json"
ABI_DIR_PATH = Path(__file__).parent / "abis"

MAX_RETRIES = 3
WAIT_SLEEP = 3.0
TIMEOUT = 60.0


@dataclass
class LedgerConfig:
    """Ledger configuration"""

    address: str
    chain_id: int
    poa_chain: bool
    default_gas_price_strategy: str
    is_gas_estimation_enabled: bool

    def __post_init__(self) -> None:
        """Post initialization to override with environment variables."""
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
    """Mech Marketplace Request Config"""

    mech_marketplace_contract: Optional[str] = field(default=None)
    priority_mech_address: Optional[str] = field(default=None)
    delivery_rate: Optional[int] = field(default=None)
    payment_type: Optional[str] = field(default=None)
    response_timeout: Optional[int] = field(default=None)
    payment_data: Optional[str] = field(default=None)


@dataclass
class MechConfig:  # pylint: disable=too-many-instance-attributes
    """Mech configuration"""

    service_registry_contract: str
    complementary_metadata_hash_address: str
    rpc_url: str
    wss_endpoint: str
    ledger_config: LedgerConfig
    gas_limit: int
    transaction_url: str
    subgraph_url: str
    price: int
    mech_marketplace_contract: str
    priority_mech_address: Optional[str] = field(default=None)

    def __post_init__(self) -> None:
        """Post initialization to override with environment variables."""
        service_registry_contract = os.getenv("MECHX_SERVICE_REGISTRY_CONTRACT")
        if service_registry_contract:
            self.service_registry_contract = service_registry_contract

        rpc_url = os.getenv("MECHX_CHAIN_RPC")
        if rpc_url:
            self.rpc_url = rpc_url

        wss_endpoint = os.getenv("MECHX_WSS_ENDPOINT")
        if wss_endpoint:
            self.wss_endpoint = wss_endpoint

        gas_limit = os.getenv("MECHX_GAS_LIMIT")
        if gas_limit:
            self.gas_limit = int(gas_limit)

        transaction_url = os.getenv("MECHX_TRANSACTION_URL")
        if transaction_url:
            self.transaction_url = transaction_url

        subgraph_url = os.getenv("MECHX_SUBGRAPH_URL")
        if subgraph_url:
            self.subgraph_url = subgraph_url


def get_mech_config(chain_config: Optional[str] = None) -> MechConfig:
    """Get `MechConfig` configuration"""
    with open(MECH_CONFIGS, "r", encoding="UTF-8") as file:
        data = json.load(file)

        if chain_config is None:
            chain_config = next(iter(data))

        entry = data[chain_config].copy()
        ledger_config = LedgerConfig(**entry.pop("ledger_config"))

        mech_config = MechConfig(
            **entry,
            ledger_config=ledger_config,
        )
        return mech_config


def get_abi(contract_abi_path: Path) -> List:
    """Get contract abi"""
    with open(contract_abi_path, encoding="utf-8") as f:
        abi = json.load(f)

    return abi if abi else []


def get_contract(
    contract_address: str, abi: List, ledger_api: EthereumApi
) -> Web3Contract:
    """
    Returns a contract instance.

    :param contract_address: The address of the contract.
    :type contract_address: str
    :param abi: ABI Object
    :type abi: List
    :param ledger_api: The Ethereum API used for interacting with the ledger.
    :type ledger_api: EthereumApi
    :return: The contract instance.
    :rtype: Web3Contract
    """

    return ledger_api.get_contract_instance(
        {"abi": abi, "bytecode": "0x"}, contract_address
    )
