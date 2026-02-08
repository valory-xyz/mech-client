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

"""Tests for tool command."""

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from mech_client.cli.commands.tool_cmd import tool


class TestToolListCommand:
    """Tests for tool list command."""

    @patch("mech_client.cli.commands.tool_cmd.ToolService")
    def test_list_command_success(self, mock_tool_service: MagicMock) -> None:
        """Test successful tool list retrieval."""
        # Mock ToolService response
        mock_instance = mock_tool_service.return_value
        mock_result = MagicMock()
        mock_result.tools = [
            MagicMock(
                tool_name="openai-gpt-4o-2024-08-06",
                unique_identifier="2182-openai-gpt-4o-2024-08-06",
            ),
            MagicMock(
                tool_name="prediction-online",
                unique_identifier="2182-prediction-online",
            ),
            MagicMock(
                tool_name="superforcaster", unique_identifier="2182-superforcaster"
            ),
        ]
        mock_instance.get_tools_info.return_value = mock_result

        runner = CliRunner()
        result = runner.invoke(tool, ["list", "2182", "--chain-config", "gnosis"])

        # Verify command succeeded
        assert result.exit_code == 0
        assert "openai-gpt-4o-2024-08-06" in result.output
        assert "2182-openai-gpt-4o-2024-08-06" in result.output
        assert "prediction-online" in result.output
        assert "superforcaster" in result.output

        # Verify service was called correctly
        mock_tool_service.assert_called_once_with("gnosis")
        mock_instance.get_tools_info.assert_called_once_with(2182)

    @patch("mech_client.cli.commands.tool_cmd.ToolService")
    def test_list_command_empty_tools(self, mock_tool_service: MagicMock) -> None:
        """Test tool list with no tools available."""
        # Mock empty tools response
        mock_instance = mock_tool_service.return_value
        mock_result = MagicMock()
        mock_result.tools = []
        mock_instance.get_tools_info.return_value = mock_result

        runner = CliRunner()
        result = runner.invoke(tool, ["list", "2182", "--chain-config", "gnosis"])

        # Should succeed but show empty table
        assert result.exit_code == 0
        assert "Tool Name" in result.output
        assert "Unique Identifier" in result.output

    def test_list_command_invalid_agent_id_negative(self) -> None:
        """Test tool list with negative agent ID."""
        runner = CliRunner()
        result = runner.invoke(tool, ["list", "-1", "--chain-config", "gnosis"])

        # Should fail - negative IDs are not valid options
        assert result.exit_code != 0

    @patch("mech_client.cli.commands.tool_cmd.ToolService")
    def test_list_command_invalid_agent_id_zero(
        self, mock_tool_service: MagicMock
    ) -> None:
        """Test tool list with zero agent ID."""
        # Mock service to raise error for zero
        mock_instance = mock_tool_service.return_value
        mock_instance.get_tools_info.side_effect = Exception("No tools found")

        runner = CliRunner()
        result = runner.invoke(tool, ["list", "0", "--chain-config", "gnosis"])

        # Should fail with error
        assert result.exit_code == 1

    def test_list_command_invalid_chain_config(self) -> None:
        """Test tool list with invalid chain config."""
        runner = CliRunner()
        result = runner.invoke(tool, ["list", "2182", "--chain-config", "invalid"])

        # Should fail with validation error
        assert result.exit_code == 1
        assert "Invalid chain configuration" in result.output

    def test_list_command_missing_chain_config(self) -> None:
        """Test tool list without required chain-config option."""
        runner = CliRunner()
        result = runner.invoke(tool, ["list", "2182"])

        # Should fail - chain-config is required
        assert result.exit_code != 0
        assert "chain-config" in result.output.lower()

    @patch("mech_client.cli.commands.tool_cmd.ToolService")
    def test_list_command_all_supported_chains(
        self, mock_tool_service: MagicMock
    ) -> None:
        """Test tool list works for all supported chains."""
        chains = ["gnosis", "base", "polygon", "optimism"]

        for chain in chains:
            # Mock response
            mock_instance = mock_tool_service.return_value
            mock_result = MagicMock()
            mock_result.tools = [
                MagicMock(tool_name="tool1", unique_identifier=f"1-tool1"),
            ]
            mock_instance.get_tools_info.return_value = mock_result

            runner = CliRunner()
            result = runner.invoke(tool, ["list", "1", "--chain-config", chain])

            # Should succeed for all chains
            assert result.exit_code == 0, f"Failed for chain {chain}"
            assert "tool1" in result.output


