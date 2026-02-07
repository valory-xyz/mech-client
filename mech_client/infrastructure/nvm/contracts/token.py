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

"""SubscriptionToken (ERC20) contract wrapper."""

import logging
from typing import Union

from eth_typing import ChecksumAddress
from web3.types import ENS

from mech_client.infrastructure.nvm.contracts.base import NVMContractWrapper


logger = logging.getLogger(__name__)


class TokenContract(NVMContractWrapper):
    """
    Wrapper for the ERC20 token smart contract.

    Note: Transaction building removed in favor of executor pattern.
    Use executor.execute_transaction() to call approve().
    """

    CONTRACT_NAME = "SubscriptionToken"

    def get_balance(self, sender: Union[ChecksumAddress, ENS]) -> int:
        """
        Get the user's token balance.

        :param sender: User address
        :return: The user's token balance
        """
        sender_address: ChecksumAddress = self.w3.to_checksum_address(sender)

        balance = self.functions.balanceOf(sender_address).call()
        logger.debug(f"Fetched Token Balance: {balance}")
        return balance
