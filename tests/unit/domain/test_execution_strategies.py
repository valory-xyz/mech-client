# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2025-2026 Valory AG
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
from mech_client.domain.signing import LocalSigner

from tests.unit.helpers import DEFAULT_TX_HASH, create_mock_signer


class TestExecutorFactory:
    """Tests for ExecutorFactory."""

    def test_create_client_executor(self, mock_ledger_api: MagicMock) -> None:
        """Test factory creates client executor wrapping crypto in LocalSigner."""
        mock_crypto_instance = MagicMock()

        executor = ExecutorFactory.create(
            agent_mode=False,
            ledger_api=mock_ledger_api,
            crypto=mock_crypto_instance,
            safe_address=None,
            ethereum_client=None,
        )

        assert isinstance(executor, ClientExecutor)
        assert isinstance(executor.signer, LocalSigner)
        assert executor.signer.crypto == mock_crypto_instance

    def test_create_client_executor_with_signer(
        self, mock_ledger_api: MagicMock
    ) -> None:
        """Test factory uses an injected signer directly (no crypto needed)."""
        mock_signer = create_mock_signer()

        executor = ExecutorFactory.create(
            agent_mode=False,
            ledger_api=mock_ledger_api,
            signer=mock_signer,
        )

        assert isinstance(executor, ClientExecutor)
        assert executor.signer is mock_signer

    def test_create_requires_crypto_or_signer(
        self, mock_ledger_api: MagicMock
    ) -> None:
        """Test factory raises when neither crypto nor signer is provided."""
        with pytest.raises(
            ValueError, match="Either a crypto object or a signer is required"
        ):
            ExecutorFactory.create(
                agent_mode=False,
                ledger_api=mock_ledger_api,
            )

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
        mock_signer = create_mock_signer()
        mock_ledger_api.get_transfer_transaction.return_value = {"raw": "tx"}

        executor = ClientExecutor(mock_ledger_api, mock_signer)
        to_address = "0x" + "2" * 40
        amount = 10**18
        gas = 50000

        result = executor.execute_transfer(to_address, amount, gas)

        assert result == DEFAULT_TX_HASH
        mock_ledger_api.get_transfer_transaction.assert_called_once_with(
            sender_address=mock_signer.address,
            destination_address=to_address,
            amount=amount,
            tx_fee=gas,
            tx_nonce="0x",
        )
        mock_signer.send_transaction.assert_called_once_with({"raw": "tx"})


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
        mock_signer = create_mock_signer()

        mock_safe_client = MagicMock()
        mock_tx_hash = MagicMock()
        mock_tx_hash.to_0x_hex.return_value = "0xtxhash"
        mock_safe_client.send_transaction.return_value = mock_tx_hash
        mock_safe_client_cls.return_value = mock_safe_client

        safe_address = "0x" + "b" * 40
        executor = AgentExecutor(
            mock_ledger_api, mock_signer, safe_address, mock_ethereum_client
        )

        to_address = "0x" + "2" * 40
        amount = 10**18

        result = executor.execute_transfer(to_address, amount, gas=50000)

        assert result == "0xtxhash"
        mock_safe_client.send_transaction.assert_called_once_with(
            to_address=to_address,
            tx_data="0x",
            signer=mock_signer,
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
        mock_signer = create_mock_signer()

        mock_safe_client = MagicMock()
        mock_safe_client.send_transaction.side_effect = Exception(
            "Transaction execution fails"
        )
        mock_safe_client_cls.return_value = mock_safe_client

        safe_address = "0x" + "b" * 40
        executor = AgentExecutor(
            mock_ledger_api, mock_signer, safe_address, mock_ethereum_client
        )

        with pytest.raises(
            Exception,
            match="Failed to execute Safe transfer transaction: "
            "Transaction execution fails",
        ):
            executor.execute_transfer("0x" + "2" * 40, 10**18, gas=50000)


class TestAgentExecutorTransaction:
    """Tests for AgentExecutor.execute_transaction."""

    @patch("mech_client.domain.execution.agent_executor.SafeClient")
    def test_execute_transaction_maps_sender_address_to_from(
        self,
        mock_safe_client_cls: MagicMock,
        mock_ledger_api: MagicMock,
        mock_ethereum_client: MagicMock,
    ) -> None:
        """tx_args uses sender_address, but web3 build_transaction expects from."""
        mock_signer = create_mock_signer()
        mock_ledger_api._chain_id = 100  # pylint: disable=protected-access

        mock_safe_client = MagicMock()
        mock_safe_client.get_nonce.return_value = 7
        mock_tx_hash = MagicMock()
        mock_tx_hash.to_0x_hex.return_value = "0xtxhash"
        mock_safe_client.send_transaction.return_value = mock_tx_hash
        mock_safe_client_cls.return_value = mock_safe_client

        executor = AgentExecutor(
            mock_ledger_api, mock_signer, "0x" + "b" * 40, mock_ethereum_client
        )

        # Mock contract function build_transaction
        mock_function = MagicMock()
        mock_function.build_transaction.return_value = {"data": "0xdeadbeef"}
        mock_contract = MagicMock()
        mock_contract.address = "0x" + "c" * 40
        mock_contract.functions.__getitem__.return_value.return_value = mock_function

        tx_hash = executor.execute_transaction(
            contract=mock_contract,
            method_name="foo",
            method_args={"x": 1},
            tx_args={"sender_address": "0x" + "1" * 40, "value": 0, "gas": 12345},
        )

        assert tx_hash == "0xtxhash"
        # ensure build_transaction got a `from` field
        args, _ = mock_function.build_transaction.call_args
        assert args[0]["from"] == "0x" + "1" * 40


class TestClientExecutorTransaction:
    """Tests for ClientExecutor.execute_transaction."""

    def test_execute_transaction_success(
        self, mock_ledger_api: MagicMock
    ) -> None:
        """Test successful contract transaction in client mode."""
        mock_signer = create_mock_signer()
        mock_ledger_api.build_transaction.return_value = {"raw": "tx"}

        executor = ClientExecutor(mock_ledger_api, mock_signer)

        mock_contract = MagicMock()
        sender = "0x" + "1" * 40
        method_args = {"param": "value"}
        tx_args = {"sender_address": sender, "gas": 500000}

        result = executor.execute_transaction(
            contract=mock_contract,
            method_name="request",
            method_args=method_args,
            tx_args=tx_args,
        )

        assert result == DEFAULT_TX_HASH
        mock_ledger_api.build_transaction.assert_called_once_with(
            contract_instance=mock_contract,
            method_name="request",
            method_args=method_args,
            tx_args=tx_args,
            raise_on_try=True,
        )
        mock_signer.send_transaction.assert_called_once_with({"raw": "tx"})


class TestClientExecutorGetters:
    """Tests for ClientExecutor getter methods."""

    def test_get_sender_address_returns_signer_address(
        self, mock_ledger_api: MagicMock
    ) -> None:
        """Test get_sender_address returns the EOA signer address."""
        mock_signer = create_mock_signer(address="0x" + "2" * 40)

        executor = ClientExecutor(mock_ledger_api, mock_signer)

        assert executor.get_sender_address() == mock_signer.address

    def test_get_nonce_returns_transaction_count(
        self, mock_ledger_api: MagicMock
    ) -> None:
        """Test get_nonce returns the on-chain transaction count."""
        mock_signer = create_mock_signer(address="0x" + "3" * 40)
        mock_ledger_api.api.eth.get_transaction_count.return_value = 5

        executor = ClientExecutor(mock_ledger_api, mock_signer)

        assert executor.get_nonce() == 5
        mock_ledger_api.api.eth.get_transaction_count.assert_called_once_with(
            mock_signer.address
        )


class TestAgentExecutorTransactionFailure:
    """Tests for AgentExecutor.execute_transaction failure path."""

    @patch("mech_client.domain.execution.agent_executor.SafeClient")
    def test_execute_transaction_send_failure_raises(
        self,
        mock_safe_client_cls: MagicMock,
        mock_ledger_api: MagicMock,
        mock_ethereum_client: MagicMock,
    ) -> None:
        """Test execute_transaction surfaces the Safe failure reason."""
        mock_signer = create_mock_signer()
        mock_ledger_api._chain_id = 100  # pylint: disable=protected-access

        mock_safe_client = MagicMock()
        mock_safe_client.get_nonce.return_value = 0
        mock_safe_client.send_transaction.side_effect = Exception(
            "Transaction execution fails"
        )
        mock_safe_client_cls.return_value = mock_safe_client

        executor = AgentExecutor(
            mock_ledger_api, mock_signer, "0x" + "b" * 40, mock_ethereum_client
        )

        mock_function = MagicMock()
        mock_function.build_transaction.return_value = {"data": "0xdeadbeef"}
        mock_contract = MagicMock()
        mock_contract.address = "0x" + "c" * 40
        mock_contract.functions.__getitem__.return_value.return_value = mock_function

        with pytest.raises(
            Exception,
            match="Failed to execute Safe transaction: Transaction execution fails",
        ):
            executor.execute_transaction(
                contract=mock_contract,
                method_name="foo",
                method_args={"x": 1},
                tx_args={"sender_address": "0x" + "1" * 40, "value": 0, "gas": 12345},
            )


class TestAgentExecutorGetters:
    """Tests for AgentExecutor getter methods."""

    @patch("mech_client.domain.execution.agent_executor.SafeClient")
    def test_get_sender_address_returns_safe_address(
        self,
        mock_safe_client_cls: MagicMock,
        mock_ledger_api: MagicMock,
        mock_ethereum_client: MagicMock,
    ) -> None:
        """Test get_sender_address returns the Safe multisig address."""
        mock_signer = create_mock_signer()
        safe_address = "0x" + "b" * 40

        executor = AgentExecutor(
            mock_ledger_api, mock_signer, safe_address, mock_ethereum_client
        )

        assert executor.get_sender_address() == safe_address

    @patch("mech_client.domain.execution.agent_executor.SafeClient")
    def test_get_nonce_returns_safe_nonce(
        self,
        mock_safe_client_cls: MagicMock,
        mock_ledger_api: MagicMock,
        mock_ethereum_client: MagicMock,
    ) -> None:
        """Test get_nonce returns the Safe nonce."""
        mock_signer = create_mock_signer()

        mock_safe_client = MagicMock()
        mock_safe_client.get_nonce.return_value = 3
        mock_safe_client_cls.return_value = mock_safe_client

        executor = AgentExecutor(
            mock_ledger_api, mock_signer, "0x" + "b" * 40, mock_ethereum_client
        )

        assert executor.get_nonce() == 3
        mock_safe_client.get_nonce.assert_called_with()
