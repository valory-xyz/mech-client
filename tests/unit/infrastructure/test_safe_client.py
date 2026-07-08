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

"""Tests for Safe client."""

from unittest.mock import MagicMock, patch

import pytest
from hexbytes import HexBytes

from mech_client.infrastructure.blockchain.safe_client import (
    OUTER_TX_GAS_MULTIPLIER,
    OUTER_TX_GAS_OVERHEAD_FLOOR,
    OUTER_TX_GAS_OVERHEAD_SHARE,
    SafeClient,
)

from tests.unit.helpers import create_mock_signer


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


class TestPreValidatedSignature:
    """Tests for build_pre_validated_signature."""

    def test_encoding_layout(self) -> None:
        """Test r=owner left-padded, s=0, v=1 layout."""
        owner = "0x" + "ab" * 20

        signature = SafeClient.build_pre_validated_signature(owner)

        assert len(signature) == 65
        # r: 12 zero bytes then the 20-byte owner address
        assert signature[:12] == b"\x00" * 12
        assert signature[12:32] == bytes.fromhex("ab" * 20)
        # s: zero
        assert signature[32:64] == b"\x00" * 32
        # v: 1 marks a pre-validated signature
        assert signature[64] == 1

    def test_accepts_unprefixed_address(self) -> None:
        """Test an address without 0x prefix encodes the same signature."""
        prefixed = SafeClient.build_pre_validated_signature("0x" + "ab" * 20)
        unprefixed = SafeClient.build_pre_validated_signature("ab" * 20)

        assert prefixed == unprefixed

    def test_rejects_non_hex_address(self) -> None:
        """Test a non-hex owner address raises a diagnostic ValueError."""
        with pytest.raises(ValueError, match="Invalid Safe owner address.*not hex"):
            SafeClient.build_pre_validated_signature("0xnot-an-address")

    def test_rejects_wrong_length_address(self) -> None:
        """Test a wrong-length owner address raises a diagnostic ValueError."""
        with pytest.raises(ValueError, match="expected 20 bytes, got 19"):
            SafeClient.build_pre_validated_signature("0x" + "ab" * 19)


