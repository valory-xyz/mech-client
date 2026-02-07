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

"""NeverminedConfig contract wrapper."""

import logging

from mech_client.infrastructure.nvm.contracts.base import NVMContractWrapper


logger = logging.getLogger(__name__)


class NeverminedConfigContract(NVMContractWrapper):
    """Wrapper for the NeverminedConfig contract."""

    CONTRACT_NAME = "NeverminedConfig"

    def get_fee_receiver(self) -> str:
        """
        Return the configured fee receiver address.

        :return: Fee receiver address
        """
        return self.functions.getFeeReceiver().call()

    def get_marketplace_fee(
        self,
    ) -> int:  # noqa: unused method (available for future use)
        """
        Return the marketplace fee in ppm (1e6 = 100%).

        :return: Marketplace fee in parts per million
        """
        return self.functions.getMarketplaceFee().call()
