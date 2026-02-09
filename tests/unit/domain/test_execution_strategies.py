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


class TestClientExecutorTransfer:
    """Tests for ClientExecutor.execute_transfer."""

    def test_execute_transfer_success(
        self, mock_ledger_api: MagicMock
    ) -> None:
        """Test successful native transfer in client mode."""
        mock_crypto = MagicMock()
        mock_crypto.address = "0x" + "1" * 40
        mock_crypto.private_key = "0x" + "a" * 64
        mock_crypto.sign_transaction.return_value = "0xsigned"
        mock_ledger_api.get_transfer_transaction.return_value = {"raw": "tx"}
        mock_ledger_api.send_signed_transaction.return_value = "0xtxhash"

        executor = ClientExecutor(mock_ledger_api, mock_crypto)
        to_address = "0x" + "2" * 40
        amount = 10**18
        gas = 50000

        result = executor.execute_transfer(to_address, amount, gas)

        assert result == "0xtxhash"
        mock_ledger_api.get_transfer_transaction.assert_called_once_with(
            sender_address=mock_crypto.address,
            destination_address=to_address,
            amount=amount,
            tx_fee=gas,
            tx_nonce="0x",
        )
        mock_crypto.sign_transaction.assert_called_once_with({"raw": "tx"})
        mock_ledger_api.send_signed_transaction.assert_called_once_with(
            "0xsigned", raise_on_try=True,
        )


class TestAgentExecutorTransfer:
    """Tests for AgentExecutor.execute_transfer."""

    @patch("mech_client.domain.execution.agent_executor.SafeClient")
    def test_execute_transfer_success(
        self,
        mock_safe_client_cls: MagicMock,
        mock_ledger_api: MagicMock,
        mock_ethereum_client: MagicMock,
    ) -> None:
        """Test successful native transfer through Safe multisig."""
        mock_crypto = MagicMock()
        mock_crypto.private_key = "0x" + "a" * 64

        mock_safe_client = MagicMock()
        mock_tx_hash = MagicMock()
        mock_tx_hash.to_0x_hex.return_value = "0xtxhash"
        mock_safe_client.send_transaction.return_value = mock_tx_hash
        mock_safe_client_cls.return_value = mock_safe_client

        safe_address = "0x" + "b" * 40
        executor = AgentExecutor(
            mock_ledger_api, mock_crypto, safe_address, mock_ethereum_client
        )

        to_address = "0x" + "2" * 40
        amount = 10**18

        result = executor.execute_transfer(to_address, amount, gas=50000)

        assert result == "0xtxhash"
        mock_safe_client.send_transaction.assert_called_once_with(
            to_address=to_address,
            tx_data="0x",
            signer_private_key=mock_crypto.private_key,
            value=amount,
        )

    @patch("mech_client.domain.execution.agent_executor.SafeClient")
    def test_execute_transfer_failure(
        self,
        mock_safe_client_cls: MagicMock,
        mock_ledger_api: MagicMock,
        mock_ethereum_client: MagicMock,
    ) -> None:
        """Test native transfer failure through Safe raises exception."""
        mock_crypto = MagicMock()
        mock_crypto.private_key = "0x" + "a" * 64

        mock_safe_client = MagicMock()
        mock_safe_client.send_transaction.return_value = None
        mock_safe_client_cls.return_value = mock_safe_client

        safe_address = "0x" + "b" * 40
        executor = AgentExecutor(
            mock_ledger_api, mock_crypto, safe_address, mock_ethereum_client
        )

        with pytest.raises(Exception, match="Failed to execute Safe transfer"):
            executor.execute_transfer("0x" + "2" * 40, 10**18, gas=50000)
