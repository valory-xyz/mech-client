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

"""SubscriptionProvider contract wrapper."""

import logging

from mech_client.infrastructure.nvm.contracts.base import NVMContractWrapper


logger = logging.getLogger(__name__)


class SubscriptionProviderContract(
    NVMContractWrapper
):  # pylint: disable=too-few-public-methods
    """
    Wrapper for the SubscriptionProvider smart contract.

    Note: Transaction building removed in favor of executor pattern.
    Use executor.execute_transaction() to call fulfill().
    """

    CONTRACT_NAME = "SubscriptionProvider"
