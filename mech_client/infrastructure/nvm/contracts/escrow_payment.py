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

"""EscrowPaymentCondition contract wrapper."""

import logging
from typing import List, Union

from eth_typing import ChecksumAddress
from web3 import Web3
from web3.types import ENS

from mech_client.infrastructure.nvm.contracts.base import NVMContractWrapper


logger = logging.getLogger(__name__)


class EscrowPaymentContract(NVMContractWrapper):
    """Wrapper for the EscrowPaymentCondition smart contract."""

    def __init__(self, w3: Web3):
        """
        Initialize the EscrowPaymentConditionContract.

        :param w3: Web3 instance connected to the network
        """
        logger.debug("Initializing EscrowPaymentConditionContract")
        super().__init__(w3, name="EscrowPaymentCondition")
        logger.info("EscrowPaymentConditionContract initialized")

    def hash_values(  # pylint: disable=too-many-arguments
        self,
        did: str,
        amounts: List[int],
        receivers: List[Union[ChecksumAddress, ENS]],
        sender: Union[ChecksumAddress, ENS],
        receiver: Union[ChecksumAddress, ENS],
        token_address: Union[ChecksumAddress, ENS],
        lock_condition_id: bytes,
        release_condition_id: bytes,
    ) -> bytes:
        """
        Compute the hash of parameters for escrow condition.

        :param did: Decentralized identifier
        :param amounts: Payment amounts
        :param receivers: Receiver addresses
        :param sender: Sender address
        :param receiver: Receiver address
        :param token_address: Token contract address
        :param lock_condition_id: ID of the lock payment condition
        :param release_condition_id: ID of the release condition
        :return: Hashed values
        """
        logger.debug("Computing hash for escrow payment condition")
        hash_value = self.functions.hashValues(
            did,
            amounts,
            receivers,
            sender,
            receiver,
            token_address,
            lock_condition_id,
            release_condition_id,
        ).call()
        logger.debug(f"Escrow payment hash: {hash_value.hex()}")
        return hash_value

    def generate_id(self, agreement_id: bytes, hash_value: bytes) -> bytes:
        """
        Generate the condition ID for the escrow payment.

        :param agreement_id: Agreement identifier
        :param hash_value: Hash of condition inputs
        :return: Generated condition ID
        """
        logger.debug("Generating escrow payment condition ID")
        condition_id = self.functions.generateId(agreement_id, hash_value).call()
        logger.info(f"Escrow payment condition ID: {condition_id.hex()}")
        return condition_id
