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

"""Tests for contract utilities."""

from unittest.mock import MagicMock

from mech_client.infrastructure.blockchain.contracts import get_contract


class TestGetContract:
    """Tests for get_contract function."""

    def test_get_contract_creates_instance(
        self, mock_ledger_api: MagicMock
    ) -> None:
        """Test that get_contract creates contract instance."""
        contract_address = "0x1234567890123456789012345678901234567890"
        abi = [{"name": "request", "type": "function"}]

        mock_contract = MagicMock()
        mock_ledger_api.get_contract_instance.return_value = mock_contract

        result = get_contract(contract_address, abi, mock_ledger_api)

        assert result == mock_contract
        mock_ledger_api.get_contract_instance.assert_called_once_with(
            {"abi": abi, "bytecode": "0x"},
            contract_address,
        )

    def test_get_contract_with_empty_abi(
        self, mock_ledger_api: MagicMock
    ) -> None:
        """Test get_contract works with empty ABI."""
        contract_address = "0x1234567890123456789012345678901234567890"
        abi = []

        mock_contract = MagicMock()
        mock_ledger_api.get_contract_instance.return_value = mock_contract

        result = get_contract(contract_address, abi, mock_ledger_api)

        assert result == mock_contract
        mock_ledger_api.get_contract_instance.assert_called_once()

    def test_get_contract_with_complex_abi(
        self, mock_ledger_api: MagicMock
    ) -> None:
        """Test get_contract with complex ABI structure."""
        contract_address = "0x1234567890123456789012345678901234567890"
        abi = [
            {
                "inputs": [{"name": "amount", "type": "uint256"}],
                "name": "deposit",
                "outputs": [],
                "stateMutability": "payable",
                "type": "function",
            },
            {
                "anonymous": False,
                "inputs": [{"indexed": True, "name": "sender", "type": "address"}],
                "name": "Deposit",
                "type": "event",
            },
        ]

        mock_contract = MagicMock()
        mock_ledger_api.get_contract_instance.return_value = mock_contract

        result = get_contract(contract_address, abi, mock_ledger_api)

        assert result == mock_contract
        call_args = mock_ledger_api.get_contract_instance.call_args
        assert call_args[0][0]["abi"] == abi
        assert call_args[0][0]["bytecode"] == "0x"
        assert call_args[0][1] == contract_address
