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

from aea_ledger_ethereum import EthereumApi, EthereumCrypto

from mech_client.domain.payment.base import PaymentStrategy
from mech_client.infrastructure.blockchain.abi_loader import get_abi
from mech_client.infrastructure.blockchain.contracts import get_contract
from mech_client.infrastructure.config import (
    CHAIN_TO_PRICE_TOKEN_OLAS,
    CHAIN_TO_PRICE_TOKEN_USDC,
    CHAIN_TO_TOKEN_BALANCE_TRACKER_OLAS,
    CHAIN_TO_TOKEN_BALANCE_TRACKER_USDC,
    PaymentType,
)


if TYPE_CHECKING:
    from mech_client.domain.execution.base import TransactionExecutor


class TokenPaymentStrategy(PaymentStrategy):
    """Payment strategy for ERC20 token payments (OLAS, USDC).

    Token payments require approval before transfer. This strategy handles
    both OLAS and USDC token types.
    """

    def __init__(
        self,
        ledger_api: EthereumApi,
        payment_type: PaymentType,
        chain_id: int,
        crypto: Optional[EthereumCrypto] = None,
    ):
        """
        Initialize token payment strategy.

        :param ledger_api: Ethereum API for blockchain interactions
        :param payment_type: Type of payment (TOKEN or USDC_TOKEN)
        :param chain_id: Chain ID
        :param crypto: Ethereum crypto object for signing (optional)
        """
        super().__init__(ledger_api, payment_type, chain_id)
        self.crypto = crypto

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

    def approve_if_needed(  # pylint: disable=too-many-arguments,too-many-locals
        self,
        payer_address: str,
        spender_address: str,
        amount: int,
        executor: Optional["TransactionExecutor"] = None,
        private_key: Optional[str] = None,
    ) -> Optional[str]:
        """
        Approve token spending for the spender address.

        Builds and sends an approve transaction for the specified amount.
        This must be called before the actual token transfer.

        :param payer_address: Address of the payer
        :param spender_address: Address allowed to spend tokens (balance tracker)
        :param amount: Amount to approve (in token's smallest unit)
        :param executor: Transaction executor (handles both agent and client mode)
        :param private_key: Private key for signing (required for client mode without executor)
        :return: Transaction hash of approval transaction
        :raises ValueError: If neither executor nor crypto is provided
        """
        token_address = self.get_payment_token_address()
        if not token_address:
            raise ValueError("Token address not configured for this payment type")

        abi = get_abi("IToken.json")
        token_contract = get_contract(token_address, abi, self.ledger_api)

        # Build approval transaction arguments
        tx_args = {"sender_address": payer_address, "value": 0, "gas": 60000}
        method_name = "approve"
        method_args = {"_to": spender_address, "_value": amount}

        # Use executor if provided (handles both agent and client mode)
        if executor:
            return executor.execute_transaction(
                contract=token_contract,
                method_name=method_name,
                method_args=method_args,
                tx_args=tx_args,
            )

        # Fallback: client mode without executor (backward compatibility)
        if self.crypto or private_key:
            if not self.crypto:
                raise ValueError("Crypto object required for token approval")
            crypto = self.crypto
            raw_transaction = self.ledger_api.build_transaction(
                contract_instance=token_contract,
                method_name=method_name,
                method_args=method_args,
                tx_args=tx_args,
                raise_on_try=True,
            )
            signed_transaction = crypto.sign_transaction(raw_transaction)
            transaction_digest = self.ledger_api.send_signed_transaction(
                signed_transaction,
                raise_on_try=True,
            )
            return transaction_digest

        raise ValueError(
            "Transaction executor or crypto object/private key required for token approval"
        )

    def get_balance_tracker_address(self) -> str:
        """
        Get the token balance tracker contract address for this chain.

        :return: Balance tracker contract address
        :raises ValueError: If balance tracker not available for this chain/type
        """
        if self.payment_type.is_usdc():
            return self._lookup_balance_tracker(
                CHAIN_TO_TOKEN_BALANCE_TRACKER_USDC, "USDC"
            )
        if self.payment_type.is_olas():
            return self._lookup_balance_tracker(
                CHAIN_TO_TOKEN_BALANCE_TRACKER_OLAS, "OLAS"
            )
        raise ValueError(f"Unknown token payment type: {self.payment_type}")

    def get_payment_token_address(self) -> Optional[str]:
        """
        Get the payment token contract address.

        :return: Token contract address
        :raises ValueError: If token not available for this chain/type
        """
        if self.payment_type.is_usdc():
            token_address = CHAIN_TO_PRICE_TOKEN_USDC.get(self.chain_id, "")
            if not token_address:
                raise ValueError(f"USDC token not available for chain {self.chain_id}")
        elif self.payment_type.is_olas():
            token_address = CHAIN_TO_PRICE_TOKEN_OLAS.get(self.chain_id, "")
            if not token_address:
                raise ValueError(f"OLAS token not available for chain {self.chain_id}")
        else:
            raise ValueError(f"Unknown token payment type: {self.payment_type}")

        return token_address

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
        return balance_tracker.functions.mapRequesterBalances(requester_address).call()
