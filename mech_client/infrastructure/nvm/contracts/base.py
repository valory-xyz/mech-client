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

"""Base contract wrapper for NVM subscription contracts."""

import json
import logging
from pathlib import Path
from typing import Any, Dict

from web3 import Web3
from web3.contract import Contract


logger = logging.getLogger(__name__)


class NVMContractWrapper:  # pylint: disable=too-few-public-methods
    """
    Base class to interact with NVM smart contracts.

    Handles loading of contract ABI and instantiating a Web3 contract instance.
    Does NOT include transaction building methods - use executor pattern for that.
    """

    def __init__(self, w3: Web3, name: str):
        """
        Initialize the NVM contract wrapper.

        :param w3: Web3 instance connected to the network
        :param name: Contract artifact filename (without extension)
        """
        self.w3 = w3
        self.name = name
        self.chain_id = self.w3.eth.chain_id

        # Map chain ID to chain name for contract artifacts
        chain_name_by_id = {
            100: "gnosis",
            8453: "base",
            137: "polygon",
            10: "optimism",
        }
        self.chain_name = chain_name_by_id.get(self.chain_id)
        if not self.chain_name:
            raise ValueError(
                f"Unsupported chain ID {self.chain_id}; "
                f"no matching contract artifacts found"
            )

        logger.debug(f"Initializing contract wrapper for {self.name!r}")
        self.contract = self._load_contract()
        self.address = self.contract.address
        logger.info(f"Contract {self.name!r} loaded at {self.address}")

    def _load_contract_info(self) -> Dict[str, Any]:
        """
        Load contract metadata (ABI and address) from the artifacts directory.

        :return: Dictionary containing contract address and ABI
        """
        # Navigate to mech_client/abis/ directory
        current_dir = Path(__file__).parent
        abis_dir = current_dir.parent.parent.parent / "abis"
        artifact_path = abis_dir / f"{self.name}.{self.chain_name}.json"

        logger.debug(f"Loading contract info from: {artifact_path}")

        if not artifact_path.exists():
            raise FileNotFoundError(f"Contract artifact not found: {artifact_path}")

        with open(artifact_path, "r", encoding="utf-8") as f:
            info = json.load(f)

        logger.debug(f"Loaded contract address: {info.get('address')}")
        return info

    def _load_contract(self) -> Contract:
        """
        Instantiate a Web3 contract object using the loaded contract info.

        :return: Web3 contract instance bound to the deployed address
        """
        info = self._load_contract_info()
        address = self.w3.to_checksum_address(info["address"])

        logger.debug(f"Creating contract instance at address: {address}")
        contract = self.w3.eth.contract(address=address, abi=info["abi"])
        logger.info("Contract instance created successfully")

        return contract

    @property
    def functions(self) -> Any:
        """
        Access the functions of the loaded contract.

        :return: The contract.functions interface for view calls
        """
        return self.contract.functions
