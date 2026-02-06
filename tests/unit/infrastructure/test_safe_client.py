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

"""Tests for Safe client."""

from unittest.mock import MagicMock, patch

import pytest
from hexbytes import HexBytes

from mech_client.infrastructure.blockchain.safe_client import (
    SafeClient,
    get_safe_nonce,
    send_safe_tx,
)


class TestSafeClientInitialization:
    """Tests for SafeClient initialization."""

    def test_initialization(self) -> None:
        """Test SafeClient initialization."""
        mock_eth_client = MagicMock()
        safe_address = "0x1234567890123456789012345678901234567890"

        client = SafeClient(mock_eth_client, safe_address)

        assert client.ethereum_client == mock_eth_client
        assert client.safe_address == safe_address
        assert client._safe is None  # pylint: disable=protected-access

    @patch("mech_client.infrastructure.blockchain.safe_client.Safe")
    def test_safe_property_lazy_loading(self, mock_safe_class: MagicMock) -> None:
        """Test Safe instance is lazy-loaded on first access."""
        mock_eth_client = MagicMock()
        safe_address = "0x1234567890123456789012345678901234567890"
        mock_safe_instance = MagicMock()
        mock_safe_class.return_value = mock_safe_instance

        client = SafeClient(mock_eth_client, safe_address)

        # Safe not loaded yet
        assert client._safe is None  # pylint: disable=protected-access

        # Access property triggers loading
        safe = client.safe

        # Verify Safe instance created
        mock_safe_class.assert_called_once_with(safe_address, mock_eth_client)
        assert safe == mock_safe_instance
        assert client._safe == mock_safe_instance  # pylint: disable=protected-access

    @patch("mech_client.infrastructure.blockchain.safe_client.Safe")
    def test_safe_property_cached(self, mock_safe_class: MagicMock) -> None:
        """Test Safe instance is cached after first access."""
        mock_eth_client = MagicMock()
        safe_address = "0x1234567890123456789012345678901234567890"
        mock_safe_instance = MagicMock()
        mock_safe_class.return_value = mock_safe_instance

        client = SafeClient(mock_eth_client, safe_address)

        # Access property twice
        safe1 = client.safe
        safe2 = client.safe

        # Safe constructor only called once
        mock_safe_class.assert_called_once()
        assert safe1 == safe2 == mock_safe_instance


