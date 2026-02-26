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

"""Tests for ABI loader."""

from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from mech_client.infrastructure.blockchain.abi_loader import get_abi, get_abi_path


class TestGetAbi:
    """Tests for get_abi function."""

    @patch("builtins.open", new_callable=mock_open, read_data='[{"name": "request", "type": "function"}]')
    def test_load_abi_success(self, mock_file: mock_open) -> None:
        """Test successfully loading ABI from file."""
        abi = get_abi("MechMarketplace.json")

        assert isinstance(abi, list)
        assert len(abi) == 1
        assert abi[0]["name"] == "request"
        assert abi[0]["type"] == "function"
        mock_file.assert_called_once()

    @patch("builtins.open", new_callable=mock_open, read_data='[]')
    def test_load_empty_abi(self, mock_file: mock_open) -> None:
        """Test loading empty ABI returns empty list."""
        abi = get_abi("EmptyContract.json")

        assert isinstance(abi, list)
        assert len(abi) == 0

    @patch("builtins.open", side_effect=FileNotFoundError())
    def test_missing_abi_file_raises_error(self, mock_file: mock_open) -> None:
        """Test that missing ABI file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            get_abi("NonExistent.json")

    @patch("builtins.open", new_callable=mock_open, read_data='invalid json')
    def test_malformed_abi_raises_error(self, mock_file: mock_open) -> None:
        """Test that malformed JSON raises JSONDecodeError."""
        with pytest.raises(Exception):  # JSONDecodeError
            get_abi("Malformed.json")

    @patch("builtins.open", new_callable=mock_open, read_data='[{"inputs": [], "name": "approve", "outputs": [{"type": "bool"}], "stateMutability": "nonpayable", "type": "function"}]')
    def test_load_complex_abi(self, mock_file: mock_open) -> None:
        """Test loading ABI with complex structure."""
        abi = get_abi("IToken.json")

        assert isinstance(abi, list)
        assert len(abi) == 1
        assert abi[0]["name"] == "approve"
        assert abi[0]["type"] == "function"
        assert abi[0]["stateMutability"] == "nonpayable"
        assert "inputs" in abi[0]
        assert "outputs" in abi[0]


class TestGetAbiPath:
    """Tests for get_abi_path function."""

    @patch("mech_client.infrastructure.blockchain.abi_loader.ABI_DIR_PATH", Path("/mock/abi/path"))
    def test_get_abi_path_returns_correct_path(self) -> None:
        """Test that get_abi_path returns correct full path."""
        result = get_abi_path("MechMarketplace.json")

        assert isinstance(result, Path)
        assert result == Path("/mock/abi/path") / "MechMarketplace.json"

    @patch("mech_client.infrastructure.blockchain.abi_loader.ABI_DIR_PATH", Path("/another/path"))
    def test_get_abi_path_with_different_contract(self) -> None:
        """Test get_abi_path with different contract name."""
        result = get_abi_path("IToken.json")

        assert isinstance(result, Path)
        assert result == Path("/another/path") / "IToken.json"
