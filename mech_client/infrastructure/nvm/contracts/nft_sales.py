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

"""NFTSalesTemplate contract wrapper."""

import logging

from web3 import Web3

from mech_client.infrastructure.nvm.contracts.base import NVMContractWrapper


logger = logging.getLogger(__name__)


class NFTSalesTemplateContract(
    NVMContractWrapper
):  # pylint: disable=too-few-public-methods
    """
    Wrapper for the NFTSalesTemplate smart contract.

    Note: Transaction building removed in favor of executor pattern.
    Use executor.execute_transaction() to call createAgreement().
    """

    def __init__(self, w3: Web3):
        """
        Initialize the NFTSalesTemplateContract.

        :param w3: Web3 instance connected to the network
        """
        logger.debug("Initializing NFTSalesTemplateContract")
        super().__init__(w3, name="NFTSalesTemplate")
        logger.info("NFTSalesTemplateContract initialized")
