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

"""Tests for IPFS command."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from mech_client.cli.commands.ipfs_cmd import ipfs


class TestIPFSUploadCommand:
    """Tests for ipfs upload command."""

    @patch("mech_client.cli.commands.ipfs_cmd.IPFSClient")
    def test_upload_command_success(self, mock_ipfs_client: MagicMock) -> None:
        """Test successful file upload to IPFS."""
        # Mock IPFSClient response
        mock_instance = mock_ipfs_client.return_value
        mock_instance.upload.return_value = (
            "bafybeiawwdkbb57bexf4meuuzcalqbvr2dpazpvo3gn6detxhtkbq7lp3e",
            "f0170122016b0d410f7e125cbc61294c880b806b1d0de0cbeaed99be192773cd4187d6fd9",
        )

        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create test file
            test_file = Path("test.json")
            test_file.write_text('{"test": "data"}')

            result = runner.invoke(ipfs, ["upload", str(test_file)])

            # Verify command succeeded
            assert result.exit_code == 0
            assert "IPFS file hash v1:" in result.output
            assert (
                "bafybeiawwdkbb57bexf4meuuzcalqbvr2dpazpvo3gn6detxhtkbq7lp3e"
                in result.output
            )
            assert "IPFS file hash v1 hex:" in result.output
            assert (
                "f0170122016b0d410f7e125cbc61294c880b806b1d0de0cbeaed99be192773cd4187d6fd9"
                in result.output
            )

            # Verify client was called correctly
            mock_instance.upload.assert_called_once_with(str(test_file))

    @patch("mech_client.cli.commands.ipfs_cmd.IPFSClient")
    def test_upload_command_with_json_file(self, mock_ipfs_client: MagicMock) -> None:
        """Test uploading JSON file to IPFS."""
        mock_instance = mock_ipfs_client.return_value
        mock_instance.upload.return_value = ("hash1", "hash1hex")

        runner = CliRunner()
        with runner.isolated_filesystem():
            test_file = Path("data.json")
            test_file.write_text('{"key": "value", "number": 42}')

            result = runner.invoke(ipfs, ["upload", str(test_file)])

            assert result.exit_code == 0
            assert "hash1" in result.output

    @patch("mech_client.cli.commands.ipfs_cmd.IPFSClient")
    def test_upload_command_with_text_file(self, mock_ipfs_client: MagicMock) -> None:
        """Test uploading text file to IPFS."""
        mock_instance = mock_ipfs_client.return_value
        mock_instance.upload.return_value = ("hash2", "hash2hex")

        runner = CliRunner()
        with runner.isolated_filesystem():
            test_file = Path("test.txt")
            test_file.write_text("This is a test file content")

            result = runner.invoke(ipfs, ["upload", str(test_file)])

            assert result.exit_code == 0
            assert "hash2" in result.output

    @patch("mech_client.cli.commands.ipfs_cmd.IPFSClient")
    def test_upload_command_nonexistent_file(
        self, mock_ipfs_client: MagicMock
    ) -> None:
        """Test upload with non-existent file."""
        # Mock client to raise FileNotFoundError
        mock_instance = mock_ipfs_client.return_value
        mock_instance.upload.side_effect = FileNotFoundError(
            "No such file or directory"
        )

        runner = CliRunner()
        result = runner.invoke(ipfs, ["upload", "/tmp/nonexistent_file.json"])

        # Should fail with error
        assert result.exit_code == 1

    @patch("mech_client.cli.commands.ipfs_cmd.IPFSClient")
    def test_upload_command_empty_file(self, mock_ipfs_client: MagicMock) -> None:
        """Test uploading empty file to IPFS."""
        mock_instance = mock_ipfs_client.return_value
        mock_instance.upload.return_value = ("emptyhash", "emptyhashex")

        runner = CliRunner()
        with runner.isolated_filesystem():
            test_file = Path("empty.txt")
            test_file.write_text("")

            result = runner.invoke(ipfs, ["upload", str(test_file)])

            assert result.exit_code == 0

    @patch("mech_client.cli.commands.ipfs_cmd.IPFSClient")
    def test_upload_command_large_file(self, mock_ipfs_client: MagicMock) -> None:
        """Test uploading larger file to IPFS."""
        mock_instance = mock_ipfs_client.return_value
        mock_instance.upload.return_value = ("largehash", "largehashex")

        runner = CliRunner()
        with runner.isolated_filesystem():
            test_file = Path("large.txt")
            # Create a 1MB file
            test_file.write_text("x" * (1024 * 1024))

            result = runner.invoke(ipfs, ["upload", str(test_file)])

            assert result.exit_code == 0
            assert "largehash" in result.output

    @patch("mech_client.cli.commands.ipfs_cmd.IPFSClient")
    def test_upload_command_with_spaces_in_filename(
        self, mock_ipfs_client: MagicMock
    ) -> None:
        """Test uploading file with spaces in filename."""
        mock_instance = mock_ipfs_client.return_value
        mock_instance.upload.return_value = ("spacehash", "spacehashex")

        runner = CliRunner()
        with runner.isolated_filesystem():
            test_file = Path("test file with spaces.txt")
            test_file.write_text("content")

            result = runner.invoke(ipfs, ["upload", str(test_file)])

            assert result.exit_code == 0

    @patch("mech_client.cli.commands.ipfs_cmd.IPFSClient")
    def test_upload_command_network_error(self, mock_ipfs_client: MagicMock) -> None:
        """Test upload with network error."""
        mock_instance = mock_ipfs_client.return_value
        mock_instance.upload.side_effect = Exception("Connection timeout")

        runner = CliRunner()
        with runner.isolated_filesystem():
            test_file = Path("test.txt")
            test_file.write_text("content")

            result = runner.invoke(ipfs, ["upload", str(test_file)])

            assert result.exit_code == 1

    def test_upload_command_missing_file_argument(self) -> None:
        """Test upload without providing file path."""
        runner = CliRunner()
        result = runner.invoke(ipfs, ["upload"])

        # Should fail - file path is required
        assert result.exit_code != 0
        assert "file-path" in result.output.lower() or "missing" in result.output.lower()


class TestIPFSUploadPromptCommand:
    """Tests for ipfs upload-prompt command."""

    @patch("mech_client.cli.commands.ipfs_cmd.push_metadata_to_ipfs")
    def test_upload_prompt_success(
        self, mock_push_metadata: MagicMock
    ) -> None:
        """Test successful prompt metadata upload."""
        # Mock response
        mock_push_metadata.return_value = (
            "0xa0e459e3d28d280afeaf54d06b1eb0f1a340683dc9e24847655ccc283f900f1d",
            "f01701220a0e459e3d28d280afeaf54d06b1eb0f1a340683dc9e24847655ccc283f900f1d",
        )

        runner = CliRunner()
        result = runner.invoke(
            ipfs, ["upload-prompt", "What is the capital of France?", "openai-gpt-4"]
        )

        # Verify command succeeded
        assert result.exit_code == 0
        assert "Visit url:" in result.output
        assert "gateway.autonolas.tech/ipfs/" in result.output
        assert "Hash for Request method:" in result.output
        assert (
            "0xa0e459e3d28d280afeaf54d06b1eb0f1a340683dc9e24847655ccc283f900f1d"
            in result.output
        )

        # Verify function was called correctly
        mock_push_metadata.assert_called_once_with(
            "What is the capital of France?", "openai-gpt-4"
        )

    @patch("mech_client.cli.commands.ipfs_cmd.push_metadata_to_ipfs")
    def test_upload_prompt_with_simple_prompt(
        self, mock_push_metadata: MagicMock
    ) -> None:
        """Test upload-prompt with simple text."""
        mock_push_metadata.return_value = ("0xabc123", "f01701220abc123")

        runner = CliRunner()
        result = runner.invoke(ipfs, ["upload-prompt", "Hello", "test-tool"])

        assert result.exit_code == 0
        assert "0xabc123" in result.output

    @patch("mech_client.cli.commands.ipfs_cmd.push_metadata_to_ipfs")
    def test_upload_prompt_with_long_prompt(
        self, mock_push_metadata: MagicMock
    ) -> None:
        """Test upload-prompt with long text."""
        long_prompt = "This is a very long prompt. " * 100
        mock_push_metadata.return_value = ("0xlong", "f01701220long")

        runner = CliRunner()
        result = runner.invoke(ipfs, ["upload-prompt", long_prompt, "gpt-4"])

        assert result.exit_code == 0
        assert "0xlong" in result.output
        mock_push_metadata.assert_called_once_with(long_prompt, "gpt-4")

    @patch("mech_client.cli.commands.ipfs_cmd.push_metadata_to_ipfs")
    def test_upload_prompt_with_special_characters(
        self, mock_push_metadata: MagicMock
    ) -> None:
        """Test upload-prompt with special characters."""
        prompt_with_special = "Test: @#$%^&*()_+-=[]{}|;:',.<>?/~`"
        mock_push_metadata.return_value = ("0xspecial", "f01701220special")

        runner = CliRunner()
        result = runner.invoke(
            ipfs, ["upload-prompt", prompt_with_special, "test-tool"]
        )

        assert result.exit_code == 0
        mock_push_metadata.assert_called_once_with(prompt_with_special, "test-tool")

    @patch("mech_client.cli.commands.ipfs_cmd.push_metadata_to_ipfs")
    def test_upload_prompt_with_quotes(self, mock_push_metadata: MagicMock) -> None:
        """Test upload-prompt with quotes in prompt."""
        prompt = 'He said "hello" and she said \'hi\''
        mock_push_metadata.return_value = ("0xquotes", "f01701220quotes")

        runner = CliRunner()
        result = runner.invoke(ipfs, ["upload-prompt", prompt, "tool"])

        assert result.exit_code == 0
        mock_push_metadata.assert_called_once_with(prompt, "tool")

    @patch("mech_client.cli.commands.ipfs_cmd.push_metadata_to_ipfs")
    def test_upload_prompt_with_newlines(self, mock_push_metadata: MagicMock) -> None:
        """Test upload-prompt with newlines in prompt."""
        prompt = "Line 1\nLine 2\nLine 3"
        mock_push_metadata.return_value = ("0xnewline", "f01701220newline")

        runner = CliRunner()
        result = runner.invoke(ipfs, ["upload-prompt", prompt, "tool"])

        assert result.exit_code == 0
        mock_push_metadata.assert_called_once_with(prompt, "tool")

    @patch("mech_client.cli.commands.ipfs_cmd.push_metadata_to_ipfs")
    def test_upload_prompt_with_unicode(self, mock_push_metadata: MagicMock) -> None:
        """Test upload-prompt with unicode characters."""
        prompt = "Hello 世界 🌍 こんにちは"
        mock_push_metadata.return_value = ("0xunicode", "f01701220unicode")

        runner = CliRunner()
        result = runner.invoke(ipfs, ["upload-prompt", prompt, "tool"])

        assert result.exit_code == 0
        mock_push_metadata.assert_called_once_with(prompt, "tool")

    @patch("mech_client.cli.commands.ipfs_cmd.push_metadata_to_ipfs")
    def test_upload_prompt_with_empty_prompt(
        self, mock_push_metadata: MagicMock
    ) -> None:
        """Test upload-prompt with empty prompt string."""
        mock_push_metadata.return_value = ("0xempty", "f01701220empty")

        runner = CliRunner()
        result = runner.invoke(ipfs, ["upload-prompt", "", "tool"])

        # Should succeed - empty prompt is valid
        assert result.exit_code == 0
        mock_push_metadata.assert_called_once_with("", "tool")

    @patch("mech_client.cli.commands.ipfs_cmd.push_metadata_to_ipfs")
    def test_upload_prompt_with_tool_name_variations(
        self, mock_push_metadata: MagicMock
    ) -> None:
        """Test upload-prompt with various tool name formats."""
        tool_names = [
            "openai-gpt-4",
            "prediction-online",
            "claude-prediction-offline",
            "tool_with_underscores",
            "tool.with.dots",
        ]

        for tool_name in tool_names:
            mock_push_metadata.return_value = (f"0x{tool_name}", f"f01701220{tool_name}")

            runner = CliRunner()
            result = runner.invoke(ipfs, ["upload-prompt", "Test", tool_name])

            assert result.exit_code == 0, f"Failed for tool name: {tool_name}"
            mock_push_metadata.assert_called_with("Test", tool_name)

    @patch("mech_client.cli.commands.ipfs_cmd.push_metadata_to_ipfs")
    def test_upload_prompt_network_error(self, mock_push_metadata: MagicMock) -> None:
        """Test upload-prompt with network error."""
        mock_push_metadata.side_effect = Exception("Connection failed")

        runner = CliRunner()
        result = runner.invoke(ipfs, ["upload-prompt", "Test", "tool"])

        assert result.exit_code == 1

    def test_upload_prompt_missing_arguments(self) -> None:
        """Test upload-prompt without required arguments."""
        runner = CliRunner()

        # Missing both arguments
        result = runner.invoke(ipfs, ["upload-prompt"])
        assert result.exit_code != 0

        # Missing tool argument
        result = runner.invoke(ipfs, ["upload-prompt", "test prompt"])
        assert result.exit_code != 0

    @patch("mech_client.cli.commands.ipfs_cmd.push_metadata_to_ipfs")
    def test_upload_prompt_json_content(self, mock_push_metadata: MagicMock) -> None:
        """Test upload-prompt with JSON-formatted prompt."""
        json_prompt = '{"question": "What is AI?", "context": "machine learning"}'
        mock_push_metadata.return_value = ("0xjson", "f01701220json")

        runner = CliRunner()
        result = runner.invoke(ipfs, ["upload-prompt", json_prompt, "tool"])

        assert result.exit_code == 0
        mock_push_metadata.assert_called_once_with(json_prompt, "tool")


class TestIPFSCommandEdgeCases:
    """Tests for edge cases in IPFS command."""

    def test_ipfs_help_command(self) -> None:
        """Test help output for ipfs command."""
        runner = CliRunner()

        # Main help
        result = runner.invoke(ipfs, ["--help"])
        assert result.exit_code == 0
        assert "upload" in result.output
        assert "upload-prompt" in result.output
        assert "IPFS utility operations" in result.output

        # Upload help
        result = runner.invoke(ipfs, ["upload", "--help"])
        assert result.exit_code == 0
        assert "file-path" in result.output.lower()

        # Upload-prompt help
        result = runner.invoke(ipfs, ["upload-prompt", "--help"])
        assert result.exit_code == 0
        assert "prompt" in result.output.lower()
        assert "tool" in result.output.lower()

    @patch("mech_client.cli.commands.ipfs_cmd.IPFSClient")
    def test_upload_with_relative_path(self, mock_ipfs_client: MagicMock) -> None:
        """Test upload with relative file path."""
        mock_instance = mock_ipfs_client.return_value
        mock_instance.upload.return_value = ("hash", "hexhash")

        runner = CliRunner()
        with runner.isolated_filesystem():
            test_file = Path("./relative/path/file.txt")
            test_file.parent.mkdir(parents=True, exist_ok=True)
            test_file.write_text("content")

            result = runner.invoke(ipfs, ["upload", str(test_file)])

            assert result.exit_code == 0

    @patch("mech_client.cli.commands.ipfs_cmd.IPFSClient")
    def test_upload_with_absolute_path(self, mock_ipfs_client: MagicMock) -> None:
        """Test upload with absolute file path."""
        mock_instance = mock_ipfs_client.return_value
        mock_instance.upload.return_value = ("hash", "hexhash")

        runner = CliRunner()
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("test content")
            temp_path = f.name

        try:
            result = runner.invoke(ipfs, ["upload", temp_path])
            assert result.exit_code == 0
        finally:
            Path(temp_path).unlink()

    @patch("mech_client.cli.commands.ipfs_cmd.push_metadata_to_ipfs")
    def test_upload_prompt_url_format(self, mock_push_metadata: MagicMock) -> None:
        """Test that upload-prompt outputs correct URL format."""
        hash_hex = "f01701220a0e459e3d28d280afeaf54d06b1eb0f1a340683dc9e24847655ccc283f900f1d"
        mock_push_metadata.return_value = ("0xtruncated", hash_hex)

        runner = CliRunner()
        result = runner.invoke(ipfs, ["upload-prompt", "Test", "tool"])

        assert result.exit_code == 0
        assert f"https://gateway.autonolas.tech/ipfs/{hash_hex}" in result.output
        assert "0xtruncated" in result.output
