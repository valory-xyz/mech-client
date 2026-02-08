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

"""Tests for deposit command."""

from unittest.mock import MagicMock, patch

from click.testing import CliRunner
from web3.constants import ADDRESS_ZERO

from mech_client.cli.commands.deposit_cmd import deposit


class TestDepositNativeCommand:
    """Tests for deposit native command."""

    @patch("mech_client.cli.commands.deposit_cmd.DepositService")
    @patch("mech_client.cli.commands.deposit_cmd.setup_wallet_command")
    @patch("mech_client.cli.commands.deposit_cmd.get_mech_config")
    def test_deposit_native_success(
        self,
        mock_get_config: MagicMock,
        mock_setup_wallet: MagicMock,
        mock_deposit_service: MagicMock,
    ) -> None:
        """Test successful native token deposit."""
        # Mock config with valid marketplace contract
        mock_config = MagicMock()
        mock_config.mech_marketplace_contract = "0x735FAAb1c4Ec41128c367AFb5c3baC73509f70bB"
        mock_get_config.return_value = mock_config

        # Mock wallet setup
        mock_wallet_ctx = MagicMock()
        mock_wallet_ctx.agent_mode = False
        mock_wallet_ctx.crypto = MagicMock()
        mock_wallet_ctx.safe_address = None
        mock_wallet_ctx.ethereum_client = None
        mock_setup_wallet.return_value = mock_wallet_ctx

        # Mock deposit service
        mock_service = MagicMock()
        mock_service.deposit_native.return_value = "0xabc123..."
        mock_deposit_service.return_value = mock_service

        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create a dummy key file
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                deposit,
                ["native", "1000000000000000000", "--chain-config", "gnosis", "--key", "key.txt"],
            )

            # Verify success
            assert result.exit_code == 0
            assert "Depositing 1000000000000000000 wei" in result.output
            assert "0xabc123" in result.output

            # Verify service was called correctly
            mock_deposit_service.assert_called_once()
            mock_service.deposit_native.assert_called_once_with(1000000000000000000)

    @patch("mech_client.cli.commands.deposit_cmd.DepositService")
    @patch("mech_client.cli.commands.deposit_cmd.setup_wallet_command")
    @patch("mech_client.cli.commands.deposit_cmd.get_mech_config")
    def test_deposit_native_all_supported_chains(
        self,
        mock_get_config: MagicMock,
        mock_setup_wallet: MagicMock,
        mock_deposit_service: MagicMock,
    ) -> None:
        """Test deposit native works for all supported chains."""
        chains = ["gnosis", "base", "polygon", "optimism"]

        runner = CliRunner()
        for chain in chains:
            # Mock config
            mock_config = MagicMock()
            mock_config.mech_marketplace_contract = "0x735FAAb1c4Ec41128c367AFb5c3baC73509f70bB"
            mock_get_config.return_value = mock_config

            # Mock wallet
            mock_wallet_ctx = MagicMock()
            mock_wallet_ctx.agent_mode = False
            mock_wallet_ctx.crypto = MagicMock()
            mock_setup_wallet.return_value = mock_wallet_ctx

            # Mock service
            mock_service = MagicMock()
            mock_service.deposit_native.return_value = f"0x{chain}..."
            mock_deposit_service.return_value = mock_service

            with runner.isolated_filesystem():
                with open("key.txt", "w") as f:
                    f.write("dummy_key")
                result = runner.invoke(
                    deposit,
                    ["native", "1000000", "--chain-config", chain, "--key", "key.txt"],
                )

                assert result.exit_code == 0, f"Failed for chain {chain}"
                assert "Depositing" in result.output

    @patch("mech_client.cli.commands.deposit_cmd.get_mech_config")
    def test_deposit_native_unsupported_chain(
        self, mock_get_config: MagicMock
    ) -> None:
        """Test deposit native fails for chain without marketplace."""
        # Mock config with ADDRESS_ZERO (no marketplace)
        mock_config = MagicMock()
        mock_config.mech_marketplace_contract = ADDRESS_ZERO
        mock_get_config.return_value = mock_config

        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create a dummy key file
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                deposit,
                ["native", "1000000", "--chain-config", "arbitrum", "--key", "key.txt"],
            )

        # Should fail with marketplace not supported error
        assert result.exit_code == 1
        assert "does not support marketplace deposits" in result.output

    def test_deposit_native_invalid_chain(self) -> None:
        """Test deposit native with invalid chain config."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create a dummy key file
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                deposit,
                ["native", "1000000", "--chain-config", "invalid", "--key", "key.txt"],
            )

        assert result.exit_code == 1
        assert "Invalid chain configuration" in result.output

    def test_deposit_native_missing_amount(self) -> None:
        """Test deposit native without amount argument."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("key.txt", "w") as f:
                f.write("dummy_key")
            result = runner.invoke(
                deposit, ["native", "--chain-config", "gnosis", "--key", "key.txt"]
            )

        # Should fail - amount is required
        assert result.exit_code != 0

    def test_deposit_native_invalid_amount_negative(self) -> None:
        """Test deposit native with negative amount."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create a dummy key file
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                deposit,
                ["native", "-1000", "--chain-config", "gnosis", "--key", "key.txt"],
            )

        # Click interprets negative numbers as options, resulting in exit code 2
        assert result.exit_code == 2

    def test_deposit_native_invalid_amount_zero(self) -> None:
        """Test deposit native with zero amount."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("key.txt", "w") as f:
                f.write("dummy_key")
            result = runner.invoke(
                deposit, ["native", "0", "--chain-config", "gnosis", "--key", "key.txt"]
            )

        assert result.exit_code == 1
        assert "must be a positive integer" in result.output.lower()

    def test_deposit_native_invalid_amount_non_numeric(self) -> None:
        """Test deposit native with non-numeric amount."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create a dummy key file
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                deposit,
                ["native", "abc", "--chain-config", "gnosis", "--key", "key.txt"],
            )

        assert result.exit_code == 1
        assert "must be a positive integer" in result.output.lower()

    def test_deposit_native_missing_chain_config(self) -> None:
        """Test deposit native without chain-config."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("key.txt", "w") as f:
                f.write("dummy_key")
            result = runner.invoke(deposit, ["native", "1000000", "--key", "key.txt"])

        # Should fail - chain-config is required
        assert result.exit_code != 0

    @patch("mech_client.cli.commands.deposit_cmd.DepositService")
    @patch("mech_client.cli.commands.deposit_cmd.setup_wallet_command")
    @patch("mech_client.cli.commands.deposit_cmd.get_mech_config")
    def test_deposit_native_service_failure(
        self,
        mock_get_config: MagicMock,
        mock_setup_wallet: MagicMock,
        mock_deposit_service: MagicMock,
    ) -> None:
        """Test deposit native when service fails."""
        # Mock config
        mock_config = MagicMock()
        mock_config.mech_marketplace_contract = "0x735FAAb1c4Ec41128c367AFb5c3baC73509f70bB"
        mock_get_config.return_value = mock_config

        # Mock wallet
        mock_wallet_ctx = MagicMock()
        mock_setup_wallet.return_value = mock_wallet_ctx

        # Mock service to raise error
        mock_service = MagicMock()
        mock_service.deposit_native.side_effect = Exception("Transaction failed")
        mock_deposit_service.return_value = mock_service

        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create a dummy key file
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                deposit,
                ["native", "1000000", "--chain-config", "gnosis", "--key", "key.txt"],
            )

        assert result.exit_code == 1
        assert "Transaction failed" in result.output

    @patch("mech_client.cli.commands.deposit_cmd.DepositService")
    @patch("mech_client.cli.commands.deposit_cmd.setup_wallet_command")
    @patch("mech_client.cli.commands.deposit_cmd.get_mech_config")
    def test_deposit_native_large_amount(
        self,
        mock_get_config: MagicMock,
        mock_setup_wallet: MagicMock,
        mock_deposit_service: MagicMock,
    ) -> None:
        """Test deposit native with very large amount."""
        # Mock config
        mock_config = MagicMock()
        mock_config.mech_marketplace_contract = "0x735FAAb1c4Ec41128c367AFb5c3baC73509f70bB"
        mock_get_config.return_value = mock_config

        # Mock wallet
        mock_wallet_ctx = MagicMock()
        mock_setup_wallet.return_value = mock_wallet_ctx

        # Mock service
        mock_service = MagicMock()
        mock_service.deposit_native.return_value = "0xabc..."
        mock_deposit_service.return_value = mock_service

        large_amount = "999999999999999999999999"
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create a dummy key file
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                deposit,
                ["native", large_amount, "--chain-config", "gnosis", "--key", "key.txt"],
            )

        assert result.exit_code == 0
        assert large_amount in result.output


