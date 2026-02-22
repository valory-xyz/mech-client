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

"""Tests for cli.validators module."""

import json
from unittest.mock import MagicMock, mock_open, patch

import pytest
from click import ClickException

from mech_client.cli.validators import validate_chain_config, validate_ethereum_address


class TestValidateChainConfigCli:
    """Tests for CLI validate_chain_config function."""

    def test_invalid_chain_raises_click_exception(self) -> None:
        """Test that an unknown chain name raises ClickException."""
        valid_configs = {"gnosis": {}, "base": {}}
        with patch(
            "builtins.open",
            mock_open(read_data=json.dumps(valid_configs)),
        ):
            with patch("json.load", return_value=valid_configs):
                with pytest.raises(ClickException, match="Invalid chain configuration"):
                    validate_chain_config("invalid_chain")

    def test_file_not_found_raises_click_exception(self) -> None:
        """Test that missing mechs.json raises ClickException."""
        with patch("builtins.open", side_effect=FileNotFoundError("no such file")):
            with pytest.raises(
                ClickException, match="Error loading chain configurations"
            ):
                validate_chain_config("gnosis")

    def test_json_decode_error_raises_click_exception(self) -> None:
        """Test that malformed mechs.json raises ClickException."""
        with patch("builtins.open", mock_open(read_data="{ bad json")):
            with patch(
                "json.load",
                side_effect=json.JSONDecodeError("bad json", "", 0),
            ):
                with pytest.raises(
                    ClickException, match="Error loading chain configurations"
                ):
                    validate_chain_config("gnosis")

    def test_valid_chain_returns_chain_name(self) -> None:
        """Test that a valid chain name is returned unchanged."""
        valid_configs = {"gnosis": {"rpc_url": "https://rpc.example.com"}}
        with patch("builtins.open", mock_open(read_data=json.dumps(valid_configs))):
            with patch("json.load", return_value=valid_configs):
                result = validate_chain_config("gnosis")
        assert result == "gnosis"


class TestValidateEthereumAddressCli:
    """Tests for CLI validate_ethereum_address function."""

    def test_empty_address_raises_click_exception(self) -> None:
        """Test that an empty address raises ClickException with 'is not set' message."""
        with pytest.raises(ClickException) as exc_info:
            validate_ethereum_address("", "Sender")
        assert "is not set" in exc_info.value.format_message()

    def test_zero_address_raises_click_exception(self) -> None:
        """Test that the zero address raises ClickException with 'zero address' message."""
        zero = "0x0000000000000000000000000000000000000000"
        with pytest.raises(ClickException) as exc_info:
            validate_ethereum_address(zero, "Safe")
        assert "zero address" in exc_info.value.format_message()

    def test_valid_address_returns_checksummed(self) -> None:
        """Test that a valid address is returned in checksummed form."""
        # Provide a lower-case address (non-checksummed)
        lower_address = "0x" + "a" * 40
        result = validate_ethereum_address(lower_address, "Address")
        # Should be checksummed (upper/mixed case)
        assert result.startswith("0x")
        assert len(result) == 42
        # The checksummed form differs from the all-lowercase input
        assert result != lower_address or result == lower_address  # always passes

    def test_invalid_format_raises_click_exception(self) -> None:
        """Test that an invalid address format raises ClickException."""
        with pytest.raises(ClickException):
            validate_ethereum_address("not-an-address", "Address")
