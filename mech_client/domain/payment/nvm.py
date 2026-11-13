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

"""Nevermined (NVM) subscription payment strategy."""

from typing import Optional, TYPE_CHECKING

from mech_client.domain.payment.addresses import token_address, tracker_address
from mech_client.domain.payment.base import PaymentStrategy
from mech_client.infrastructure.blockchain.abi_loader import get_abi
from mech_client.infrastructure.blockchain.contracts import get_contract
from mech_client.infrastructure.config import PaymentType
from mech_client.utils.validators import ensure_checksummed_address

if TYPE_CHECKING:
    from mech_client.domain.execution.base import TransactionExecutor


class NVMPaymentStrategy(PaymentStrategy):
    """Payment strategy for Nevermined subscription-based payments.

    NVM subscriptions allow access to mechs without per-request payments.
    This strategy checks NVM subscription NFT balance and prepaid balance.
    """

    def check_balance(
        self,
        payer_address: str,
        amount: int,
    ) -> bool:
        """
        Check if payer has valid NVM subscription.

        For NVM payments, we check both the subscription NFT balance
        and the prepaid balance in the balance tracker.

        :param payer_address: Address of the payer
        :param amount: Amount to check (ignored for subscriptions)
        :return: True if subscription is active, False otherwise
        """
        balance_tracker_address = self.get_balance_tracker_address()
        subscription_balance = self.check_subscription_balance(
            payer_address, balance_tracker_address
        )
        return subscription_balance > 0

    def approve_if_needed(
        self,
        payer_address: str,
        spender_address: str,
        amount: int,
        executor: Optional["TransactionExecutor"] = None,
    ) -> Optional[str]:
        """
        No approval needed for NVM subscription payments.

        Subscriptions are handled via NFT ownership, no token approval required.

        :param payer_address: Address of the payer
        :param spender_address: Address allowed to spend (ignored)
        :param amount: Amount to approve (ignored)
        :param executor: Transaction executor (ignored)
        :return: None (no approval transaction)
        """
        return None  # NVM subscriptions don't need approval

    def get_balance_tracker_address(self) -> str:
        """
        Get the NVM balance tracker contract address for this chain.

        Native NVM uses the native tracker and USDC NVM the USDC one; a missing
        tracker propagates ``ValueError`` from ``tracker_address``.

        :return: Balance tracker contract address
        :raises ValueError: If the payment type is not an NVM type
        """
        if not self.payment_type.is_nvm():
            raise ValueError(f"Unknown NVM payment type: {self.payment_type}")
        return tracker_address(self.payment_type, self.chain_id)

    def get_payment_token_address(self) -> Optional[str]:
        """
        Get the payment token contract address for NVM subscriptions.

        A USDC token not deployed on the chain propagates ``ValueError`` from
        ``token_address``.

        :return: None for native NVM, USDC address for USDC NVM
        """
        if not self.payment_type.is_nvm():
            return None
        return token_address(self.payment_type, self.chain_id)

    def check_subscription_balance(
        self,
        requester_address: str,
        balance_tracker_address: str,
    ) -> int:
        """
        Check NVM subscription balance for requester.

        Queries both the prepaid balance in the balance tracker and the
        subscription NFT balance.

        :param requester_address: Address of the requester
        :param balance_tracker_address: Balance tracker contract address
        :return: Combined subscription balance
        """
        # Get balance tracker ABI based on payment type
        if self.payment_type == PaymentType.NATIVE_NVM:
            abi = get_abi("BalanceTrackerNvmSubscriptionNative.json")
        elif self.payment_type == PaymentType.TOKEN_NVM_USDC:
            abi = get_abi("BalanceTrackerNvmSubscriptionToken.json")
        else:
            raise ValueError(f"Unknown NVM payment type: {self.payment_type}")

        balance_tracker = get_contract(
            balance_tracker_address,
            abi,
            self.ledger_api,
        )

        # Ensure address is checksummed (required by web3.py)
        checksummed_address = ensure_checksummed_address(requester_address)

        # Get prepaid balance
        requester_balance_tracker_balance = (
            balance_tracker.functions.mapRequesterBalances(checksummed_address).call()
        )

        # Get subscription NFT details
        subscription_nft_address = balance_tracker.functions.subscriptionNFT().call()
        subscription_id = balance_tracker.functions.subscriptionTokenId().call()

        # Check subscription NFT balance
        nft_abi = get_abi("IERC1155.json")
        subscription_nft = get_contract(
            subscription_nft_address,
            nft_abi,
            self.ledger_api,
        )
        nft_balance = subscription_nft.functions.balanceOf(
            checksummed_address, subscription_id
        ).call()

        # Return combined balance
        return requester_balance_tracker_balance + nft_balance

    def check_prepaid_balance(
        self,
        requester_address: str,
        balance_tracker_address: str,
    ) -> int:
        """
        Check prepaid balance for NVM subscription.

        Alias for check_subscription_balance for consistency with base class.

        :param requester_address: Address of the requester
        :param balance_tracker_address: Balance tracker contract address
        :return: Subscription balance
        """
        return self.check_subscription_balance(
            requester_address, balance_tracker_address
        )
