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

"""Payment type configuration and mappings."""

from enum import Enum


class PaymentType(Enum):
    """Payment type identifiers for mech marketplace.

    Values are keccak256 hashes identifying each payment type:
    - NATIVE: Native token payment (xDAI, ETH, MATIC, etc.)
    - TOKEN: OLAS token payment
    - USDC_TOKEN: USDC token payment
    - NATIVE_NVM: Native token with NVM subscription
    - TOKEN_NVM_USDC: USDC token with NVM subscription
    """

    NATIVE = "ba699a34be8fe0e7725e93dcbce1701b0211a8ca61330aaeb8a05bf2ec7abed1"  # nosec
    TOKEN = "3679d66ef546e66ce9057c4a052f317b135bc8e8c509638f7966edfd4fcf45e9"  # nosec
    USDC_TOKEN = (
        "6406bb5f31a732f898e1ce9fdd988a80a808d36ab5d9a4a4805a8be8d197d5e3"  # nosec
    )
    NATIVE_NVM = (
        "803dd08fe79d91027fc9024e254a0942372b92f3ccabc1bd19f4a5c2b251c316"  # nosec
    )
    TOKEN_NVM_USDC = (
        "0d6fd99afa9c4c580fab5e341922c2a5c4b61d880da60506193d7bf88944dd14"  # nosec
    )

    @classmethod
    def from_value(cls, value: str) -> "PaymentType":
        """Get PaymentType from hash value.

        :param value: Payment type hash value
        :return: PaymentType enum member
        :raises ValueError: If value doesn't match any payment type
        """
        for payment_type in cls:
            if payment_type.value == value:
                return payment_type
        raise ValueError(f"Unknown payment type value: {value}")

    def is_native(self) -> bool:
        """Check if payment type uses native tokens."""
        return self in (PaymentType.NATIVE, PaymentType.NATIVE_NVM)

    def is_token(self) -> bool:
        """Check if payment type uses ERC20 tokens."""
        return self in (
            PaymentType.TOKEN,
            PaymentType.USDC_TOKEN,
            PaymentType.TOKEN_NVM_USDC,
        )

    def is_nvm(self) -> bool:
        """Check if payment type uses NVM subscription."""
        return self in (PaymentType.NATIVE_NVM, PaymentType.TOKEN_NVM_USDC)

    def is_usdc(self) -> bool:
        """Check if payment type uses USDC token."""
        return self in (PaymentType.USDC_TOKEN, PaymentType.TOKEN_NVM_USDC)

    def is_olas(self) -> bool:
        """Check if payment type uses OLAS token."""
        return self == PaymentType.TOKEN
