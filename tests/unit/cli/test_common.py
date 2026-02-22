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

"""Tests for cli.common module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click import ClickException

from mech_client.cli.common import (
    WalletCommandContext,
    load_crypto_with_error_handling,
    setup_wallet_command,
)


class TestLoadCryptoWithErrorHandling:
    """Tests for load_crypto_with_error_handling function."""

    @patch("mech_client.cli.common.EthereumCrypto")
    def test_permission_error_raises_click_exception(
        self, mock_crypto_cls: MagicMock
    ) -> None:
        """Test that PermissionError raises ClickException with readable message."""
        mock_crypto_cls.side_effect = PermissionError("denied")

        with pytest.raises(ClickException) as exc_info:
            load_crypto_with_error_handling("/key")
        assert "Cannot read private key" in exc_info.value.format_message()

    @patch("mech_client.cli.common.EthereumCrypto")
    def test_decrypt_error_raises_click_exception(
        self, mock_crypto_cls: MagicMock
    ) -> None:
        """Test that ValueError containing 'password' raises ClickException with decrypt message."""
        mock_crypto_cls.side_effect = ValueError("password wrong")

        with pytest.raises(ClickException) as exc_info:
            load_crypto_with_error_handling("/key")
        assert "Failed to decrypt" in exc_info.value.format_message()

    @patch("mech_client.cli.common.EthereumCrypto")
    def test_mac_error_raises_click_exception(
        self, mock_crypto_cls: MagicMock
    ) -> None:
        """Test that ValueError containing 'mac' raises ClickException with decrypt message."""
        mock_crypto_cls.side_effect = ValueError("mac check failed")

        with pytest.raises(ClickException) as exc_info:
            load_crypto_with_error_handling("/key")
        assert "Failed to decrypt" in exc_info.value.format_message()

    @patch("mech_client.cli.common.EthereumCrypto")
    def test_generic_error_raises_click_exception(
        self, mock_crypto_cls: MagicMock
    ) -> None:
        """Test that a generic ValueError raises ClickException with generic message."""
        mock_crypto_cls.side_effect = ValueError("some other error")

        with pytest.raises(ClickException) as exc_info:
            load_crypto_with_error_handling("/key")
        assert "Error loading private key" in exc_info.value.format_message()

    @patch("mech_client.cli.common.EthereumCrypto")
    def test_success_returns_crypto(self, mock_crypto_cls: MagicMock) -> None:
        """Test that successful load returns the EthereumCrypto object."""
        mock_crypto_instance = MagicMock()
        mock_crypto_cls.return_value = mock_crypto_instance

        result = load_crypto_with_error_handling("/key")

        assert result is mock_crypto_instance
        mock_crypto_cls.assert_called_once_with(
            private_key_path="/key", password=None
        )


class TestSetupWalletCommandClientMode:
    """Tests for setup_wallet_command in client mode."""

    def test_client_mode_missing_key_raises(self) -> None:
        """Test that client mode raises ClickException when key file does not exist."""
        ctx = MagicMock()
        ctx.obj = {"client_mode": True}

        with pytest.raises(ClickException) as exc_info:
            setup_wallet_command(ctx, "gnosis", key="/nonexistent/key.txt")
        assert "does not exist" in exc_info.value.format_message()

    @patch("mech_client.cli.common.load_crypto_with_error_handling")
    @patch("mech_client.cli.common.Path")
    def test_client_mode_with_valid_key(
        self,
        mock_path_cls: MagicMock,
        mock_load_crypto: MagicMock,
    ) -> None:
        """Test that client mode with a valid key returns WalletCommandContext with agent_mode=False."""
        ctx = MagicMock()
        ctx.obj = {"client_mode": True}

        # Make Path.exists() return True for the key file
        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True
        mock_path_cls.return_value = mock_path_instance

        mock_crypto = MagicMock()
        mock_load_crypto.return_value = mock_crypto

        result = setup_wallet_command(ctx, "gnosis", key="/valid/key.txt")

        assert isinstance(result, WalletCommandContext)
        assert result.agent_mode is False
        assert result.crypto is mock_crypto


class TestSetupWalletCommandAgentMode:
    """Tests for setup_wallet_command in agent mode."""

    @patch("mech_client.cli.common.EthereumClient")
    @patch("mech_client.cli.common.get_mech_config")
    @patch("mech_client.cli.common.load_crypto_with_error_handling")
    @patch("mech_client.cli.common.validate_ethereum_address")
    @patch("mech_client.cli.common.fetch_agent_mode_keys")
    def test_agent_mode_success(
        self,
        mock_fetch_keys: MagicMock,
        mock_validate_addr: MagicMock,
        mock_load_crypto: MagicMock,
        mock_get_mech_config: MagicMock,
        mock_eth_client_cls: MagicMock,
    ) -> None:
        """Test that agent mode successfully returns WalletCommandContext with agent_mode=True."""
        ctx = MagicMock()
        ctx.obj = {"client_mode": False}

        safe_addr = "0x" + "a" * 40
        key_path = "/agent/key.txt"
        password = "secret"
        mock_fetch_keys.return_value = (safe_addr, key_path, password)

        mock_crypto = MagicMock()
        mock_load_crypto.return_value = mock_crypto

        mock_mech_config = MagicMock()
        mock_mech_config.ledger_config.address = "https://rpc.example.com"
        mock_get_mech_config.return_value = mock_mech_config

        mock_eth_client = MagicMock()
        mock_eth_client_cls.return_value = mock_eth_client

        result = setup_wallet_command(ctx, "gnosis", key=None)

        assert isinstance(result, WalletCommandContext)
        assert result.agent_mode is True
        assert result.safe_address == safe_addr
        assert result.crypto is mock_crypto
        assert result.ethereum_client is mock_eth_client

    @patch("mech_client.cli.common.fetch_agent_mode_keys")
    def test_agent_mode_empty_safe_raises(
        self,
        mock_fetch_keys: MagicMock,
    ) -> None:
        """Test that agent mode raises ClickException when safe address is empty."""
        ctx = MagicMock()
        ctx.obj = {"client_mode": False}

        # Return empty safe address
        mock_fetch_keys.return_value = ("", "/agent/key.txt", "password")

        with pytest.raises(ClickException) as exc_info:
            setup_wallet_command(ctx, "gnosis", key=None)
        assert "Cannot fetch safe or key data" in exc_info.value.format_message()