class TestDepositTokenCommand:
    """Tests for deposit token command."""

    @patch("mech_client.cli.commands.deposit_cmd.DepositService")
    @patch("mech_client.cli.commands.deposit_cmd.setup_wallet_command")
    @patch("mech_client.cli.commands.deposit_cmd.get_mech_config")
    def test_deposit_token_olas_success(
        self,
        mock_get_config: MagicMock,
        mock_setup_wallet: MagicMock,
        mock_deposit_service: MagicMock,
    ) -> None:
        """Test successful OLAS token deposit."""
        # Mock config
        mock_config = MagicMock()
        mock_config.mech_marketplace_contract = "0x735FAAb1c4Ec41128c367AFb5c3baC73509f70bB"
        mock_get_config.return_value = mock_config

        # Mock wallet
        mock_wallet_ctx = MagicMock()
        mock_wallet_ctx.agent_mode = False
        mock_wallet_ctx.crypto = MagicMock()
        mock_setup_wallet.return_value = mock_wallet_ctx

        # Mock service
        mock_service = MagicMock()
        mock_service.deposit_token.return_value = "0xdef456..."
        mock_deposit_service.return_value = mock_service

        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create a dummy key file
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                deposit,
                [
                    "token",
                    "1000000000000000000",
                    "--chain-config",
                    "gnosis",
                    "--token-type",
                    "olas",
                    "--key",
                    "key.txt",
                ],
            )

        # Verify success
        assert result.exit_code == 0
        assert "Depositing 1000000000000000000 of OLAS tokens" in result.output
        assert "0xdef456" in result.output

        # Verify service was called correctly
        mock_service.deposit_token.assert_called_once_with(
            1000000000000000000, token_type="olas"
        )

    @patch("mech_client.cli.commands.deposit_cmd.DepositService")
    @patch("mech_client.cli.commands.deposit_cmd.setup_wallet_command")
    @patch("mech_client.cli.commands.deposit_cmd.get_mech_config")
    def test_deposit_token_usdc_success(
        self,
        mock_get_config: MagicMock,
        mock_setup_wallet: MagicMock,
        mock_deposit_service: MagicMock,
    ) -> None:
        """Test successful USDC token deposit."""
        # Mock config
        mock_config = MagicMock()
        mock_config.mech_marketplace_contract = "0x735FAAb1c4Ec41128c367AFb5c3baC73509f70bB"
        mock_get_config.return_value = mock_config

        # Mock wallet
        mock_wallet_ctx = MagicMock()
        mock_setup_wallet.return_value = mock_wallet_ctx

        # Mock service
        mock_service = MagicMock()
        mock_service.deposit_token.return_value = "0xghi789..."
        mock_deposit_service.return_value = mock_service

        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create a dummy key file
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                deposit,
                [
                    "token",
                    "1000000",
                    "--chain-config",
                    "base",
                    "--token-type",
                    "usdc",
                    "--key",
                    "key.txt",
                ],
            )

        # Verify success
        assert result.exit_code == 0
        assert "Depositing 1000000 of USDC tokens" in result.output
        assert "0xghi789" in result.output

        # Verify lowercase token type was used
        mock_service.deposit_token.assert_called_once_with(1000000, token_type="usdc")

    @patch("mech_client.cli.commands.deposit_cmd.DepositService")
    @patch("mech_client.cli.commands.deposit_cmd.setup_wallet_command")
    @patch("mech_client.cli.commands.deposit_cmd.get_mech_config")
    def test_deposit_token_requires_token_type(
        self,
        mock_get_config: MagicMock,
        mock_setup_wallet: MagicMock,
        mock_deposit_service: MagicMock,
    ) -> None:
        """Test deposit token requires --token-type to be specified."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create a dummy key file
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                deposit,
                ["token", "1000000", "--chain-config", "gnosis", "--key", "key.txt"],
            )

        # Should fail - token-type is required
        assert result.exit_code == 2  # Click usage error
        assert "Missing option '--token-type'" in result.output

    @patch("mech_client.cli.commands.deposit_cmd.DepositService")
    @patch("mech_client.cli.commands.deposit_cmd.setup_wallet_command")
    @patch("mech_client.cli.commands.deposit_cmd.get_mech_config")
    def test_deposit_token_case_insensitive(
        self,
        mock_get_config: MagicMock,
        mock_setup_wallet: MagicMock,
        mock_deposit_service: MagicMock,
    ) -> None:
        """Test deposit token accepts case-insensitive token types."""
        # Mock config
        mock_config = MagicMock()
        mock_config.mech_marketplace_contract = "0x735FAAb1c4Ec41128c367AFb5c3baC73509f70bB"
        mock_get_config.return_value = mock_config

        # Mock wallet
        mock_wallet_ctx = MagicMock()
        mock_setup_wallet.return_value = mock_wallet_ctx

        # Mock service
        mock_service = MagicMock()
        mock_service.deposit_token.return_value = "0xabc..."
        mock_deposit_service.return_value = mock_service

        # Test with uppercase
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create a dummy key file
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                deposit,
                [
                    "token",
                    "1000000",
                    "--chain-config",
                    "gnosis",
                    "--token-type",
                    "USDC",
                    "--key",
                    "key.txt",
                ],
            )

        # Should accept uppercase and convert to lowercase
        assert result.exit_code == 0
        mock_service.deposit_token.assert_called_with(1000000, token_type="usdc")

    def test_deposit_token_invalid_token_type(self) -> None:
        """Test deposit token with invalid token type."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create a dummy key file
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                deposit,
                [
                    "token",
                    "1000000",
                    "--chain-config",
                    "gnosis",
                    "--token-type",
                    "dai",
                    "--key",
                    "key.txt",
                ],
            )

        # Should fail - only olas and usdc are valid
        assert result.exit_code != 0
        assert "Invalid value" in result.output or "Choice" in result.output

    @patch("mech_client.cli.commands.deposit_cmd.get_mech_config")
    def test_deposit_token_unsupported_chain(
        self, mock_get_config: MagicMock
    ) -> None:
        """Test deposit token fails for chain without marketplace."""
        # Mock config with ADDRESS_ZERO
        mock_config = MagicMock()
        mock_config.mech_marketplace_contract = ADDRESS_ZERO
        mock_get_config.return_value = mock_config

        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create a dummy key file
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                deposit,
                [
                    "token",
                    "1000000",
                    "--chain-config",
                    "arbitrum",
                    "--token-type",
                    "olas",
                    "--key",
                    "key.txt",
                ],
            )

        assert result.exit_code == 1
        assert "does not support marketplace deposits" in result.output

    def test_deposit_token_invalid_amount(self) -> None:
        """Test deposit token with invalid amount."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create a dummy key file
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                deposit,
                [
                    "token",
                    "-100",
                    "--chain-config",
                    "gnosis",
                    "--token-type",
                    "olas",
                    "--key",
                    "key.txt",
                ],
            )

        # Click interprets negative numbers as options, resulting in exit code 2
        assert result.exit_code == 2

    def test_deposit_token_missing_amount(self) -> None:
        """Test deposit token without amount argument."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create a dummy key file
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                deposit,
                [
                    "token",
                    "--chain-config",
                    "gnosis",
                    "--token-type",
                    "olas",
                    "--key",
                    "key.txt",
                ],
            )

        # Should fail - amount is required
        assert result.exit_code != 0

    @patch("mech_client.cli.commands.deposit_cmd.DepositService")
    @patch("mech_client.cli.commands.deposit_cmd.setup_wallet_command")
    @patch("mech_client.cli.commands.deposit_cmd.get_mech_config")
    def test_deposit_token_service_failure(
        self,
        mock_get_config: MagicMock,
        mock_setup_wallet: MagicMock,
        mock_deposit_service: MagicMock,
    ) -> None:
        """Test deposit token when service fails."""
        # Mock config
        mock_config = MagicMock()
        mock_config.mech_marketplace_contract = "0x735FAAb1c4Ec41128c367AFb5c3baC73509f70bB"
        mock_get_config.return_value = mock_config

        # Mock wallet
        mock_wallet_ctx = MagicMock()
        mock_setup_wallet.return_value = mock_wallet_ctx

        # Mock service to raise error
        mock_service = MagicMock()
        mock_service.deposit_token.side_effect = Exception("Insufficient balance")
        mock_deposit_service.return_value = mock_service

        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create a dummy key file
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                deposit,
                [
                    "token",
                    "1000000",
                    "--chain-config",
                    "gnosis",
                    "--token-type",
                    "olas",
                    "--key",
                    "key.txt",
                ],
            )

        assert result.exit_code == 1
        assert "Insufficient balance" in result.output


