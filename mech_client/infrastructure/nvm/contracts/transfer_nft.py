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

"""TransferNFTCondition contract wrapper."""

import logging
from typing import Union

from eth_typing import ChecksumAddress
from web3.types import ENS

from mech_client.infrastructure.nvm.contracts.base import NVMContractWrapper


logger = logging.getLogger(__name__)


class TransferNFTContract(NVMContractWrapper):
    """Wrapper for the TransferNFTCondition smart contract."""

    CONTRACT_NAME = "TransferNFTCondition"

    def hash_values(  # pylint: disable=too-many-arguments
        self,
        did: str,
        from_address: Union[ChecksumAddress, ENS],
        to_address: Union[ChecksumAddress, ENS],
        amount: int,
        lock_condition_id: bytes,
        nft_contract_address: Union[ChecksumAddress, ENS],
        is_transfer: bool,
    ) -> bytes:
        """
        Compute the hash of parameters for the transfer condition.

        :param did: Decentralized identifier
        :param from_address: Address sending the NFT
        :param to_address: Address receiving the NFT
        :param amount: Number of tokens to transfer
        :param lock_condition_id: Lock payment condition ID
        :param nft_contract_address: NFT contract address
        :param is_transfer: Indicates if escrow is involved
        :return: Hashed value
        """
        logger.debug("Computing transfer NFT hash value")
        hash_value = self.functions.hashValues(
            did,
            from_address,
            to_address,
            amount,
            lock_condition_id,
            nft_contract_address,
            is_transfer,
        ).call()
        logger.debug(f"Transfer NFT hash: {hash_value.hex()}")
        return hash_value

    def generate_id(self, agreement_id: bytes, hash_value: bytes) -> bytes:
        """
        Generate the condition ID for the transfer NFT condition.

        :param agreement_id: ID of the agreement
        :param hash_value: Hashed condition parameters
        :return: Condition ID
        """
        logger.debug("Generating transfer NFT condition ID")
        condition_id = self.functions.generateId(agreement_id, hash_value).call()
        logger.info(f"Transfer NFT condition ID: {condition_id.hex()}")
        return condition_id
