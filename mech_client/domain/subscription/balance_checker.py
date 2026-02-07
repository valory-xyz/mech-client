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

"""Balance checker for NVM subscriptions."""

import logging
from typing import Optional

from web3 import Web3

from mech_client.infrastructure.nvm.config import NVMConfig
from mech_client.infrastructure.nvm.contracts import TokenContract


logger = logging.getLogger(__name__)


class SubscriptionBalanceChecker:  # pylint: disable=too-few-public-methods
    """Validates user has sufficient balance for subscription purchase."""

    def __init__(
        self,
        w3: Web3,
        config: NVMConfig,
        sender: str,
        token_contract: Optional[TokenContract] = None,
    ):
        """
        Initialize the balance checker.

        :param w3: Web3 instance
        :param config: NVM configuration
        :param sender: Sender address
        :param token_contract: Token contract (required for Base chain)
        """
        self.w3 = w3
        self.config = config
        self.sender = sender
        self.token_contract = token_contract

    def check(self) -> None:
        """
        Check if sender has sufficient balance.

        :raises ValueError: If insufficient balance
        """
        logger.info(f"Checking balance for {self.sender}")

        # Get total required amount
        required_amount = self.config.get_total_payment_amount()

        if self.config.requires_token_approval():
            # Base: Check USDC token balance (6 decimals)
            if not self.token_contract:
                raise ValueError("Token contract required for Base chain balance check")

            token_balance = self.token_contract.get_balance(self.sender)
            token_balance_human = self.w3.from_wei(token_balance, unit="mwei")
            required_human = self.w3.from_wei(required_amount, unit="mwei")

            logger.info(
                f"USDC balance: {token_balance_human}, required: {required_human}"
            )

            if token_balance < required_amount:
                raise ValueError(
                    f"Insufficient USDC balance. "
                    f"Required: {required_human} USDC, "
                    f"Available: {token_balance_human} USDC. "
                    f"Token address: {self.token_contract.address}"
                )
        else:
            # Gnosis: Check native xDAI balance (18 decimals)
            native_balance = self.w3.eth.get_balance(self.sender)
            native_balance_human = self.w3.from_wei(native_balance, unit="ether")
            required_human = self.w3.from_wei(required_amount, unit="ether")

            logger.info(
                f"Native balance: {native_balance_human}, required: {required_human}"
            )

            if native_balance < required_amount:
                raise ValueError(
                    f"Insufficient native balance. "
                    f"Required: {required_human} xDAI, "
                    f"Available: {native_balance_human} xDAI"
                )

        logger.info("Balance check passed")
