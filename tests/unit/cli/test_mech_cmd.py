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

"""Tests for mech command."""

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from mech_client.cli.commands.mech_cmd import mech


class TestMechListCommand:
    """Tests for mech list command."""

    @patch("mech_client.cli.commands.mech_cmd.query_mm_mechs_info")
    @patch.dict(
        "os.environ", {"MECHX_SUBGRAPH_URL": "https://subgraph.example.com/gnosis"}
    )
    def test_list_command_with_realistic_metadata_structure(
        self, mock_query: MagicMock
    ) -> None:
        """Test mech list handles actual GraphQL response structure.

        The actual subgraph returns metadata as a LIST of dicts:
        metadata: [{'metadata': '0x...'}]

        This test verifies the command correctly accesses metadata[0]["metadata"]
        instead of metadata["metadata"].
        """
        # Mock realistic GraphQL response structure
        mock_query.return_value = [
            {
                "id": "2182",
                "address": "0xc05e7412439bd7e91730a6880e18d5d5873f632c",
                "mechFactory": "0x8b299c20f87e3fcbff0e1b86dc0acc06ab6993ef",
                "totalDeliveriesTransactions": "781673",
                "service": {
                    "id": "2182",
                    "totalDeliveries": "781673",
                    "metadata": [
                        {"metadata": "0x4d82a931d803e2b46b0dcd53f558f8de8305fd44b36288b42287ef1450a6611f"}
                    ],  # LIST of dicts!
                },
                "mech_type": "Fixed Price Native",
            }
        ]

        runner = CliRunner()
        result = runner.invoke(mech, ["list", "--chain-config", "gnosis"])

        # Verify command succeeded
        assert result.exit_code == 0
        assert "2182" in result.output
        assert "Fixed Price Native" in result.output
        assert "781673" in result.output
        # Verify IPFS URL was formatted correctly
        assert "4d82a931d803e2b46b0dcd53f558f8de8305fd44b36288b42287ef1450a6611f" in result.output

    @patch("mech_client.cli.commands.mech_cmd.query_mm_mechs_info")
    @patch.dict(
        "os.environ", {"MECHX_SUBGRAPH_URL": "https://subgraph.example.com/gnosis"}
    )
    def test_list_command_with_empty_metadata(self, mock_query: MagicMock) -> None:
        """Test mech list handles empty metadata gracefully."""
        mock_query.return_value = [
            {
                "id": "1841",
                "address": "0x15719caecfafb1b1356255cb167cd2a73bd1555d",
                "mechFactory": "0x8b299c20f87e3fcbff0e1b86dc0acc06ab6993ef",
                "totalDeliveriesTransactions": "253",
                "service": {
                    "id": "1841",
                    "totalDeliveries": "253",
                    "metadata": None,  # No metadata
                },
                "mech_type": "Fixed Price Native",
            }
        ]

        runner = CliRunner()
        result = runner.invoke(mech, ["list", "--chain-config", "gnosis"])

        # Should succeed even with null metadata
        assert result.exit_code == 0
        assert "1841" in result.output
        assert "253" in result.output

    @patch("mech_client.cli.commands.mech_cmd.query_mm_mechs_info")
    @patch.dict(
        "os.environ", {"MECHX_SUBGRAPH_URL": "https://subgraph.example.com/gnosis"}
    )
    def test_list_command_with_empty_metadata_list(
        self, mock_query: MagicMock
    ) -> None:
        """Test mech list handles empty metadata list gracefully."""
        mock_query.return_value = [
            {
                "id": "2000",
                "address": "0x15719caecfafb1b1356255cb167cd2a73bd1555d",
                "mechFactory": "0x8b299c20f87e3fcbff0e1b86dc0acc06ab6993ef",
                "totalDeliveriesTransactions": "100",
                "service": {
                    "id": "2000",
                    "totalDeliveries": "100",
                    "metadata": [],  # Empty list
                },
                "mech_type": "Fixed Price Native",
            }
        ]

        runner = CliRunner()
        result = runner.invoke(mech, ["list", "--chain-config", "gnosis"])

        # Should succeed even with empty metadata list
        assert result.exit_code == 0
        assert "2000" in result.output

    @patch("mech_client.cli.commands.mech_cmd.query_mm_mechs_info")
    @patch.dict(
        "os.environ", {"MECHX_SUBGRAPH_URL": "https://subgraph.example.com/gnosis"}
    )
    def test_list_command_with_multiple_mechs(self, mock_query: MagicMock) -> None:
        """Test mech list displays multiple mechs correctly."""
        mock_query.return_value = [
            {
                "id": "2182",
                "address": "0xc05e7412439bd7e91730a6880e18d5d5873f632c",
                "mechFactory": "0x8b299c20f87e3fcbff0e1b86dc0acc06ab6993ef",
                "totalDeliveriesTransactions": "781673",
                "service": {
                    "id": "2182",
                    "totalDeliveries": "781673",
                    "metadata": [
                        {"metadata": "0x4d82a931d803e2b46b0dcd53f558f8de8305fd44b36288b42287ef1450a6611f"}
                    ],
                },
                "mech_type": "Fixed Price Native",
            },
            {
                "id": "2469",
                "address": "0x1cae83a8a68993954ed28e4de23341f6e672d9dc",
                "mechFactory": "0x65fd74c29463afe08c879a3020323dd7df02da57",
                "totalDeliveriesTransactions": "1425",
                "service": {
                    "id": "2469",
                    "totalDeliveries": "1425",
                    "metadata": [
                        {"metadata": "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"}
                    ],
                },
                "mech_type": "NvmSubscription Native",
            },
        ]

        runner = CliRunner()
        result = runner.invoke(mech, ["list", "--chain-config", "gnosis"])

        # Verify both mechs displayed
        assert result.exit_code == 0
        assert "2182" in result.output
        assert "2469" in result.output
        assert "Fixed Price Native" in result.output
        assert "NvmSubscription Native" in result.output
        assert "781673" in result.output
        assert "1425" in result.output

    @patch.dict("os.environ", {}, clear=True)
    def test_list_command_without_subgraph_url(self) -> None:
        """Test mech list fails gracefully when MECHX_SUBGRAPH_URL not set."""
        runner = CliRunner()
        result = runner.invoke(mech, ["list", "--chain-config", "gnosis"])

        # Should fail with clear error message
        assert result.exit_code == 1
        assert "MECHX_SUBGRAPH_URL" in result.output
        assert "required" in result.output.lower()

    @patch("mech_client.cli.commands.mech_cmd.query_mm_mechs_info")
    @patch.dict(
        "os.environ", {"MECHX_SUBGRAPH_URL": "https://subgraph.example.com/gnosis"}
    )
    def test_list_command_with_no_mechs(self, mock_query: MagicMock) -> None:
        """Test mech list displays message when no mechs found."""
        mock_query.return_value = None

        runner = CliRunner()
        result = runner.invoke(mech, ["list", "--chain-config", "gnosis"])

        # Should display "No mechs found" message
        assert result.exit_code == 0
        assert "No mechs found" in result.output

    @patch("mech_client.cli.commands.mech_cmd.query_mm_mechs_info")
    @patch.dict(
        "os.environ", {"MECHX_SUBGRAPH_URL": "https://subgraph.example.com/base"}
    )
    def test_list_command_for_base_chain(self, mock_query: MagicMock) -> None:
        """Test mech list works for base chain."""
        mock_query.return_value = [
            {
                "id": "100",
                "address": "0x1234567890123456789012345678901234567890",
                "mechFactory": "0x2e008211f34b25a7d7c102403c6c2c3b665a1abe",
                "totalDeliveriesTransactions": "500",
                "service": {
                    "id": "100",
                    "totalDeliveries": "500",
                    "metadata": [
                        {"metadata": "0x1111111111111111111111111111111111111111111111111111111111111111"}
                    ],
                },
                "mech_type": "Fixed Price Native",
            }
        ]

        runner = CliRunner()
        result = runner.invoke(mech, ["list", "--chain-config", "base"])

        assert result.exit_code == 0
        assert "100" in result.output
        assert "500" in result.output


