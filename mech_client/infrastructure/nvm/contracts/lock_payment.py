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

"""LockPaymentCondition contract wrapper."""

import logging
from typing import List, Union

from eth_typing import ChecksumAddress
from web3.types import ENS

from mech_client.infrastructure.nvm.contracts.base import NVMContractWrapper


logger = logging.getLogger(__name__)


class LockPaymentContract(NVMContractWrapper):
    """Wrapper for the LockPaymentCondition smart contract."""

    CONTRACT_NAME = "LockPaymentCondition"

    def hash_values(  # pylint: disable=too-many-arguments
        self,
        did: str,
        reward_address: Union[ChecksumAddress, ENS],
        token_address: Union[ChecksumAddress, ENS],
        amounts: List[int],
        receivers: List[Union[ChecksumAddress, ENS]],
    ) -> bytes:
        """
        Compute the hash of the condition parameters.

        :param did: Decentralized identifier
        :param reward_address: Address to receive the reward
        :param token_address: ERC20 token address
        :param amounts: List of amounts for each receiver
        :param receivers: List of receiver addresses
        :return: The keccak256 hash of the encoded values
        """
        logger.debug("Computing hash for lock payment condition")
        hash_value = self.functions.hashValues(
            did, reward_address, token_address, amounts, receivers
        ).call()
        logger.debug(f"Computed hash: {hash_value.hex()}")
        return hash_value

    def generate_id(self, agreement_id: bytes, hash_value: bytes) -> bytes:
        """
        Generate a condition ID for a given agreement ID and hash.

        :param agreement_id: ID of the agreement
        :param hash_value: Hashed condition parameters
        :return: The condition ID
        """
        logger.debug("Generating condition ID from agreement ID and hash")
        condition_id = self.functions.generateId(agreement_id, hash_value).call()
        logger.info(f"Generated condition ID: {condition_id.hex()}")
        return condition_id
