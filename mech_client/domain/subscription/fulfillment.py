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

"""Fulfillment builder for NVM subscriptions."""

import logging
from dataclasses import dataclass
from typing import List, Tuple

from mech_client.domain.subscription.agreement import AgreementData
from mech_client.infrastructure.nvm.config import NVMConfig


logger = logging.getLogger(__name__)


@dataclass
class FulfillmentData:
    """Data structure for subscription fulfillment."""

    fulfill_for_delegate_params: Tuple
    fulfill_params: Tuple


class FulfillmentBuilder:  # pylint: disable=too-few-public-methods
    """Builds fulfillment parameters for NVM subscription."""

    def __init__(self, config: NVMConfig, sender: str):
        """
        Initialize the fulfillment builder.

        :param config: NVM configuration
        :param sender: Sender address
        """
        self.config = config
        self.sender = sender

    def build(self, agreement: AgreementData) -> FulfillmentData:
        """
        Build fulfillment parameters from agreement data.

        :param agreement: Agreement data structure
        :return: Fulfillment data structure
        """
        logger.info("Building fulfillment parameters")

        # Prepare amounts [fee, price]
        amounts: List[int] = [
            int(self.config.plan_fee_nvm),
            int(self.config.plan_price_mechs),
        ]

        # Build fulfill_for_delegate_params tuple
        fulfill_for_delegate_params = (
            agreement.ddo["owner"],  # nftHolder
            self.sender,  # nftReceiver
            int(self.config.subscription_credits),  # nftAmount
            "0x" + agreement.lock_id.hex(),  # lockPaymentCondition
            self.config.subscription_nft_address,  # nftContractAddress
            False,  # transfer
            0,  # expirationBlock
        )

        # Build fulfill_params tuple
        fulfill_params = (
            amounts,  # amounts
            agreement.receivers,  # receivers
            self.sender,  # returnAddress
            agreement.reward_address,  # lockPaymentAddress
            self.config.token_address,  # tokenAddress
            "0x" + agreement.lock_id.hex(),  # lockCondition
            "0x" + agreement.transfer_id.hex(),  # releaseCondition
        )

        logger.info("Fulfillment parameters built successfully")

        return FulfillmentData(
            fulfill_for_delegate_params=fulfill_for_delegate_params,
            fulfill_params=fulfill_params,
        )