class TestDepositCommandGroup:
    """Tests for deposit command group."""

    def test_deposit_help(self) -> None:
        """Test deposit help output."""
        runner = CliRunner()
        result = runner.invoke(deposit, ["--help"])

        assert result.exit_code == 0
        assert "Manage prepaid balance deposits" in result.output
        assert "native" in result.output
        assert "token" in result.output

    def test_deposit_native_help(self) -> None:
        """Test deposit native help output."""
        runner = CliRunner()
        result = runner.invoke(deposit, ["native", "--help"])

        assert result.exit_code == 0
        assert "Deposit native tokens" in result.output
        assert "amount" in result.output.lower()
        assert "chain-config" in result.output

    def test_deposit_token_help(self) -> None:
        """Test deposit token help output."""
        runner = CliRunner()
        result = runner.invoke(deposit, ["token", "--help"])

        assert result.exit_code == 0
        assert "Deposit ERC20 tokens" in result.output
        assert "token-type" in result.output
        assert "olas" in result.output.lower()
        assert "usdc" in result.output.lower()

    def test_deposit_no_subcommand(self) -> None:
        """Test deposit without subcommand shows help."""
        runner = CliRunner()
        result = runner.invoke(deposit, [])

        # Should show help or error about missing subcommand
        assert result.exit_code != 1 or "Usage:" in result.output

    def test_deposit_invalid_subcommand(self) -> None:
        """Test deposit with invalid subcommand."""
        runner = CliRunner()
        result = runner.invoke(deposit, ["invalid"])

        # Should fail with error
        assert result.exit_code != 0
