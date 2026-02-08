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

"""Tests for setup command."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from mech_client.cli.commands.setup_cmd import setup as setup_command


class TestSetupCommand:
    """Tests for setup command."""

    @patch("mech_client.cli.commands.setup_cmd.SetupService")
    def test_setup_command_success_gnosis(
        self, mock_setup_service: MagicMock
    ) -> None:
        """Test successful setup for gnosis chain."""
        # Mock SetupService
        mock_service_instance = MagicMock()
        mock_setup_service.return_value = mock_service_instance

        runner = CliRunner()
        result = runner.invoke(setup_command, ["--chain-config", "gnosis"])

        # Verify command succeeded
        assert result.exit_code == 0
        assert "Setting up agent mode for gnosis" in result.output

        # Verify SetupService was called correctly
        mock_setup_service.assert_called_once()
        call_args = mock_setup_service.call_args[0]
        assert call_args[0] == "gnosis"
        assert isinstance(call_args[1], Path)
        assert "mech_client_gnosis.json" in str(call_args[1])

        # Verify setup and display_wallets were called
        mock_service_instance.setup.assert_called_once()
        mock_service_instance.display_wallets.assert_called_once()

    @patch("mech_client.cli.commands.setup_cmd.SetupService")
    def test_setup_command_success_base(self, mock_setup_service: MagicMock) -> None:
        """Test successful setup for base chain."""
        mock_service_instance = MagicMock()
        mock_setup_service.return_value = mock_service_instance

        runner = CliRunner()
        result = runner.invoke(setup_command, ["--chain-config", "base"])

        assert result.exit_code == 0
        assert "Setting up agent mode for base" in result.output

        # Verify correct template was used
        call_args = mock_setup_service.call_args[0]
        assert call_args[0] == "base"
        assert "mech_client_base.json" in str(call_args[1])

    @patch("mech_client.cli.commands.setup_cmd.SetupService")
    def test_setup_command_success_polygon(
        self, mock_setup_service: MagicMock
    ) -> None:
        """Test successful setup for polygon chain."""
        mock_service_instance = MagicMock()
        mock_setup_service.return_value = mock_service_instance

        runner = CliRunner()
        result = runner.invoke(setup_command, ["--chain-config", "polygon"])

        assert result.exit_code == 0
        assert "Setting up agent mode for polygon" in result.output

        call_args = mock_setup_service.call_args[0]
        assert call_args[0] == "polygon"
        assert "mech_client_polygon.json" in str(call_args[1])

    @patch("mech_client.cli.commands.setup_cmd.SetupService")
    def test_setup_command_success_optimism(
        self, mock_setup_service: MagicMock
    ) -> None:
        """Test successful setup for optimism chain."""
        mock_service_instance = MagicMock()
        mock_setup_service.return_value = mock_service_instance

        runner = CliRunner()
        result = runner.invoke(setup_command, ["--chain-config", "optimism"])

        assert result.exit_code == 0
        assert "Setting up agent mode for optimism" in result.output

        call_args = mock_setup_service.call_args[0]
        assert call_args[0] == "optimism"
        assert "mech_client_optimism.json" in str(call_args[1])

    def test_setup_command_missing_chain_config(self) -> None:
        """Test setup without required chain-config option."""
        runner = CliRunner()
        result = runner.invoke(setup_command, [])

        # Should fail - chain-config is required
        assert result.exit_code != 0
        assert "chain-config" in result.output.lower()

    def test_setup_command_invalid_chain_config(self) -> None:
        """Test setup with invalid chain config."""
        runner = CliRunner()
        result = runner.invoke(setup_command, ["--chain-config", "invalid_chain"])

        # Should fail with validation error
        assert result.exit_code == 1
        assert "Invalid chain configuration" in result.output

    def test_setup_command_unsupported_chain(self) -> None:
        """Test setup with valid but unsupported chain."""
        runner = CliRunner()
        # Arbitrum and Celo are in mechs.json but not supported for agent mode
        result = runner.invoke(setup_command, ["--chain-config", "arbitrum"])

        # Should fail with unsupported chain error
        assert result.exit_code == 1
        assert "Agent mode not supported" in result.output
        assert "arbitrum" in result.output.lower()

    @patch("mech_client.cli.commands.setup_cmd.SetupService")
    def test_setup_command_service_setup_fails(
        self, mock_setup_service: MagicMock
    ) -> None:
        """Test setup when SetupService.setup() fails."""
        # Mock setup to raise an error
        mock_service_instance = MagicMock()
        mock_service_instance.setup.side_effect = Exception("Setup failed")
        mock_setup_service.return_value = mock_service_instance

        runner = CliRunner()
        result = runner.invoke(setup_command, ["--chain-config", "gnosis"])

        # Should fail with error
        assert result.exit_code == 1
        assert "Setup failed" in result.output

    @patch("mech_client.cli.commands.setup_cmd.SetupService")
    def test_setup_command_display_wallets_fails(
        self, mock_setup_service: MagicMock
    ) -> None:
        """Test setup when display_wallets() fails."""
        # Mock display_wallets to raise an error
        mock_service_instance = MagicMock()
        mock_service_instance.display_wallets.side_effect = Exception(
            "Failed to display wallets"
        )
        mock_setup_service.return_value = mock_service_instance

        runner = CliRunner()
        result = runner.invoke(setup_command, ["--chain-config", "gnosis"])

        # Should fail with error
        assert result.exit_code == 1
        assert "Failed to display wallets" in result.output

    @patch("mech_client.cli.commands.setup_cmd.SetupService")
    def test_setup_command_all_supported_chains(
        self, mock_setup_service: MagicMock
    ) -> None:
        """Test setup works for all supported chains."""
        supported_chains = ["gnosis", "base", "polygon", "optimism"]

        for chain in supported_chains:
            mock_service_instance = MagicMock()
            mock_setup_service.return_value = mock_service_instance

            runner = CliRunner()
            result = runner.invoke(setup_command, ["--chain-config", chain])

            # Should succeed for all supported chains
            assert result.exit_code == 0, f"Failed for chain {chain}"
            assert f"Setting up agent mode for {chain}" in result.output

    def test_setup_command_help(self) -> None:
        """Test setup help output."""
        runner = CliRunner()
        result = runner.invoke(setup_command, ["--help"])

        assert result.exit_code == 0
        assert "Setup agent mode" in result.output
        assert "chain-config" in result.output
        assert "Safe multisig" in result.output

    def test_setup_command_uppercase_chain_fails(self) -> None:
        """Test setup with uppercase chain config fails."""
        runner = CliRunner()
        result = runner.invoke(setup_command, ["--chain-config", "GNOSIS"])

        # Should fail - validator requires exact lowercase match
        assert result.exit_code == 1
        assert "Invalid chain configuration" in result.output

    @patch("mech_client.cli.commands.setup_cmd.SetupService")
    def test_setup_command_template_paths_exist(
        self, mock_setup_service: MagicMock
    ) -> None:
        """Test that template paths point to existing files."""
        from mech_client.cli.commands.setup_cmd import CHAIN_TO_TEMPLATE

        # Verify all templates exist
        for chain, template_path in CHAIN_TO_TEMPLATE.items():
            assert template_path.exists(), f"Template not found for {chain}: {template_path}"
            assert template_path.suffix == ".json", f"Template should be JSON for {chain}"

    @patch("mech_client.cli.commands.setup_cmd.SetupService")
    def test_setup_command_creates_service_with_correct_params(
        self, mock_setup_service: MagicMock
    ) -> None:
        """Test that SetupService is created with correct parameters."""
        mock_service_instance = MagicMock()
        mock_setup_service.return_value = mock_service_instance

        runner = CliRunner()
        result = runner.invoke(setup_command, ["--chain-config", "polygon"])

        assert result.exit_code == 0

        # Verify SetupService constructor was called with correct args
        mock_setup_service.assert_called_once()
        chain_arg, template_arg = mock_setup_service.call_args[0]

        assert chain_arg == "polygon"
        assert isinstance(template_arg, Path)
        assert template_arg.name == "mech_client_polygon.json"
        assert template_arg.exists()


class TestSetupCommandEdgeCases:
    """Tests for edge cases in setup command."""

    def test_setup_command_with_extra_args(self) -> None:
        """Test setup with unexpected extra arguments."""
        runner = CliRunner()
        result = runner.invoke(
            setup_command, ["--chain-config", "gnosis", "extra_argument"]
        )

        # Should fail - no positional arguments expected
        assert result.exit_code != 0

    @patch("mech_client.cli.commands.setup_cmd.SetupService")
    def test_setup_command_empty_chain_config(
        self, mock_setup_service: MagicMock
    ) -> None:
        """Test setup with empty chain config string."""
        runner = CliRunner()
        result = runner.invoke(setup_command, ["--chain-config", ""])

        # Should fail with validation error
        assert result.exit_code == 1
        assert "Invalid chain configuration" in result.output

    @patch("mech_client.cli.commands.setup_cmd.SetupService")
    def test_setup_command_special_chars_in_chain(
        self, mock_setup_service: MagicMock
    ) -> None:
        """Test setup with special characters in chain config."""
        runner = CliRunner()
        result = runner.invoke(setup_command, ["--chain-config", "gnosis@#$"])

        # Should fail with validation error
        assert result.exit_code == 1
        assert "Invalid chain configuration" in result.output

    def test_setup_command_whitespace_in_chain_fails(self) -> None:
        """Test setup with whitespace in chain config fails."""
        runner = CliRunner()
        result = runner.invoke(setup_command, ["--chain-config", " gnosis "])

        # Should fail - validator requires exact match without whitespace
        assert result.exit_code == 1
        assert "Invalid chain configuration" in result.output

    @patch("mech_client.cli.commands.setup_cmd.SetupService")
    def test_setup_command_multiple_chain_configs(
        self, mock_setup_service: MagicMock
    ) -> None:
        """Test setup with multiple chain-config options."""
        mock_service_instance = MagicMock()
        mock_setup_service.return_value = mock_service_instance

        runner = CliRunner()
        result = runner.invoke(
            setup_command, ["--chain-config", "gnosis", "--chain-config", "base"]
        )

        # Click will use the last value - should succeed with 'base'
        assert result.exit_code == 0
        assert "Setting up agent mode for base" in result.output
