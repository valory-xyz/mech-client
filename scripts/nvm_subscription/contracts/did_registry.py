# subscription/contracts/did_registry.py
import logging
from typing import Dict, Any
from web3 import Web3
from web3.constants import ADDRESS_ZERO

from .base_contract import BaseContract

logger = logging.getLogger(__name__)


class DIDRegistryContract(BaseContract):
    """
    Wrapper class for the DIDRegistry smart contract.
    Provides methods to interact with DID-related functionality.
    """

    def __init__(self, w3: Web3):
        """
        Initialize the DIDRegistryContract with a Web3 instance.

        Args:
            w3 (Web3): Web3 instance connected to the desired Ethereum network.
        """
        super().__init__(w3, name="DIDRegistry")

    def get_ddo(self, did: str) -> Dict[str, Any]:
        """
        Retrieve the DDO (Decentralized Document Object) for a given DID.

        Args:
            did (str): Decentralized identifier (DID) to look up.

        Returns:
            Dict[str, Any]: Parsed DDO object.
        """
        logger.debug(f"Fetching DDO for DID: {did}")
        registered_values = self.functions().getDIDRegister(did).call()
        service_endpoint = registered_values[2]

        logger.debug(f"Resolved service endpoint: {service_endpoint}")
        response = self._fetch_ddo_from_endpoint(service_endpoint)

        ddo = {
            "did": f"did:nv:{did}",
            "serviceEndpoint": registered_values[2],
            "checksum": registered_values[1],
            "owner": registered_values[0],
            "providers": registered_values[5],
            "royalties": registered_values[6],
            "immutableUrl": registered_values[7],
            "nftInitialized": registered_values[8],
            "service": response.get("service", []),
            "proof": response.get("proof", [])
        }

        non_zero_providers = [
            addr
            for addr in ddo["providers"]
            if addr.lower() != ADDRESS_ZERO
        ]
        print("================ SUBSCRIBGING TO NVM OLAS PLAN =======================")
        print(f"PLAN : {ddo['did']}")
        print(f"OWNER: {ddo['owner']}")
        print(f"PROVIDERS: {non_zero_providers}")
        logger.info(f"ROYALTIES: {ddo['royalties']}")
        logger.info(f"IMMUTABLE URL: {ddo['immutableUrl']}")
        logger.info(f"NFT INITIALIZED: {ddo['nftInitialized']}")
        logger.info(f"DDO fetched successfully for DID: {did}")
        return ddo

    def _fetch_ddo_from_endpoint(self, endpoint: str) -> Dict[str, Any]:
        """
        Helper method to fetch the DDO JSON from a service endpoint.

        Args:
            endpoint (str): URL to fetch DDO data from.

        Returns:
            Dict[str, Any]: Parsed JSON response.
        """
        import requests

        try:
            response = requests.get(endpoint, timeout=10)
            response.raise_for_status()
            logger.debug(f"Received response from DDO endpoint: {response.status_code}")
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to fetch DDO from {endpoint}: {e}")
            return {}