class TestMechListCommandMetadataEdgeCases:
    """Tests for edge cases in metadata structure handling."""

    @patch("mech_client.cli.commands.mech_cmd.query_mm_mechs_info")
    @patch.dict(
        "os.environ", {"MECHX_SUBGRAPH_URL": "https://subgraph.example.com/gnosis"}
    )
    def test_metadata_without_0x_prefix(self, mock_query: MagicMock) -> None:
        """Test handling metadata that already has correct format."""
        mock_query.return_value = [
            {
                "id": "2182",
                "address": "0xc05e7412439bd7e91730a6880e18d5d5873f632c",
                "mechFactory": "0x8b299c20f87e3fcbff0e1b86dc0acc06ab6993ef",
                "totalDeliveriesTransactions": "100",
                "service": {
                    "id": "2182",
                    "totalDeliveries": "100",
                    "metadata": [
                        {"metadata": "4d82a931d803e2b46b0dcd53f558f8de8305fd44b36288b42287ef1450a6611f"}
                    ],  # No 0x prefix
                },
                "mech_type": "Fixed Price Native",
            }
        ]

        runner = CliRunner()
        result = runner.invoke(mech, ["list", "--chain-config", "gnosis"])

        # Should handle gracefully (code strips first 2 chars with [2:])
        assert result.exit_code == 0

    @patch("mech_client.cli.commands.mech_cmd.query_mm_mechs_info")
    @patch.dict(
        "os.environ", {"MECHX_SUBGRAPH_URL": "https://subgraph.example.com/gnosis"}
    )
    def test_metadata_with_multiple_entries(self, mock_query: MagicMock) -> None:
        """Test metadata list with multiple entries (uses first one)."""
        mock_query.return_value = [
            {
                "id": "2182",
                "address": "0xc05e7412439bd7e91730a6880e18d5d5873f632c",
                "mechFactory": "0x8b299c20f87e3fcbff0e1b86dc0acc06ab6993ef",
                "totalDeliveriesTransactions": "100",
                "service": {
                    "id": "2182",
                    "totalDeliveries": "100",
                    "metadata": [
                        {"metadata": "0xfirst_hash"},
                        {"metadata": "0xsecond_hash"},
                    ],  # Multiple entries
                },
                "mech_type": "Fixed Price Native",
            }
        ]

        runner = CliRunner()
        result = runner.invoke(mech, ["list", "--chain-config", "gnosis"])

        # Should use first entry
        assert result.exit_code == 0
        assert "first_hash" in result.output
