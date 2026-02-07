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

"""Native token payment strategy."""

from typing import Optional

from mech_client.domain.payment.base import PaymentStrategy
from mech_client.infrastructure.blockchain.abi_loader import get_abi
from mech_client.infrastructure.blockchain.contracts import get_contract
from mech_client.infrastructure.config import CHAIN_TO_NATIVE_BALANCE_TRACKER


class NativePaymentStrategy(PaymentStrategy):
    """Payment strategy for native token payments (xDAI, ETH, MATIC, etc.).

    Native payments don't require token approval since they're sent directly
    as value with the transaction.
    """

    def check_balance(
        self,
        payer_address: str,
        amount: int,
    ) -> bool:
        """
        Check if payer has sufficient native token balance.

        :param payer_address: Address of the payer
        :param amount: Amount to check (in wei)
        :return: True if balance is sufficient, False otherwise
        """
        balance = self.ledger_api.get_balance(payer_address)
        return balance >= amount

    def approve_if_needed(
        self,
        payer_address: str,
        spender_address: str,
        amount: int,
        private_key: Optional[str] = None,
    ) -> Optional[str]:
        """
        No approval needed for native token payments.

        :param payer_address: Address of the payer
        :param spender_address: Address allowed to spend tokens (ignored)
        :param amount: Amount to approve (ignored)
        :param private_key: Private key for signing (ignored)
        :return: None (no approval transaction)
        """
        return None  # Native payments don't need approval

    def get_balance_tracker_address(self) -> str:
        """
        Get the native balance tracker contract address for this chain.

        :return: Balance tracker contract address
        :raises ValueError: If native balance tracker not available for this chain
        """
        return self._lookup_balance_tracker(CHAIN_TO_NATIVE_BALANCE_TRACKER, "Native")

    def get_payment_token_address(self) -> Optional[str]:
        """
        Get the payment token contract address.

        :return: None (native payments don't use a token contract)
        """
        return None  # Native payments don't have a token address

    def check_prepaid_balance(
        self,
        requester_address: str,
        balance_tracker_address: str,
    ) -> int:
        """
        Check prepaid native token balance for requester.

        :param requester_address: Address of the requester
        :param balance_tracker_address: Balance tracker contract address
        :return: Prepaid balance amount in wei
        """
        abi = get_abi("BalanceTrackerFixedPriceNative.json")
        balance_tracker = get_contract(
            balance_tracker_address,
            abi,
            self.ledger_api,
        )
        return balance_tracker.functions.mapRequesterBalances(requester_address).call()