class TestSafeClientSendTransaction:
    """Tests for send_transaction method."""

    @patch("mech_client.infrastructure.blockchain.safe_client.Safe")
    def test_send_transaction_success(self, mock_safe_class: MagicMock) -> None:
        """Test successful Safe transaction."""
        # Setup mocks
        mock_eth_client = MagicMock()
        safe_address = "0x1234567890123456789012345678901234567890"
        to_address = "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd"
        tx_data = "0x1234abcd"
        signer_key = "0xdeadbeef"
        value = 1000000000000000000

        # Mock Safe instance
        mock_safe_instance = MagicMock()
        mock_safe_class.return_value = mock_safe_instance

        # Mock gas estimation
        mock_safe_instance.estimate_tx_gas_with_safe.return_value = 100000

        # Mock transaction building
        mock_safe_tx = MagicMock()
        expected_tx_hash = HexBytes("0x" + "ff" * 32)
        mock_safe_tx.execute.return_value = (expected_tx_hash, None)
        mock_safe_instance.build_multisig_tx.return_value = mock_safe_tx

        # Create client and send transaction
        client = SafeClient(mock_eth_client, safe_address)
        tx_hash = client.send_transaction(
            to_address=to_address,
            tx_data=tx_data,
            signer_private_key=signer_key,
            value=value,
        )

        # Verify gas estimation called
        mock_safe_instance.estimate_tx_gas_with_safe.assert_called_once_with(
            to=to_address,
            value=value,
            data=bytes.fromhex(tx_data[2:]),
            operation=0,
        )

        # Verify transaction built
        mock_safe_instance.build_multisig_tx.assert_called_once()
        build_call = mock_safe_instance.build_multisig_tx.call_args
        assert build_call[1]["to"] == to_address
        assert build_call[1]["value"] == value
        assert build_call[1]["data"] == bytes.fromhex(tx_data[2:])
        assert build_call[1]["operation"] == 0
        assert build_call[1]["safe_tx_gas"] == 100000

        # Verify transaction signed and executed
        mock_safe_tx.sign.assert_called_once_with(signer_key)
        mock_safe_tx.execute.assert_called_once_with(signer_key)

        # Verify hash returned
        assert tx_hash == expected_tx_hash

    @patch("mech_client.infrastructure.blockchain.safe_client.Safe")
    def test_send_transaction_with_zero_value(
        self, mock_safe_class: MagicMock
    ) -> None:
        """Test Safe transaction with zero value (default)."""
        # Setup mocks
        mock_eth_client = MagicMock()
        safe_address = "0x1234567890123456789012345678901234567890"
        to_address = "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd"
        tx_data = "0x1234abcd"
        signer_key = "0xdeadbeef"

        # Mock Safe instance
        mock_safe_instance = MagicMock()
        mock_safe_class.return_value = mock_safe_instance
        mock_safe_instance.estimate_tx_gas_with_safe.return_value = 100000

        # Mock transaction
        mock_safe_tx = MagicMock()
        mock_safe_tx.execute.return_value = (HexBytes("0x" + "ff" * 32), None)
        mock_safe_instance.build_multisig_tx.return_value = mock_safe_tx

        # Send transaction without value parameter (defaults to 0)
        client = SafeClient(mock_eth_client, safe_address)
        tx_hash = client.send_transaction(
            to_address=to_address, tx_data=tx_data, signer_private_key=signer_key
        )

        # Verify value=0 used
        build_call = mock_safe_instance.build_multisig_tx.call_args
        assert build_call[1]["value"] == 0
        assert tx_hash is not None

    @patch("mech_client.infrastructure.blockchain.safe_client.Safe")
    def test_send_transaction_gas_estimation_failure(
        self, mock_safe_class: MagicMock
    ) -> None:
        """Test send_transaction handles gas estimation errors."""
        # Setup mocks
        mock_eth_client = MagicMock()
        safe_address = "0x1234567890123456789012345678901234567890"
        to_address = "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd"
        tx_data = "0x1234abcd"
        signer_key = "0xdeadbeef"

        # Mock Safe instance with gas estimation failure
        mock_safe_instance = MagicMock()
        mock_safe_class.return_value = mock_safe_instance
        mock_safe_instance.estimate_tx_gas_with_safe.side_effect = Exception(
            "Gas estimation failed"
        )

        # Send transaction
        client = SafeClient(mock_eth_client, safe_address)
        tx_hash = client.send_transaction(
            to_address=to_address, tx_data=tx_data, signer_private_key=signer_key
        )

        # Verify None returned on error
        assert tx_hash is None

    @patch("mech_client.infrastructure.blockchain.safe_client.Safe")
    def test_send_transaction_build_failure(self, mock_safe_class: MagicMock) -> None:
        """Test send_transaction handles transaction build errors."""
        # Setup mocks
        mock_eth_client = MagicMock()
        safe_address = "0x1234567890123456789012345678901234567890"
        to_address = "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd"
        tx_data = "0x1234abcd"
        signer_key = "0xdeadbeef"

        # Mock Safe instance
        mock_safe_instance = MagicMock()
        mock_safe_class.return_value = mock_safe_instance
        mock_safe_instance.estimate_tx_gas_with_safe.return_value = 100000
        mock_safe_instance.build_multisig_tx.side_effect = Exception(
            "Build transaction failed"
        )

        # Send transaction
        client = SafeClient(mock_eth_client, safe_address)
        tx_hash = client.send_transaction(
            to_address=to_address, tx_data=tx_data, signer_private_key=signer_key
        )

        # Verify None returned on error
        assert tx_hash is None

    @patch("mech_client.infrastructure.blockchain.safe_client.Safe")
    def test_send_transaction_sign_failure(self, mock_safe_class: MagicMock) -> None:
        """Test send_transaction handles signing errors."""
        # Setup mocks
        mock_eth_client = MagicMock()
        safe_address = "0x1234567890123456789012345678901234567890"
        to_address = "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd"
        tx_data = "0x1234abcd"
        signer_key = "0xdeadbeef"

        # Mock Safe instance
        mock_safe_instance = MagicMock()
        mock_safe_class.return_value = mock_safe_instance
        mock_safe_instance.estimate_tx_gas_with_safe.return_value = 100000

        # Mock transaction with sign failure
        mock_safe_tx = MagicMock()
        mock_safe_tx.sign.side_effect = Exception("Invalid private key")
        mock_safe_instance.build_multisig_tx.return_value = mock_safe_tx

        # Send transaction
        client = SafeClient(mock_eth_client, safe_address)
        tx_hash = client.send_transaction(
            to_address=to_address, tx_data=tx_data, signer_private_key=signer_key
        )

        # Verify None returned on error
        assert tx_hash is None

    @patch("mech_client.infrastructure.blockchain.safe_client.Safe")
    def test_send_transaction_execute_failure(
        self, mock_safe_class: MagicMock
    ) -> None:
        """Test send_transaction handles execution errors."""
        # Setup mocks
        mock_eth_client = MagicMock()
        safe_address = "0x1234567890123456789012345678901234567890"
        to_address = "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd"
        tx_data = "0x1234abcd"
        signer_key = "0xdeadbeef"

        # Mock Safe instance
        mock_safe_instance = MagicMock()
        mock_safe_class.return_value = mock_safe_instance
        mock_safe_instance.estimate_tx_gas_with_safe.return_value = 100000

        # Mock transaction with execute failure
        mock_safe_tx = MagicMock()
        mock_safe_tx.execute.side_effect = Exception("Execution reverted")
        mock_safe_instance.build_multisig_tx.return_value = mock_safe_tx

        # Send transaction
        client = SafeClient(mock_eth_client, safe_address)
        tx_hash = client.send_transaction(
            to_address=to_address, tx_data=tx_data, signer_private_key=signer_key
        )

        # Verify None returned on error
        assert tx_hash is None


