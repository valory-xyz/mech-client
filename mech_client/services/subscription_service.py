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

"""Subscription service for NVM subscription management."""

from typing import Optional

from mech_client.nvm_subscription import nvm_subscribe_main


class SubscriptionService:
    """Service for managing Nevermined (NVM) subscriptions.

    Provides operations for purchasing and managing NVM subscriptions
    for subscription-based mech access.
    """

    def __init__(
        self,
        chain_config: str,
        agent_mode: bool,
        private_key_path: str,
        safe_address: Optional[str] = None,
        private_key_password: Optional[str] = None,
    ):
        """
        Initialize subscription service.

        :param chain_config: Chain configuration name (gnosis, base)
        :param agent_mode: True for agent mode (Safe), False for client mode (EOA)
        :param private_key_path: Path to private key file
        :param safe_address: Safe address (required for agent mode)
        :param private_key_password: Password for encrypted key (agent mode)
        """
        self.chain_config = chain_config
        self.agent_mode = agent_mode
        self.private_key_path = private_key_path
        self.safe_address = safe_address
        self.private_key_password = private_key_password

    def purchase_subscription(self) -> None:
        """
        Purchase NVM subscription for the chain.

        Uses the NVM subscription module to purchase a subscription plan.
        Currently supported on Gnosis and Base chains.

        :raises ValueError: If chain doesn't support NVM subscriptions
        :raises Exception: If subscription purchase fails
        """
        # Validate chain supports NVM
        from mech_client.nvm_subscription import (  # pylint: disable=import-outside-toplevel
            CHAIN_TO_ENVS,
        )

        if self.chain_config not in CHAIN_TO_ENVS:
            supported = ", ".join(CHAIN_TO_ENVS.keys())
            raise ValueError(
                f"NVM subscriptions not available for {self.chain_config}. "
                f"Supported chains: {supported}"
            )

        # Call NVM subscription main function
        nvm_subscribe_main(
            agent_mode=self.agent_mode,
            safe_address=self.safe_address,
            private_key_path=self.private_key_path,
            private_key_password=self.private_key_password,
            chain_config=self.chain_config,
        )

        print(f"✓ NVM subscription purchased for {self.chain_config}")

    def check_subscription_status(self, requester_address: str) -> bool:
        """
        Check if requester has active NVM subscription.

        :param requester_address: Address to check subscription for
        :return: True if subscription is active, False otherwise
        """
        # This would query the NVM subscription NFT balance
        # For now, return placeholder
        # TODO: Implement actual subscription status check
        return False
