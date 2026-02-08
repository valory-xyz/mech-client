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

"""Base payment strategy interface."""

from abc import ABC, abstractmethod
from typing import Dict, Optional, TYPE_CHECKING

from aea_ledger_ethereum import EthereumApi

from mech_client.infrastructure.config import PaymentType


if TYPE_CHECKING:
    from mech_client.domain.execution.base import TransactionExecutor


class PaymentStrategy(ABC):
    """Abstract base class for payment strategies.

    Defines the interface that all payment strategies must implement.
    Each payment type (native, token, NVM) has its own concrete strategy.
    """

    def __init__(
        self,
        ledger_api: EthereumApi,
        payment_type: PaymentType,
        chain_id: int,
    ):
        """
        Initialize payment strategy.

        :param ledger_api: Ethereum API for blockchain interactions
        :param payment_type: Type of payment (NATIVE, TOKEN, etc.)
        :param chain_id: Chain ID (100=Gnosis, 137=Polygon, etc.)
        """
        self.ledger_api = ledger_api
        self.payment_type = payment_type
        self.chain_id = chain_id

    @abstractmethod
    def check_balance(
        self,
        payer_address: str,
        amount: int,
    ) -> bool:
        """
        Check if payer has sufficient balance for payment.

        :param payer_address: Address of the payer
        :param amount: Amount to check (in wei/smallest unit)
        :return: True if balance is sufficient, False otherwise
        """

    @abstractmethod
    def approve_if_needed(
        self,
        payer_address: str,
        spender_address: str,
        amount: int,
        executor: Optional["TransactionExecutor"] = None,
    ) -> Optional[str]:
        """
        Approve token spending if needed (for token-based payments).

        For native payments, this is a no-op.

        :param payer_address: Address of the payer
        :param spender_address: Address allowed to spend tokens
        :param amount: Amount to approve (in wei/smallest unit)
        :param executor: Transaction executor (handles both agent and client mode)
        :return: Transaction hash if approval was sent, None otherwise
        """

    @abstractmethod
    def get_balance_tracker_address(self) -> str:
        """
        Get the balance tracker contract address for this payment type.

        :return: Balance tracker contract address
        :raises ValueError: If balance tracker not available for this chain/type
        """

    @abstractmethod
    def get_payment_token_address(self) -> Optional[str]:
        """
        Get the payment token contract address.

        :return: Token address, or None for native payments
        """

    def check_prepaid_balance(  # pylint: disable=no-self-use,unused-argument
        self,
        requester_address: str,
        balance_tracker_address: str,
    ) -> int:
        """
        Check prepaid balance for requester.

        Default implementation returns 0 (no prepaid balance).
        Override in specific strategies that support prepaid balances.

        :param requester_address: Address of the requester
        :param balance_tracker_address: Balance tracker contract address
        :return: Prepaid balance amount
        """
        return 0

    def _lookup_balance_tracker(
        self, tracker_map: Dict[int, str], tracker_type: str
    ) -> str:
        """
        Helper method to lookup balance tracker address from chain ID.

        Consolidates the common pattern of looking up addresses by chain ID
        and raising a ValueError if not found.

        :param tracker_map: Dictionary mapping chain IDs to tracker addresses
        :param tracker_type: Description of tracker type for error message
        :return: Balance tracker contract address
        :raises ValueError: If tracker not available for this chain
        """
        tracker_address = tracker_map.get(self.chain_id, "")
        if not tracker_address:
            raise ValueError(
                f"{tracker_type} balance tracker not available for chain {self.chain_id}"
            )
        return tracker_address
