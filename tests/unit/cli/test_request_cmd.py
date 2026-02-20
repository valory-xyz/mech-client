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

"""Tests for request command."""

from unittest.mock import AsyncMock, MagicMock, patch

from mech_client.infrastructure.config import IPFS_URL_TEMPLATE
from click.testing import CliRunner

from mech_client.cli.commands.request_cmd import request


class TestRequestCommand:
    """Tests for request command."""

    @patch("mech_client.cli.commands.request_cmd.MarketplaceService")
    @patch("mech_client.cli.commands.request_cmd.setup_wallet_command")
    def test_request_success_single_prompt(
        self,
        mock_setup_wallet: MagicMock,
        mock_marketplace_service: MagicMock,
    ) -> None:
        """Test successful single prompt request."""
        # Mock wallet
        mock_wallet_ctx = MagicMock()
        mock_wallet_ctx.agent_mode = False
        mock_wallet_ctx.crypto = MagicMock()
        mock_wallet_ctx.safe_address = None
        mock_wallet_ctx.ethereum_client = None
        mock_setup_wallet.return_value = mock_wallet_ctx

        # Mock service
        mock_service = MagicMock()
        mock_service.send_request = AsyncMock(
            return_value={
                "tx_hash": "0xabc123...",
                "request_ids": [1],
                "delivery_results": {1: "ipfs://Qm..."},
            }
        )
        mock_marketplace_service.return_value = mock_service

        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                request,
                [
                    "--prompts",
                    "What is 2+2?",
                    "--tools",
                    "openai-gpt-4",
                    "--chain-config",
                    "gnosis",
                    "--key",
                    "key.txt",
                ],
            )

            # Verify success
            assert result.exit_code == 0
            assert "Sending marketplace request" in result.output
            assert "0xabc123" in result.output
            assert "Request IDs: [1]" in result.output
            assert "Delivery results" in result.output
            assert "ipfs://Qm" in result.output

            # Verify service was called correctly
            mock_marketplace_service.assert_called_once()
            mock_service.send_request.assert_called_once()

    @patch("mech_client.cli.commands.request_cmd.MarketplaceService")
    @patch("mech_client.cli.commands.request_cmd.setup_wallet_command")
    def test_request_success_batch(
        self,
        mock_setup_wallet: MagicMock,
        mock_marketplace_service: MagicMock,
    ) -> None:
        """Test successful batch request with multiple prompts."""
        # Mock wallet
        mock_wallet_ctx = MagicMock()
        mock_setup_wallet.return_value = mock_wallet_ctx

        # Mock service
        mock_service = MagicMock()
        mock_service.send_request = AsyncMock(
            return_value={
                "tx_hash": "0xbatch123...",
                "request_ids": [1, 2, 3],
                "delivery_results": {
                    1: "ipfs://Qm1...",
                    2: "ipfs://Qm2...",
                    3: "ipfs://Qm3...",
                },
            }
        )
        mock_marketplace_service.return_value = mock_service

        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                request,
                [
                    "--prompts",
                    "Prompt 1",
                    "--prompts",
                    "Prompt 2",
                    "--prompts",
                    "Prompt 3",
                    "--tools",
                    "tool1",
                    "--tools",
                    "tool2",
                    "--tools",
                    "tool3",
                    "--chain-config",
                    "gnosis",
                    "--key",
                    "key.txt",
                ],
            )

            # Verify success
            assert result.exit_code == 0
            assert "Request IDs: [1, 2, 3]" in result.output
            assert "ipfs://Qm1" in result.output
            assert "ipfs://Qm2" in result.output
            assert "ipfs://Qm3" in result.output

    @patch("mech_client.cli.commands.request_cmd.MarketplaceService")
    @patch("mech_client.cli.commands.request_cmd.setup_wallet_command")
    def test_request_with_priority_mech(
        self,
        mock_setup_wallet: MagicMock,
        mock_marketplace_service: MagicMock,
    ) -> None:
        """Test request with priority mech address."""
        # Mock wallet
        mock_wallet_ctx = MagicMock()
        mock_setup_wallet.return_value = mock_wallet_ctx

        # Mock service
        mock_service = MagicMock()
        mock_service.send_request = AsyncMock(
            return_value={
                "tx_hash": "0xpriority123...",
                "request_ids": [1],
            }
        )
        mock_marketplace_service.return_value = mock_service

        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                request,
                [
                    "--prompts",
                    "Test prompt",
                    "--tools",
                    "tool1",
                    "--priority-mech",
                    "0x1234567890123456789012345678901234567890",
                    "--chain-config",
                    "gnosis",
                    "--key",
                    "key.txt",
                ],
            )

            assert result.exit_code == 0
            # Verify priority_mech was passed to service
            call_kwargs = mock_service.send_request.call_args[1]
            assert call_kwargs["priority_mech"] == "0x1234567890123456789012345678901234567890"

    @patch("mech_client.cli.commands.request_cmd.MarketplaceService")
    @patch("mech_client.cli.commands.request_cmd.setup_wallet_command")
    def test_request_with_use_prepaid(
        self,
        mock_setup_wallet: MagicMock,
        mock_marketplace_service: MagicMock,
    ) -> None:
        """Test request with prepaid balance."""
        # Mock wallet
        mock_wallet_ctx = MagicMock()
        mock_setup_wallet.return_value = mock_wallet_ctx

        # Mock service
        mock_service = MagicMock()
        mock_service.send_request = AsyncMock(
            return_value={
                "tx_hash": "0xprepaid123...",
                "request_ids": [1],
            }
        )
        mock_marketplace_service.return_value = mock_service

        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                request,
                [
                    "--prompts",
                    "Test prompt",
                    "--tools",
                    "tool1",
                    "--use-prepaid",
                    "true",
                    "--chain-config",
                    "gnosis",
                    "--key",
                    "key.txt",
                ],
            )

            assert result.exit_code == 0
            # Verify use_prepaid flag was passed
            call_kwargs = mock_service.send_request.call_args[1]
            assert call_kwargs["use_prepaid"] is True

    @patch("mech_client.cli.commands.request_cmd.EnvironmentConfig")
    @patch("mech_client.cli.commands.request_cmd.MarketplaceService")
    @patch("mech_client.cli.commands.request_cmd.setup_wallet_command")
    @patch("mech_client.cli.commands.request_cmd.requests.get")
    def test_request_with_use_offchain(
        self,
        mock_requests_get: MagicMock,
        mock_setup_wallet: MagicMock,
        mock_marketplace_service: MagicMock,
        mock_env_config: MagicMock,
    ) -> None:
        """Test request with offchain mech."""
        # Mock environment config with offchain URL
        mock_config_instance = MagicMock()
        mock_config_instance.mechx_mech_offchain_url = "https://offchain.example.com"
        mock_env_config.load.return_value = mock_config_instance

        # Mock wallet
        mock_wallet_ctx = MagicMock()
        mock_setup_wallet.return_value = mock_wallet_ctx

        # Mock service
        mock_service = MagicMock()
        mock_service.send_request = AsyncMock(
            return_value={
                "tx_hash": "0xoffchain123...",
                "request_ids": [1],
                "delivery_results": {
                    "0xabc": {
                        "request_id": "12345",
                        "task_result": "a" * 64,
                    }
                },
            }
        )
        mock_marketplace_service.return_value = mock_service

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"result": "final mech answer"}
        mock_requests_get.return_value = mock_response

        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                request,
                [
                    "--prompts",
                    "Test prompt",
                    "--tools",
                    "tool1",
                    "--use-offchain",
                    "true",
                    "--chain-config",
                    "gnosis",
                    "--key",
                    "key.txt",
                ],
            )

            assert result.exit_code == 0
            # Verify offchain flags were passed
            call_kwargs = mock_service.send_request.call_args[1]
            assert call_kwargs["use_offchain"] is True
            assert call_kwargs["use_prepaid"] is True  # Auto-enabled with offchain
            assert call_kwargs["mech_offchain_url"] == "https://offchain.example.com"
            expected_url = f"{IPFS_URL_TEMPLATE.format('a' * 64).rstrip('/')}/12345"
            mock_requests_get.assert_called_once_with(expected_url, timeout=10)
            assert "final mech answer" in result.output
            assert "task_result" not in result.output

    @patch("mech_client.cli.commands.request_cmd.EnvironmentConfig")
    @patch("mech_client.cli.commands.request_cmd.MarketplaceService")
    @patch("mech_client.cli.commands.request_cmd.setup_wallet_command")
    @patch("mech_client.cli.commands.request_cmd.requests.get")
    def test_request_with_use_offchain_requestid_key_supported(
        self,
        mock_requests_get: MagicMock,
        mock_setup_wallet: MagicMock,
        mock_marketplace_service: MagicMock,
        mock_env_config: MagicMock,
    ) -> None:
        """Test offchain result fetch supports requestId key."""
        mock_config_instance = MagicMock()
        mock_config_instance.mechx_mech_offchain_url = "https://offchain.example.com"
        mock_env_config.load.return_value = mock_config_instance

        mock_wallet_ctx = MagicMock()
        mock_setup_wallet.return_value = mock_wallet_ctx

        mock_service = MagicMock()
        mock_service.send_request = AsyncMock(
            return_value={
                "tx_hash": None,
                "request_ids": ["0xabc"],
                "delivery_results": {
                    "0xabc": {
                        "requestId": "67890",
                        "task_result": "b" * 64,
                    }
                },
            }
        )
        mock_marketplace_service.return_value = mock_service

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"result": "resolved via requestId"}
        mock_requests_get.return_value = mock_response

        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                request,
                [
                    "--prompts",
                    "Test prompt",
                    "--tools",
                    "tool1",
                    "--use-offchain",
                    "true",
                    "--chain-config",
                    "gnosis",
                    "--key",
                    "key.txt",
                ],
            )

            assert result.exit_code == 0
            expected_url = f"{IPFS_URL_TEMPLATE.format('b' * 64).rstrip('/')}/67890"
            mock_requests_get.assert_called_once_with(expected_url, timeout=10)
            assert "resolved via requestId" in result.output

    @patch("mech_client.cli.commands.request_cmd.EnvironmentConfig")
    def test_request_offchain_without_url_fails(
        self, mock_env_config: MagicMock
    ) -> None:
        """Test request fails when offchain URL not set."""
        # Mock environment config without offchain URL
        mock_config_instance = MagicMock()
        mock_config_instance.mechx_mech_offchain_url = None
        mock_env_config.load.return_value = mock_config_instance

        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                request,
                [
                    "--prompts",
                    "Test prompt",
                    "--tools",
                    "tool1",
                    "--use-offchain",
                    "true",
                    "--chain-config",
                    "gnosis",
                    "--key",
                    "key.txt",
                ],
            )

            assert result.exit_code == 1
            assert "MECHX_MECH_OFFCHAIN_URL is required" in result.output

    @patch("mech_client.cli.commands.request_cmd.MarketplaceService")
    @patch("mech_client.cli.commands.request_cmd.setup_wallet_command")
    def test_request_with_extra_attributes(
        self,
        mock_setup_wallet: MagicMock,
        mock_marketplace_service: MagicMock,
    ) -> None:
        """Test request with extra attributes."""
        # Mock wallet
        mock_wallet_ctx = MagicMock()
        mock_setup_wallet.return_value = mock_wallet_ctx

        # Mock service
        mock_service = MagicMock()
        mock_service.send_request = AsyncMock(
            return_value={
                "tx_hash": "0xattr123...",
                "request_ids": [1],
            }
        )
        mock_marketplace_service.return_value = mock_service

        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                request,
                [
                    "--prompts",
                    "Test prompt",
                    "--tools",
                    "tool1",
                    "--extra-attribute",
                    "key1=value1",
                    "--extra-attribute",
                    "key2=value2",
                    "--chain-config",
                    "gnosis",
                    "--key",
                    "key.txt",
                ],
            )

            assert result.exit_code == 0
            # Verify extra attributes were passed
            call_kwargs = mock_service.send_request.call_args[1]
            assert "key1" in call_kwargs["extra_attributes"]
            assert "key2" in call_kwargs["extra_attributes"]

    def test_request_extra_attribute_invalid_format(self) -> None:
        """Test request fails with invalid extra attribute format."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                request,
                [
                    "--prompts",
                    "Test prompt",
                    "--tools",
                    "tool1",
                    "--extra-attribute",
                    "invalid_no_equals",
                    "--chain-config",
                    "gnosis",
                    "--key",
                    "key.txt",
                ],
            )

            assert result.exit_code == 1
            assert "Invalid extra attribute format" in result.output
            assert "Expected format: key=value" in result.output

    def test_request_missing_tools(self) -> None:
        """Test request fails without tools."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                request,
                [
                    "--prompts",
                    "Test prompt",
                    "--chain-config",
                    "gnosis",
                    "--key",
                    "key.txt",
                ],
            )

            assert result.exit_code == 1
            assert "Tools are required" in result.output

    def test_request_missing_prompts(self) -> None:
        """Test request fails without prompts."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                request,
                [
                    "--tools",
                    "tool1",
                    "--chain-config",
                    "gnosis",
                    "--key",
                    "key.txt",
                ],
            )

            # Should fail - prompts are required
            assert result.exit_code != 0

    def test_request_batch_size_mismatch(self) -> None:
        """Test request fails when prompts and tools counts don't match."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                request,
                [
                    "--prompts",
                    "Prompt 1",
                    "--prompts",
                    "Prompt 2",
                    "--tools",
                    "tool1",
                    "--chain-config",
                    "gnosis",
                    "--key",
                    "key.txt",
                ],
            )

            assert result.exit_code == 1
            assert "must match" in result.output.lower()

    def test_request_invalid_priority_mech_address(self) -> None:
        """Test request fails with invalid priority mech address."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                request,
                [
                    "--prompts",
                    "Test prompt",
                    "--tools",
                    "tool1",
                    "--priority-mech",
                    "invalid_address",
                    "--chain-config",
                    "gnosis",
                    "--key",
                    "key.txt",
                ],
            )

            assert result.exit_code == 1
            assert "Invalid" in result.output or "address" in result.output.lower()

    def test_request_invalid_chain_config(self) -> None:
        """Test request fails with invalid chain config."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                request,
                [
                    "--prompts",
                    "Test prompt",
                    "--tools",
                    "tool1",
                    "--chain-config",
                    "invalid",
                    "--key",
                    "key.txt",
                ],
            )

            assert result.exit_code == 1
            assert "Invalid chain configuration" in result.output

    @patch("mech_client.cli.commands.request_cmd.MarketplaceService")
    @patch("mech_client.cli.commands.request_cmd.setup_wallet_command")
    def test_request_service_failure(
        self,
        mock_setup_wallet: MagicMock,
        mock_marketplace_service: MagicMock,
    ) -> None:
        """Test request when service fails."""
        # Mock wallet
        mock_wallet_ctx = MagicMock()
        mock_setup_wallet.return_value = mock_wallet_ctx

        # Mock service to raise error
        mock_service = MagicMock()
        mock_service.send_request = AsyncMock(
            side_effect=Exception("Transaction failed")
        )
        mock_marketplace_service.return_value = mock_service

        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                request,
                [
                    "--prompts",
                    "Test prompt",
                    "--tools",
                    "tool1",
                    "--chain-config",
                    "gnosis",
                    "--key",
                    "key.txt",
                ],
            )

            assert result.exit_code == 1
            assert "Transaction failed" in result.output

    @patch("mech_client.cli.commands.request_cmd.MarketplaceService")
    @patch("mech_client.cli.commands.request_cmd.setup_wallet_command")
    def test_request_without_delivery_results(
        self,
        mock_setup_wallet: MagicMock,
        mock_marketplace_service: MagicMock,
    ) -> None:
        """Test request when no delivery results returned."""
        # Mock wallet
        mock_wallet_ctx = MagicMock()
        mock_setup_wallet.return_value = mock_wallet_ctx

        # Mock service without delivery results
        mock_service = MagicMock()
        mock_service.send_request = AsyncMock(
            return_value={
                "tx_hash": "0xnodelivery123...",
                "request_ids": [1],
            }
        )
        mock_marketplace_service.return_value = mock_service

        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                request,
                [
                    "--prompts",
                    "Test prompt",
                    "--tools",
                    "tool1",
                    "--chain-config",
                    "gnosis",
                    "--key",
                    "key.txt",
                ],
            )

            # Should still succeed
            assert result.exit_code == 0
            assert "0xnodelivery123" in result.output
            assert "Request IDs: [1]" in result.output
            # Should not show delivery results section
            assert "Delivery results" not in result.output

    @patch("mech_client.cli.commands.request_cmd.MarketplaceService")
    @patch("mech_client.cli.commands.request_cmd.setup_wallet_command")
    def test_request_all_supported_chains(
        self,
        mock_setup_wallet: MagicMock,
        mock_marketplace_service: MagicMock,
    ) -> None:
        """Test request works for all supported chains."""
        chains = ["gnosis", "base", "polygon", "optimism"]

        runner = CliRunner()
        for chain in chains:
            # Mock wallet
            mock_wallet_ctx = MagicMock()
            mock_setup_wallet.return_value = mock_wallet_ctx

            # Mock service
            mock_service = MagicMock()
            mock_service.send_request = AsyncMock(
                return_value={
                    "tx_hash": f"0x{chain}123...",
                    "request_ids": [1],
                }
            )
            mock_marketplace_service.return_value = mock_service

            with runner.isolated_filesystem():
                with open("key.txt", "w") as f:
                    f.write("dummy_key")

                result = runner.invoke(
                    request,
                    [
                        "--prompts",
                        "Test prompt",
                        "--tools",
                        "tool1",
                        "--chain-config",
                        chain,
                        "--key",
                        "key.txt",
                    ],
                )

                assert result.exit_code == 0, f"Failed for chain {chain}"

    @patch("mech_client.cli.commands.request_cmd.MarketplaceService")
    @patch("mech_client.cli.commands.request_cmd.setup_wallet_command")
    def test_request_with_timeout(
        self,
        mock_setup_wallet: MagicMock,
        mock_marketplace_service: MagicMock,
    ) -> None:
        """Test request with custom timeout."""
        # Mock wallet
        mock_wallet_ctx = MagicMock()
        mock_setup_wallet.return_value = mock_wallet_ctx

        # Mock service
        mock_service = MagicMock()
        mock_service.send_request = AsyncMock(
            return_value={
                "tx_hash": "0xtimeout123...",
                "request_ids": [1],
            }
        )
        mock_marketplace_service.return_value = mock_service

        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                request,
                [
                    "--prompts",
                    "Test prompt",
                    "--tools",
                    "tool1",
                    "--timeout",
                    "30.5",
                    "--chain-config",
                    "gnosis",
                    "--key",
                    "key.txt",
                ],
            )

            assert result.exit_code == 0
            # Verify timeout was passed
            call_kwargs = mock_service.send_request.call_args[1]
            assert call_kwargs["timeout"] == 30.5

    def test_request_help(self) -> None:
        """Test request help output."""
        runner = CliRunner()
        result = runner.invoke(request, ["--help"])

        assert result.exit_code == 0
        assert "Send an AI task request" in result.output
        assert "--prompts" in result.output
        assert "--tools" in result.output
        assert "--priority-mech" in result.output
        assert "--use-prepaid" in result.output
        assert "--use-offchain" in result.output
        assert "--extra-attribute" in result.output


