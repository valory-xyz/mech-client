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

"""Transaction executor factory."""

from typing import Optional

from aea_ledger_ethereum import EthereumApi, EthereumCrypto
from mech_client.domain.execution.agent_executor import AgentExecutor
from mech_client.domain.execution.base import TransactionExecutor
from mech_client.domain.execution.client_executor import ClientExecutor
from mech_client.domain.signing import LocalSigner, Signer
from safe_eth.eth import EthereumClient


class ExecutorFactory:  # pylint: disable=too-few-public-methods
    """Factory for creating transaction executor instances.

    Creates the appropriate executor based on agent mode flag,
    eliminating agent/client mode branching throughout the codebase.
    """

    @staticmethod
    def create(  # pylint: disable=too-many-arguments
        agent_mode: bool,
        ledger_api: EthereumApi,
        crypto: Optional[EthereumCrypto] = None,
        safe_address: Optional[str] = None,
        ethereum_client: Optional[EthereumClient] = None,
        signer: Optional[Signer] = None,
    ) -> TransactionExecutor:
        """
        Create transaction executor for given mode.

        Signing goes through ``signer`` when provided; otherwise a
        ``LocalSigner`` is built around ``crypto``.

        :param agent_mode: True for agent mode (Safe), False for client mode (EOA)
        :param ledger_api: Ethereum API for blockchain interactions
        :param crypto: Ethereum crypto object for signing (alternative to signer)
        :param safe_address: Safe address (required for agent mode)
        :param ethereum_client: Ethereum client (required for agent mode)
        :param signer: Signer for externalized signing (alternative to crypto)
        :return: Concrete executor instance
        :raises ValueError: If neither crypto nor signer is provided, or if
            agent mode but Safe address/client not provided
        """
        if signer is None:
            if crypto is None:
                raise ValueError("Either a crypto object or a signer is required")
            signer = LocalSigner(crypto, ledger_api)

        if agent_mode:
            if not safe_address or not ethereum_client:
                raise ValueError(
                    "Safe address and Ethereum client required for agent mode"
                )
            return AgentExecutor(
                ledger_api,
                signer,
                safe_address,
                ethereum_client,
            )

        return ClientExecutor(ledger_api, signer)