class TestSafeClientSendTransaction:
    """Tests for send_transaction method."""

    @staticmethod
    def _make_safe_tx() -> MagicMock:
        """Build a mock SafeTx whose w3_tx echoes the given tx params.

        :return: Mock SafeTx
        """
        mock_safe_tx = MagicMock()
        mock_safe_tx.w3_tx.build_transaction.side_effect = lambda params: {
            **params,
            "to": "0x1234567890123456789012345678901234567890",
            "data": "0xouter",
        }
        return mock_safe_tx

    @patch("mech_client.infrastructure.blockchain.safe_client.Safe")
    def test_send_transaction_success(self, mock_safe_class: MagicMock) -> None:
        """Test successful Safe transaction via pre-validated signature."""
        # Setup mocks
        mock_eth_client = MagicMock()
        mock_eth_client.w3.eth.gas_price = 2_000_000_000
        safe_address = "0x1234567890123456789012345678901234567890"
        to_address = "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd"
        tx_data = "0x1234abcd"
        signer = create_mock_signer()
        value = 1000000000000000000

        # Mock Safe instance
        mock_safe_instance = MagicMock()
        mock_safe_class.return_value = mock_safe_instance

        # Mock gas estimation
        mock_safe_instance.estimate_tx_gas_with_safe.return_value = 100000

        # Mock transaction building
        mock_safe_tx = self._make_safe_tx()
        mock_safe_instance.build_multisig_tx.return_value = mock_safe_tx

        # Create client and send transaction
        client = SafeClient(mock_eth_client, safe_address)
        tx_hash = client.send_transaction(
            to_address=to_address,
            tx_data=tx_data,
            signer=signer,
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
        # safe_tx_gas=0 forwards all gas to the inner call (EIP-150 63/64 fix)
        assert build_call[1]["safe_tx_gas"] == 0

        # Verify pre-validated signature set (no ECDSA over the SafeTx hash)
        assert mock_safe_tx.signatures == SafeClient.build_pre_validated_signature(
            signer.address
        )
        mock_safe_tx.sign.assert_not_called()
        mock_safe_tx.execute.assert_not_called()

        # Verify the outer tx was built from the owner with an explicit gas
        # limit derived from the inner-call estimate (skips the outer
        # eth_estimateGas); for a small estimate the fixed overhead floor
        # applies
        expected_tx_gas = (
            int(100000 * OUTER_TX_GAS_MULTIPLIER) + OUTER_TX_GAS_OVERHEAD_FLOOR
        )
        outer_params = mock_safe_tx.w3_tx.build_transaction.call_args[0][0]
        assert outer_params["from"] == signer.address
        assert outer_params["gasPrice"] == 2_000_000_000
        assert outer_params["gas"] == expected_tx_gas

        # Verify the outer tx was submitted via the signer
        signer.send_transaction.assert_called_once()
        outer_tx = signer.send_transaction.call_args[0][0]
        assert outer_tx["gas"] == expected_tx_gas

        # Verify hash returned
        assert tx_hash == HexBytes("0x" + "ff" * 32)

    @patch("mech_client.infrastructure.blockchain.safe_client.Safe")
    def test_send_transaction_large_inner_call_scales_overhead(
        self, mock_safe_class: MagicMock
    ) -> None:
        """Test outer gas overhead scales proportionally for large inner calls."""
        mock_eth_client = MagicMock()
        safe_address = "0x1234567890123456789012345678901234567890"
        to_address = "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd"
        tx_data = "0x1234abcd"
        signer = create_mock_signer()

        # Inner estimate large enough that 5% exceeds the 250k floor
        large_estimate = 10_000_000
        mock_safe_instance = MagicMock()
        mock_safe_class.return_value = mock_safe_instance
        mock_safe_instance.estimate_tx_gas_with_safe.return_value = large_estimate

        mock_safe_instance.build_multisig_tx.return_value = self._make_safe_tx()

        client = SafeClient(mock_eth_client, safe_address)
        client.send_transaction(to_address=to_address, tx_data=tx_data, signer=signer)

        expected_tx_gas = int(large_estimate * OUTER_TX_GAS_MULTIPLIER) + int(
            large_estimate * OUTER_TX_GAS_OVERHEAD_SHARE
        )
        outer_tx = signer.send_transaction.call_args[0][0]
        assert outer_tx["gas"] == expected_tx_gas

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
        signer = create_mock_signer()

        # Mock Safe instance
        mock_safe_instance = MagicMock()
        mock_safe_class.return_value = mock_safe_instance
        mock_safe_instance.estimate_tx_gas_with_safe.return_value = 100000

        # Mock transaction
        mock_safe_instance.build_multisig_tx.return_value = self._make_safe_tx()

        # Send transaction without value parameter (defaults to 0)
        client = SafeClient(mock_eth_client, safe_address)
        tx_hash = client.send_transaction(
            to_address=to_address, tx_data=tx_data, signer=signer
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
        signer = create_mock_signer()

        # Mock Safe instance with gas estimation failure
        mock_safe_instance = MagicMock()
        mock_safe_class.return_value = mock_safe_instance
        mock_safe_instance.estimate_tx_gas_with_safe.side_effect = Exception(
            "Gas estimation failed"
        )

        # Send transaction and verify the error is surfaced
        client = SafeClient(mock_eth_client, safe_address)
        with pytest.raises(Exception, match="Gas estimation failed"):
            client.send_transaction(
                to_address=to_address, tx_data=tx_data, signer=signer
            )

    @patch("mech_client.infrastructure.blockchain.safe_client.Safe")
    def test_send_transaction_build_failure(self, mock_safe_class: MagicMock) -> None:
        """Test send_transaction handles transaction build errors."""
        # Setup mocks
        mock_eth_client = MagicMock()
        safe_address = "0x1234567890123456789012345678901234567890"
        to_address = "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd"
        tx_data = "0x1234abcd"
        signer = create_mock_signer()

        # Mock Safe instance
        mock_safe_instance = MagicMock()
        mock_safe_class.return_value = mock_safe_instance
        mock_safe_instance.estimate_tx_gas_with_safe.return_value = 100000
        mock_safe_instance.build_multisig_tx.side_effect = Exception(
            "Build transaction failed"
        )

        # Send transaction and verify the error is surfaced
        client = SafeClient(mock_eth_client, safe_address)
        with pytest.raises(Exception, match="Build transaction failed"):
            client.send_transaction(
                to_address=to_address, tx_data=tx_data, signer=signer
            )

    @patch("mech_client.infrastructure.blockchain.safe_client.Safe")
    def test_send_transaction_outer_build_failure(
        self, mock_safe_class: MagicMock
    ) -> None:
        """Test send_transaction handles outer execTransaction build errors."""
        # Setup mocks
        mock_eth_client = MagicMock()
        safe_address = "0x1234567890123456789012345678901234567890"
        to_address = "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd"
        tx_data = "0x1234abcd"
        signer = create_mock_signer()

        # Mock Safe instance
        mock_safe_instance = MagicMock()
        mock_safe_class.return_value = mock_safe_instance
        mock_safe_instance.estimate_tx_gas_with_safe.return_value = 100000

        # Mock outer tx build failure (e.g. estimation revert)
        mock_safe_tx = MagicMock()
        mock_safe_tx.w3_tx.build_transaction.side_effect = Exception(
            "Invalid owner provided"
        )
        mock_safe_instance.build_multisig_tx.return_value = mock_safe_tx

        # Send transaction and verify the error is surfaced
        client = SafeClient(mock_eth_client, safe_address)
        with pytest.raises(Exception, match="Invalid owner provided"):
            client.send_transaction(
                to_address=to_address, tx_data=tx_data, signer=signer
            )

    @patch("mech_client.infrastructure.blockchain.safe_client.Safe")
    def test_send_transaction_signer_failure(
        self, mock_safe_class: MagicMock
    ) -> None:
        """Test send_transaction surfaces signer submission errors."""
        # Setup mocks
        mock_eth_client = MagicMock()
        safe_address = "0x1234567890123456789012345678901234567890"
        to_address = "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd"
        tx_data = "0x1234abcd"
        signer = create_mock_signer()
        signer.send_transaction.side_effect = Exception("Signer unavailable")

        # Mock Safe instance
        mock_safe_instance = MagicMock()
        mock_safe_class.return_value = mock_safe_instance
        mock_safe_instance.estimate_tx_gas_with_safe.return_value = 100000
        mock_safe_instance.build_multisig_tx.return_value = self._make_safe_tx()

        # Send transaction and verify the error is surfaced
        client = SafeClient(mock_eth_client, safe_address)
        with pytest.raises(Exception, match="Signer unavailable"):
            client.send_transaction(
                to_address=to_address, tx_data=tx_data, signer=signer
            )


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