class TestRequestEdgeCases:
    """Tests for edge cases in request command."""

    @patch("mech_client.cli.commands.request_cmd.MarketplaceService")
    @patch("mech_client.cli.commands.request_cmd.setup_wallet_command")
    def test_request_with_empty_prompt(
        self,
        mock_setup_wallet: MagicMock,
        mock_marketplace_service: MagicMock,
    ) -> None:
        """Test request with empty prompt string."""
        # Mock wallet
        mock_wallet_ctx = MagicMock()
        mock_setup_wallet.return_value = mock_wallet_ctx

        # Mock service
        mock_service = MagicMock()
        mock_service.send_request = AsyncMock(
            return_value={
                "tx_hash": "0xempty123...",
                "request_ids": [1],
            }
        )
        mock_marketplace_service.return_value = mock_service

        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                request,
                [
                    "--prompts",
                    "",
                    "--tools",
                    "tool1",
                    "--chain-config",
                    "gnosis",
                    "--key",
                    "key.txt",
                ],
            )

            # Should succeed - empty strings are technically valid
            assert result.exit_code == 0

    @patch("mech_client.cli.commands.request_cmd.MarketplaceService")
    @patch("mech_client.cli.commands.request_cmd.setup_wallet_command")
    def test_request_with_special_characters_in_prompt(
        self,
        mock_setup_wallet: MagicMock,
        mock_marketplace_service: MagicMock,
    ) -> None:
        """Test request with special characters in prompt."""
        # Mock wallet
        mock_wallet_ctx = MagicMock()
        mock_setup_wallet.return_value = mock_wallet_ctx

        # Mock service
        mock_service = MagicMock()
        mock_service.send_request = AsyncMock(
            return_value={
                "tx_hash": "0xspecial123...",
                "request_ids": [1],
            }
        )
        mock_marketplace_service.return_value = mock_service

        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                request,
                [
                    "--prompts",
                    "Test with émojis 🚀 and spëcial çhars!",
                    "--tools",
                    "tool1",
                    "--chain-config",
                    "gnosis",
                    "--key",
                    "key.txt",
                ],
            )

            # Should handle special characters
            assert result.exit_code == 0

    @patch("mech_client.cli.commands.request_cmd.MarketplaceService")
    @patch("mech_client.cli.commands.request_cmd.setup_wallet_command")
    def test_request_with_very_long_prompt(
        self,
        mock_setup_wallet: MagicMock,
        mock_marketplace_service: MagicMock,
    ) -> None:
        """Test request with very long prompt."""
        # Mock wallet
        mock_wallet_ctx = MagicMock()
        mock_setup_wallet.return_value = mock_wallet_ctx

        # Mock service
        mock_service = MagicMock()
        mock_service.send_request = AsyncMock(
            return_value={
                "tx_hash": "0xlong123...",
                "request_ids": [1],
            }
        )
        mock_marketplace_service.return_value = mock_service

        long_prompt = "a" * 10000  # 10k character prompt

        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                request,
                [
                    "--prompts",
                    long_prompt,
                    "--tools",
                    "tool1",
                    "--chain-config",
                    "gnosis",
                    "--key",
                    "key.txt",
                ],
            )

            # Should handle long prompts
            assert result.exit_code == 0
