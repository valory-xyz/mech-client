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

"""SubscriptionNFT contract wrapper."""

import logging
from typing import Union

from eth_typing import ChecksumAddress
from web3 import Web3
from web3.types import ENS

from mech_client.infrastructure.nvm.contracts.base import NVMContractWrapper


logger = logging.getLogger(__name__)


class NFTContract(NVMContractWrapper):
    """Wrapper for the Subscription NFT (ERC1155) smart contract."""

    def __init__(self, w3: Web3):
        """
        Initialize the Subscription NFT instance.

        :param w3: Web3 instance connected to the network
        """
        logger.debug("Initializing Subscription NFT")
        super().__init__(w3, name="SubscriptionNFT")
        logger.info("Subscription NFT initialized")

    def get_balance(
        self, sender: Union[ChecksumAddress, ENS], subscription_id: str
    ) -> int:
        """
        Get the user's subscription credit balance.

        :param sender: User address
        :param subscription_id: Subscription ID
        :return: The user's credit balance
        """
        sender_address: ChecksumAddress = self.w3.to_checksum_address(sender)

        balance = self.functions.balanceOf(sender_address, int(subscription_id)).call()
        logger.debug(f"Fetched Balance: {balance}")
        return balance
