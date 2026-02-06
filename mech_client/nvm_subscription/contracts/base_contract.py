# subscription/contracts/base_contract.py
import json
import logging
import os
from typing import Any, Dict

from web3 import Web3
from web3.contract import Contract


# Configure module-level logger
logger = logging.getLogger(__name__)


class BaseContract:
    """
    Base class to interact with Ethereum smart contracts. Handles loading of contract
    ABI and instantiating a Web3 contract instance.
    """

    def __init__(self, w3: Web3, name: str):
        """
        Initialize the base contract wrapper.

        Args:
            w3 (Web3): An instance of Web3 connected to the desired network.
            name (str): The name of the contract artifact file (without extension).
        """
        self.w3 = w3
        self.name = name
        self.chain_id = self.w3.eth.chain_id
        chain_name_by_id = {100: "gnosis", 8453: "base", 137: "polygon", 10: "optimism"}
        self.chain_name = chain_name_by_id.get(self.chain_id)
        if not self.chain_name:
            raise ValueError(
                f"Unsupported chain id {self.chain_id}; no matching contract artifacts found"
            )

        logger.debug(f"Initializing contract wrapper for '{self.name}'")
        self.contract = self._load_contract()  # Load contract from artifact

        self.address = self.contract.address
        logger.info(f"Contract '{self.name}' loaded successfully")

    def _load_contract_info(self) -> Dict[str, Any]:
        """
        Load contract metadata (ABI and address) from the artifacts directory.

        Returns:
            dict: A dictionary containing the contract address and ABI.
        """
        current_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.abspath(os.path.join(current_dir, "..", "..", ".."))
        path = os.path.join(
            root_dir, "mech_client", "abis", f"{self.name}.{self.chain_name}.json"
        )
        logger.debug(f"Loading contract info from: {path}")
        with open(path, "r", encoding="utf-8") as f:
            info = json.load(f)  # Parse JSON containing ABI and address
        logger.debug(f"Loaded contract address: {info.get('address')}")
        return info

    def _load_contract(self) -> Contract:
        """
        Instantiate a Web3 contract object using the loaded contract info.

        Returns:
            Contract: A Web3 contract instance bound to the deployed address.
        """
        info = self._load_contract_info()
        address = self.w3.to_checksum_address(
            info["address"]
        )  # Ensure correct checksum
        logger.debug(f"Creating contract instance at address: {address}")
        contract = self.w3.eth.contract(address=address, abi=info["abi"])
        logger.info("Contract instance created successfully")
        return contract

    def functions(self) -> Any:
        """
        Access the functions of the loaded contract. Acts as a proxy to contract.functions.

        Returns:
            Any: The contract.functions interface for calling or building transactions.
        """
        logger.debug(f"Accessing contract functions for '{self.name}'")
        return self.contract.functions