class TestToolDescribeCommand:
    """Tests for tool describe command."""

    @patch("mech_client.cli.commands.tool_cmd.ToolService")
    def test_describe_command_success(self, mock_tool_service: MagicMock) -> None:
        """Test successful tool description retrieval."""
        # Mock ToolService response
        mock_instance = mock_tool_service.return_value
        mock_instance.get_description.return_value = (
            "A tool that runs a prompt against the OpenAI API hosted in TEE."
        )

        runner = CliRunner()
        result = runner.invoke(
            tool,
            ["describe", "2182-openai-gpt-4o-2024-08-06", "--chain-config", "gnosis"],
        )

        # Verify command succeeded
        assert result.exit_code == 0
        assert "Description for tool 2182-openai-gpt-4o-2024-08-06" in result.output
        assert "OpenAI API hosted in TEE" in result.output

        # Verify service was called correctly
        mock_tool_service.assert_called_once_with("gnosis")
        mock_instance.get_description.assert_called_once_with(
            "2182-openai-gpt-4o-2024-08-06"
        )

    def test_describe_command_invalid_tool_id_format(self) -> None:
        """Test tool describe with invalid tool ID format (no dash)."""
        runner = CliRunner()
        result = runner.invoke(
            tool, ["describe", "invalidtoolid", "--chain-config", "gnosis"]
        )

        # Should fail with validation error
        assert result.exit_code == 1
        assert "Invalid" in result.output or "must" in result.output.lower()

    def test_describe_command_invalid_service_id(self) -> None:
        """Test tool describe with non-numeric service ID."""
        runner = CliRunner()
        result = runner.invoke(
            tool, ["describe", "abc-tool-name", "--chain-config", "gnosis"]
        )

        # Should fail with validation error
        assert result.exit_code == 1
        assert "Invalid service ID" in result.output or "integer" in result.output

    @patch("mech_client.cli.commands.tool_cmd.ToolService")
    def test_describe_command_nonexistent_tool(
        self, mock_tool_service: MagicMock
    ) -> None:
        """Test tool describe with non-existent tool."""
        # Mock service to raise error
        mock_instance = mock_tool_service.return_value
        mock_instance.get_description.side_effect = Exception("Tool not found")

        runner = CliRunner()
        result = runner.invoke(
            tool, ["describe", "99999-nonexistent-tool", "--chain-config", "gnosis"]
        )

        # Should fail with error
        assert result.exit_code == 1

    def test_describe_command_missing_chain_config(self) -> None:
        """Test tool describe without required chain-config option."""
        runner = CliRunner()
        result = runner.invoke(tool, ["describe", "2182-tool"])

        # Should fail - chain-config is required
        assert result.exit_code != 0


class TestToolSchemaCommand:
    """Tests for tool schema command."""

    @patch("mech_client.cli.commands.tool_cmd.ToolService")
    def test_schema_command_success(self, mock_tool_service: MagicMock) -> None:
        """Test successful tool schema retrieval."""
        # Mock ToolService response
        mock_instance = mock_tool_service.return_value
        mock_instance.get_schema.return_value = {
            "name": "openai-gpt-4o-2024-08-06",
            "description": "A tool that runs a prompt against the OpenAI API hosted in TEE.",
            "input": {"type": "text", "description": "The text to make a prediction on"},
            "output": {"type": "text", "description": "The model's response"},
        }
        mock_instance.format_input_schema.return_value = [
            ["type", "text"],
            ["description", "The text to make a prediction on"],
        ]
        mock_instance.format_output_schema.return_value = [
            ["type", "text", "The model's response"],
        ]

        runner = CliRunner()
        result = runner.invoke(
            tool,
            ["schema", "2182-openai-gpt-4o-2024-08-06", "--chain-config", "gnosis"],
        )

        # Verify command succeeded
        assert result.exit_code == 0
        assert "Tool Details:" in result.output
        assert "openai-gpt-4o-2024-08-06" in result.output
        assert "Input Schema:" in result.output
        assert "Output Schema:" in result.output
        assert "text" in result.output

        # Verify service was called correctly
        mock_tool_service.assert_called_once_with("gnosis")
        mock_instance.get_schema.assert_called_once_with(
            "2182-openai-gpt-4o-2024-08-06"
        )

    @patch("mech_client.cli.commands.tool_cmd.ToolService")
    def test_schema_command_empty_output_schema(
        self, mock_tool_service: MagicMock
    ) -> None:
        """Test tool schema with empty output schema."""
        # Mock response with empty output
        mock_instance = mock_tool_service.return_value
        mock_instance.get_schema.return_value = {
            "name": "test-tool",
            "description": "Test tool",
            "input": {"type": "text"},
            "output": {},
        }
        mock_instance.format_input_schema.return_value = [["type", "text"]]
        mock_instance.format_output_schema.return_value = []

        runner = CliRunner()
        result = runner.invoke(
            tool, ["schema", "2182-test-tool", "--chain-config", "gnosis"]
        )

        # Should succeed even with empty output schema
        assert result.exit_code == 0
        assert "Output Schema:" in result.output

    def test_schema_command_invalid_tool_id(self) -> None:
        """Test tool schema with invalid tool ID format."""
        runner = CliRunner()
        result = runner.invoke(
            tool, ["schema", "invalid-format", "--chain-config", "gnosis"]
        )

        # Should fail with validation error
        assert result.exit_code == 1

    @patch("mech_client.cli.commands.tool_cmd.ToolService")
    def test_schema_command_service_error(self, mock_tool_service: MagicMock) -> None:
        """Test tool schema with service error."""
        # Mock service to raise error
        mock_instance = mock_tool_service.return_value
        mock_instance.get_schema.side_effect = Exception("Failed to fetch schema")

        runner = CliRunner()
        result = runner.invoke(
            tool, ["schema", "2182-test-tool", "--chain-config", "gnosis"]
        )

        # Should fail with error
        assert result.exit_code == 1

    @patch("mech_client.cli.commands.tool_cmd.ToolService")
    def test_schema_command_all_chains(self, mock_tool_service: MagicMock) -> None:
        """Test tool schema works for all supported chains."""
        chains = ["gnosis", "base", "polygon", "optimism"]

        for chain in chains:
            # Mock response
            mock_instance = mock_tool_service.return_value
            mock_instance.get_schema.return_value = {
                "name": "test-tool",
                "description": "Test tool",
                "input": {},
                "output": {},
            }
            mock_instance.format_input_schema.return_value = []
            mock_instance.format_output_schema.return_value = []

            runner = CliRunner()
            result = runner.invoke(
                tool, ["schema", "1-test-tool", "--chain-config", chain]
            )

            # Should succeed for all chains
            assert result.exit_code == 0, f"Failed for chain {chain}"


