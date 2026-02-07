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

"""AgreementStoreManager contract wrapper."""

import logging

from mech_client.infrastructure.nvm.contracts.base import NVMContractWrapper


logger = logging.getLogger(__name__)


class AgreementManagerContract(NVMContractWrapper):
    """Wrapper for the AgreementStoreManager smart contract."""

    CONTRACT_NAME = "AgreementStoreManager"

    def agreement_id(self, agreement_id_seed: str, subscriber: str) -> bytes:
        """
        Generate an agreement ID from seed and subscriber address.

        :param agreement_id_seed: Seed for the agreement ID
        :param subscriber: Address of the subscriber
        :return: The agreement ID
        """
        logger.debug("Generating agreement ID from seed and subscriber")
        agreement_id_value = self.functions.agreementId(
            agreement_id_seed, subscriber
        ).call()
        logger.info(f"Generated agreement ID: {agreement_id_value.hex()}")
        return agreement_id_value
