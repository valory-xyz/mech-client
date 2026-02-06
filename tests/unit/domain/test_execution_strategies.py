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

"""Tests for domain.execution strategies."""

from unittest.mock import MagicMock, patch

import pytest

from mech_client.domain.execution.agent_executor import AgentExecutor
from mech_client.domain.execution.client_executor import ClientExecutor
from mech_client.domain.execution.factory import ExecutorFactory


class TestExecutorFactory:
    """Tests for ExecutorFactory."""

    @patch("mech_client.domain.execution.client_executor.EthereumCrypto")
    def test_create_client_executor(
        self, mock_crypto: MagicMock, mock_ledger_api: MagicMock
    ) -> None:
        """Test factory creates client executor for client mode."""
        mock_crypto_instance = MagicMock()
        mock_crypto.return_value = mock_crypto_instance
        
        executor = ExecutorFactory.create(
            agent_mode=False,
            ledger_api=mock_ledger_api,
            crypto=mock_crypto_instance,
            safe_address=None,
            ethereum_client=None,
        )

        assert isinstance(executor, ClientExecutor)
        assert executor.crypto == mock_crypto_instance

    def test_create_agent_executor(
        self, mock_ledger_api: MagicMock, mock_ethereum_client: MagicMock
    ) -> None:
        """Test factory creates agent executor for agent mode."""
        mock_crypto = MagicMock()
        
        executor = ExecutorFactory.create(
            agent_mode=True,
            ledger_api=mock_ledger_api,
            crypto=mock_crypto,
            safe_address="0x" + "a" * 40,
            ethereum_client=mock_ethereum_client,
        )

        assert isinstance(executor, AgentExecutor)
        assert executor.safe_address == "0x" + "a" * 40

    def test_create_agent_executor_missing_safe_address(
        self, mock_ledger_api: MagicMock, mock_ethereum_client: MagicMock
    ) -> None:
        """Test factory raises error when safe_address missing in agent mode."""
        mock_crypto = MagicMock()
        
        with pytest.raises(
            ValueError, match="Safe address and Ethereum client required"
        ):
            ExecutorFactory.create(
                agent_mode=True,
                ledger_api=mock_ledger_api,
                crypto=mock_crypto,
                safe_address=None,
                ethereum_client=mock_ethereum_client,
            )

    def test_create_agent_executor_missing_ethereum_client(
        self, mock_ledger_api: MagicMock
    ) -> None:
        """Test factory raises error when ethereum_client missing in agent mode."""
        mock_crypto = MagicMock()
        
        with pytest.raises(
            ValueError, match="Safe address and Ethereum client required"
        ):
            ExecutorFactory.create(
                agent_mode=True,
                ledger_api=mock_ledger_api,
                crypto=mock_crypto,
                safe_address="0x" + "a" * 40,
                ethereum_client=None,
            )