class TestToolCommandEdgeCases:
    """Tests for edge cases in tool command."""

    @patch("mech_client.cli.commands.tool_cmd.ToolService")
    def test_tool_id_with_multiple_dashes(
        self, mock_tool_service: MagicMock
    ) -> None:
        """Test tool commands with tool names containing multiple dashes."""
        # Mock response
        mock_instance = mock_tool_service.return_value
        mock_instance.get_description.return_value = "Test description"

        runner = CliRunner()
        result = runner.invoke(
            tool,
            [
                "describe",
                "2182-prediction-request-reasoning",
                "--chain-config",
                "gnosis",
            ],
        )

        # Should handle multiple dashes correctly
        assert result.exit_code == 0

    @patch("mech_client.cli.commands.tool_cmd.ToolService")
    def test_large_agent_id(self, mock_tool_service: MagicMock) -> None:
        """Test tool list with very large agent ID."""
        # Mock response
        mock_instance = mock_tool_service.return_value
        mock_result = MagicMock()
        mock_result.tools = []
        mock_instance.get_tools_info.return_value = mock_result

        runner = CliRunner()
        result = runner.invoke(
            tool, ["list", "999999", "--chain-config", "gnosis"]
        )

        # Should accept large valid integers
        assert result.exit_code == 0

    @patch("mech_client.cli.commands.tool_cmd.ToolService")
    def test_special_characters_in_tool_name(
        self, mock_tool_service: MagicMock
    ) -> None:
        """Test tool describe with special characters in tool name."""
        # Mock response
        mock_instance = mock_tool_service.return_value
        mock_instance.get_description.return_value = "Test description"

        runner = CliRunner()
        # Tool name with dots, numbers, and dashes
        result = runner.invoke(
            tool,
            ["describe", "2182-openai-gpt-4.1-turbo", "--chain-config", "gnosis"],
        )

        # Should handle special characters
        assert result.exit_code == 0

    def test_tool_help_commands(self) -> None:
        """Test help output for tool commands."""
        runner = CliRunner()

        # Test main tool help
        result = runner.invoke(tool, ["--help"])
        assert result.exit_code == 0
        assert "list" in result.output
        assert "describe" in result.output
        assert "schema" in result.output

        # Test list help
        result = runner.invoke(tool, ["list", "--help"])
        assert result.exit_code == 0
        assert "agent-id" in result.output.lower()

        # Test describe help
        result = runner.invoke(tool, ["describe", "--help"])
        assert result.exit_code == 0
        assert "tool-id" in result.output.lower()

        # Test schema help
        result = runner.invoke(tool, ["schema", "--help"])
        assert result.exit_code == 0
        assert "tool-id" in result.output.lower()
