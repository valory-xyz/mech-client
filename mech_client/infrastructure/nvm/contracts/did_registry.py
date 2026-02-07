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

"""DIDRegistry contract wrapper."""

import logging
from typing import Any, Dict

from web3 import Web3
from web3.constants import ADDRESS_ZERO

from mech_client.infrastructure.nvm.contracts.base import NVMContractWrapper


logger = logging.getLogger(__name__)


class DIDRegistryContract(NVMContractWrapper):
    """Wrapper for the DIDRegistry smart contract."""

    def __init__(self, w3: Web3):
        """
        Initialize the DIDRegistryContract.

        :param w3: Web3 instance connected to the network
        """
        logger.debug("Initializing DIDRegistryContract")
        super().__init__(w3, name="DIDRegistry")
        logger.info("DIDRegistryContract initialized")

    def get_ddo(self, did: str) -> Dict[str, Any]:
        """
        Retrieve the DDO (Decentralized Document Object) for a given DID.

        :param did: Decentralized identifier (DID) to look up
        :return: Parsed DDO object
        """
        logger.debug(f"Fetching DDO for DID: {did}")
        registered_values = self.functions.getDIDRegister(did).call()
        service_endpoint = registered_values[2]

        logger.debug(f"Resolved service endpoint: {service_endpoint}")
        ddo = {
            "did": f"did:nv:{did}",
            "serviceEndpoint": registered_values[2],
            "checksum": registered_values[1],
            "owner": registered_values[0],
            "providers": registered_values[5],
            "royalties": registered_values[6],
            "immutableUrl": registered_values[7],
            "nftInitialized": registered_values[8],
            # Legacy networks do not host a DDO metadata endpoint
            "service": [],
            "proof": [],
        }

        non_zero_providers = [
            addr for addr in ddo["providers"] if addr.lower() != ADDRESS_ZERO
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