class TestSafeClientGetNonce:
    """Tests for get_nonce method."""

    @patch("mech_client.infrastructure.blockchain.safe_client.Safe")
    def test_get_nonce_success(self, mock_safe_class: MagicMock) -> None:
        """Test successful nonce retrieval."""
        # Setup mocks
        mock_eth_client = MagicMock()
        safe_address = "0x1234567890123456789012345678901234567890"

        # Mock Safe instance
        mock_safe_instance = MagicMock()
        mock_safe_class.return_value = mock_safe_instance
        mock_safe_instance.retrieve_nonce.return_value = 42

        # Get nonce
        client = SafeClient(mock_eth_client, safe_address)
        nonce = client.get_nonce()

        # Verify
        mock_safe_instance.retrieve_nonce.assert_called_once()
        assert nonce == 42

    @patch("mech_client.infrastructure.blockchain.safe_client.Safe")
    def test_get_nonce_zero(self, mock_safe_class: MagicMock) -> None:
        """Test nonce retrieval for new Safe."""
        # Setup mocks
        mock_eth_client = MagicMock()
        safe_address = "0x1234567890123456789012345678901234567890"

        # Mock Safe instance with zero nonce
        mock_safe_instance = MagicMock()
        mock_safe_class.return_value = mock_safe_instance
        mock_safe_instance.retrieve_nonce.return_value = 0

        # Get nonce
        client = SafeClient(mock_eth_client, safe_address)
        nonce = client.get_nonce()

        # Verify
        assert nonce == 0


class TestSafeClientEstimateGas:
    """Tests for estimate_gas method."""

    @patch("mech_client.infrastructure.blockchain.safe_client.Safe")
    def test_estimate_gas_success(self, mock_safe_class: MagicMock) -> None:
        """Test successful gas estimation."""
        # Setup mocks
        mock_eth_client = MagicMock()
        safe_address = "0x1234567890123456789012345678901234567890"
        to_address = "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd"
        tx_data = "0x1234abcd"
        value = 1000000000000000000

        # Mock Safe instance
        mock_safe_instance = MagicMock()
        mock_safe_class.return_value = mock_safe_instance
        mock_safe_instance.estimate_tx_gas_with_safe.return_value = 150000

        # Estimate gas
        client = SafeClient(mock_eth_client, safe_address)
        gas = client.estimate_gas(to_address=to_address, tx_data=tx_data, value=value)

        # Verify
        mock_safe_instance.estimate_tx_gas_with_safe.assert_called_once_with(
            to=to_address,
            value=value,
            data=bytes.fromhex(tx_data[2:]),
            operation=0,
        )
        assert gas == 150000

    @patch("mech_client.infrastructure.blockchain.safe_client.Safe")
    def test_estimate_gas_with_zero_value(self, mock_safe_class: MagicMock) -> None:
        """Test gas estimation with zero value (default)."""
        # Setup mocks
        mock_eth_client = MagicMock()
        safe_address = "0x1234567890123456789012345678901234567890"
        to_address = "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd"
        tx_data = "0x1234abcd"

        # Mock Safe instance
        mock_safe_instance = MagicMock()
        mock_safe_class.return_value = mock_safe_instance
        mock_safe_instance.estimate_tx_gas_with_safe.return_value = 100000

        # Estimate gas without value parameter
        client = SafeClient(mock_eth_client, safe_address)
        gas = client.estimate_gas(to_address=to_address, tx_data=tx_data)

        # Verify value=0 used
        call_args = mock_safe_instance.estimate_tx_gas_with_safe.call_args
        assert call_args[1]["value"] == 0
        assert gas == 100000


