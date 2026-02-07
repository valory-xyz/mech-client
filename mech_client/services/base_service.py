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

"""Base service class for transaction services."""

from dataclasses import asdict
from typing import Optional

from aea_ledger_ethereum import EthereumApi, EthereumCrypto
from safe_eth.eth import EthereumClient

from mech_client.domain.execution import ExecutorFactory, TransactionExecutor
from mech_client.infrastructure.config import MechConfig, get_mech_config


class BaseTransactionService:  # pylint: disable=too-few-public-methods,too-many-instance-attributes
    """
    Base class for services that execute blockchain transactions.

    Provides common initialization for:
    - Chain configuration and mech config loading
    - Ethereum API creation from ledger config
    - Transaction executor setup (agent mode or client mode)
    - Crypto and address management

    Subclasses should call super().__init__() first, then add their own
    specific initialization.
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        chain_config: str,
        agent_mode: bool,
        crypto: EthereumCrypto,
        safe_address: Optional[str] = None,
        ethereum_client: Optional[EthereumClient] = None,
    ):
        """
        Initialize base transaction service.

        :param chain_config: Chain configuration name (gnosis, base, polygon, optimism)
        :param agent_mode: True for agent mode (Safe), False for client mode (EOA)
        :param crypto: Ethereum crypto object for signing
        :param safe_address: Safe address (required for agent mode)
        :param ethereum_client: Ethereum client (required for agent mode)
        """
        self.chain_config = chain_config
        self.agent_mode = agent_mode
        self.crypto = crypto
        self.private_key = crypto.private_key
        self.safe_address = safe_address
        self.ethereum_client = ethereum_client

        # Load configuration
        self.mech_config: MechConfig = get_mech_config(chain_config)
        self.ledger_api = EthereumApi(**asdict(self.mech_config.ledger_config))

        # Create executor
        self.executor: TransactionExecutor = ExecutorFactory.create(
            agent_mode=agent_mode,
            ledger_api=self.ledger_api,
            crypto=crypto,
            safe_address=safe_address,
            ethereum_client=ethereum_client,
        )
