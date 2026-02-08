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

"""Payment strategy factory."""

from typing import Optional

from aea_ledger_ethereum import EthereumApi, EthereumCrypto

from mech_client.domain.payment.base import PaymentStrategy
from mech_client.domain.payment.native import NativePaymentStrategy
from mech_client.domain.payment.nvm import NVMPaymentStrategy
from mech_client.domain.payment.token import TokenPaymentStrategy
from mech_client.infrastructure.config import PaymentType


class PaymentStrategyFactory:  # pylint: disable=too-few-public-methods
    """Factory for creating payment strategy instances.

    Creates the appropriate payment strategy based on payment type,
    eliminating the need for conditional logic throughout the codebase.
    """

    @staticmethod
    def create(
        payment_type: PaymentType,
        ledger_api: EthereumApi,
        chain_id: int,
        crypto: Optional[EthereumCrypto] = None,
    ) -> PaymentStrategy:
        """
        Create payment strategy for given payment type.

        :param payment_type: Type of payment
        :param ledger_api: Ethereum API for blockchain interactions
        :param chain_id: Chain ID (100=Gnosis, 137=Polygon, etc.)
        :param crypto: Ethereum crypto object for signing (optional)
        :return: Concrete payment strategy instance
        :raises ValueError: If payment type is unknown
        """
        if payment_type == PaymentType.NATIVE:
            return NativePaymentStrategy(ledger_api, payment_type, chain_id)

        if payment_type in (PaymentType.OLAS_TOKEN, PaymentType.USDC_TOKEN):
            return TokenPaymentStrategy(ledger_api, payment_type, chain_id, crypto)

        if payment_type in (PaymentType.NATIVE_NVM, PaymentType.TOKEN_NVM_USDC):
            return NVMPaymentStrategy(ledger_api, payment_type, chain_id)

        raise ValueError(f"Unknown payment type: {payment_type}")