class TestLegacyFunctions:
    """Tests for legacy functions."""

    @patch("mech_client.infrastructure.blockchain.safe_client.SafeClient")
    def test_send_safe_tx_legacy_function(
        self, mock_safe_client_class: MagicMock
    ) -> None:
        """Test send_safe_tx legacy function."""
        # Setup mocks
        mock_eth_client = MagicMock()
        tx_data = "0x1234abcd"
        to_adress = "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd"  # Note: typo preserved
        safe_address = "0x1234567890123456789012345678901234567890"
        signer_pkey = "0xdeadbeef"
        value = 1000000000000000000

        # Mock SafeClient instance
        mock_client = MagicMock()
        expected_tx_hash = HexBytes("0x" + "ff" * 32)
        mock_client.send_transaction.return_value = expected_tx_hash
        mock_safe_client_class.return_value = mock_client

        # Call legacy function
        tx_hash = send_safe_tx(
            ethereum_client=mock_eth_client,
            tx_data=tx_data,
            to_adress=to_adress,
            safe_address=safe_address,
            signer_pkey=signer_pkey,
            value=value,
        )

        # Verify SafeClient created
        mock_safe_client_class.assert_called_once_with(mock_eth_client, safe_address)

        # Verify send_transaction called
        mock_client.send_transaction.assert_called_once_with(
            to_address=to_adress,
            tx_data=tx_data,
            signer_private_key=signer_pkey,
            value=value,
        )

        # Verify hash returned
        assert tx_hash == expected_tx_hash

    @patch("mech_client.infrastructure.blockchain.safe_client.SafeClient")
    def test_send_safe_tx_with_zero_value(
        self, mock_safe_client_class: MagicMock
    ) -> None:
        """Test send_safe_tx legacy function with default value."""
        # Setup mocks
        mock_eth_client = MagicMock()
        tx_data = "0x1234abcd"
        to_adress = "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd"
        safe_address = "0x1234567890123456789012345678901234567890"
        signer_pkey = "0xdeadbeef"

        # Mock SafeClient instance
        mock_client = MagicMock()
        mock_client.send_transaction.return_value = HexBytes("0x" + "ff" * 32)
        mock_safe_client_class.return_value = mock_client

        # Call legacy function without value
        send_safe_tx(
            ethereum_client=mock_eth_client,
            tx_data=tx_data,
            to_adress=to_adress,
            safe_address=safe_address,
            signer_pkey=signer_pkey,
        )

        # Verify send_transaction called with value=0
        call_args = mock_client.send_transaction.call_args
        assert call_args[1]["value"] == 0

    @patch("mech_client.infrastructure.blockchain.safe_client.SafeClient")
    def test_get_safe_nonce_legacy_function(
        self, mock_safe_client_class: MagicMock
    ) -> None:
        """Test get_safe_nonce legacy function."""
        # Setup mocks
        mock_eth_client = MagicMock()
        safe_address = "0x1234567890123456789012345678901234567890"

        # Mock SafeClient instance
        mock_client = MagicMock()
        mock_client.get_nonce.return_value = 99
        mock_safe_client_class.return_value = mock_client

        # Call legacy function
        nonce = get_safe_nonce(
            ethereum_client=mock_eth_client, safe_address=safe_address
        )

        # Verify SafeClient created
        mock_safe_client_class.assert_called_once_with(mock_eth_client, safe_address)

        # Verify get_nonce called
        mock_client.get_nonce.assert_called_once()

        # Verify nonce returned
        assert nonce == 99
