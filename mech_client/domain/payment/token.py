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

"""ERC20 token payment strategy."""

from typing import Optional, TYPE_CHECKING

from mech_client.domain.payment import addresses
from mech_client.domain.payment.base import PaymentStrategy
from mech_client.infrastructure.blockchain.abi_loader import get_abi
from mech_client.infrastructure.blockchain.contracts import get_contract
from mech_client.utils.validators import ensure_checksummed_address

if TYPE_CHECKING:
    from mech_client.domain.execution.base import TransactionExecutor


# Client-mode fallback gas for ERC20 approve when estimation fails. Ignored
# in agent mode (AgentExecutor hardcodes `gas: 0` and Safe estimates its own
# gas). Sized as a generous buffer above the ~67k measured cost of a
# 0->nonzero approve on Polygon's Circle USDC (FiatToken) proxy; the historic
# 60k underfunds that proxy. Re-measure if Circle upgrades the implementation.
_APPROVE_FALLBACK_GAS = 120_000


class TokenPaymentStrategy(PaymentStrategy):
    """Payment strategy for ERC20 token payments (OLAS, USDC).

    Token payments require approval before transfer. This strategy handles
    both OLAS and USDC token types.
    """

    def check_balance(
        self,
        payer_address: str,
        amount: int,
    ) -> bool:
        """
        Check if payer has sufficient token balance.

        :param payer_address: Address of the payer
        :param amount: Amount to check (in token's smallest unit)
        :return: True if balance is sufficient, False otherwise
        """
        token_address = self.get_payment_token_address()
        if not token_address:
            raise ValueError("Token address not configured for this payment type")

        abi = get_abi("IToken.json")
        token_contract = get_contract(token_address, abi, self.ledger_api)
        balance = token_contract.functions.balanceOf(payer_address).call()
        return balance >= amount

    def approve_if_needed(
        self,
        payer_address: str,
        spender_address: str,
        amount: int,
        executor: Optional["TransactionExecutor"] = None,
    ) -> str:
        """
        Approve token spending for the spender address.

        Builds and sends an approve transaction for the specified amount.
        This must be called before the actual token transfer. Always sends
        a transaction and returns the hash; raises if it cannot.

        :param payer_address: Address of the payer
        :param spender_address: Address allowed to spend tokens (balance tracker)
        :param amount: Amount to approve (in token's smallest unit)
        :param executor: Transaction executor (handles both agent and client mode)
        :return: Transaction hash of approval transaction
        :raises ValueError: If executor is not provided
        """
        if not executor:
            raise ValueError("Transaction executor required for token approval")

        token_address = self.get_payment_token_address()
        if not token_address:
            raise ValueError("Token address not configured for this payment type")

        abi = get_abi("IToken.json")
        token_contract = get_contract(token_address, abi, self.ledger_api)

        tx_args = {
            "sender_address": payer_address,
            "value": 0,
            "gas": _APPROVE_FALLBACK_GAS,
        }
        method_name = "approve"
        method_args = {"_to": spender_address, "_value": amount}

        return executor.execute_transaction(
            contract=token_contract,
            method_name=method_name,
            method_args=method_args,
            tx_args=tx_args,
        )

    def get_balance_tracker_address(self) -> str:
        """
        Get the token balance tracker contract address for this chain.

        Propagates ``ValueError`` from ``addresses.tracker_address`` when no tracker is
        registered for the token on the active chain.

        :return: Balance tracker contract address
        """
        self._check_token_type()
        return addresses.tracker_address(self.payment_type, self.chain_id)

    def get_payment_token_address(self) -> Optional[str]:
        """
        Get the payment token contract address.

        Propagates ``ValueError`` from ``addresses.token_address`` when the token is not
        deployed on the active chain.

        :return: Token contract address
        """
        self._check_token_type()
        return addresses.token_address(self.payment_type, self.chain_id)

    def _check_token_type(self) -> None:
        """Refuse a payment type that is not an OLAS or USDC token.

        :raises ValueError: For any other payment type
        """
        if not (self.payment_type.is_usdc() or self.payment_type.is_olas()):
            raise ValueError(f"Unknown token payment type: {self.payment_type}")

    def check_prepaid_balance(
        self,
        requester_address: str,
        balance_tracker_address: str,
    ) -> int:
        """
        Check prepaid token balance for requester.

        :param requester_address: Address of the requester
        :param balance_tracker_address: Balance tracker contract address
        :return: Prepaid balance amount in token's smallest unit
        """
        abi = get_abi("BalanceTrackerFixedPriceToken.json")
        balance_tracker = get_contract(
            balance_tracker_address,
            abi,
            self.ledger_api,
        )
        # Ensure address is checksummed (required by web3.py)
        checksummed_address = ensure_checksummed_address(requester_address)
        return balance_tracker.functions.mapRequesterBalances(
            checksummed_address
        ).call()
