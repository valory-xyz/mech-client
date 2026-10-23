# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2025-2026 Valory AG
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

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mech_client.infrastructure.config import IPFS_URL_TEMPLATE
from click.testing import CliRunner, Result

from mech_client.cli.commands.request_cmd import request
from mech_client.domain.delivery import (
    FAULT_CLIENT,
    FAULT_MECH,
    DeliveryResult,
    RunFailure,
)


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
                "deliveries": {
                    1: DeliveryResult(
                        "1",
                        data={"result": '"4"'},
                        url=f"{IPFS_URL_TEMPLATE.format('a' * 64)}/1",
                    )
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
            # A JSON-encoded string answer prints as itself, not as `"4"`
            assert "Request 1: 4" in result.output
            assert f"{IPFS_URL_TEMPLATE.format('a' * 64)}/1" in result.output

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
                # Three tools, three payload shapes: a JSON-encoded string
                # answer, an answer already decoded to an object, and a bare
                # list with no `result` field at all.
                "deliveries": {
                    1: DeliveryResult(
                        "1",
                        data={"result": '"answer one"'},
                        url=f"{IPFS_URL_TEMPLATE.format('a' * 64)}/1",
                    ),
                    2: DeliveryResult(
                        "2",
                        data={"result": {"p_yes": 0.42}},
                        url=f"{IPFS_URL_TEMPLATE.format('b' * 64)}/2",
                    ),
                    3: DeliveryResult(
                        "3",
                        data=[1, 2, 3],
                        url=f"{IPFS_URL_TEMPLATE.format('c' * 64)}/3",
                    ),
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
            assert "Request 1: answer one" in result.output
            # An already-decoded answer is pretty-printed rather than stringified
            assert '"p_yes": 0.42' in result.output
            # ...as is a payload that carries no `result` field
            assert "[\n  1,\n  2,\n  3\n]" in result.output
            for i, char in enumerate("abc", start=1):
                assert f"{IPFS_URL_TEMPLATE.format(char * 64)}/{i}" in result.output

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

    @patch("mech_client.cli.commands.request_cmd.MarketplaceService")
    @patch("mech_client.cli.commands.request_cmd.setup_wallet_command")
    def test_request_with_use_offchain(
        self,
        mock_setup_wallet: MagicMock,
        mock_marketplace_service: MagicMock,
    ) -> None:
        """Test request with offchain mech (URL auto-discovered from metadata)."""
        # Mock wallet
        mock_wallet_ctx = MagicMock()
        mock_setup_wallet.return_value = mock_wallet_ctx

        # Mock service
        mock_service = MagicMock()
        mock_service.send_request = AsyncMock(
            return_value={
                "tx_hash": "0xoffchain123...",
                "request_ids": [1],
                "deliveries": {
                    "0xabc": DeliveryResult(
                        "0xabc",
                        data={
                            "requestId": 12345,
                            "result": '{"p_yes": 0.38}',
                            "tool": "factual_research",
                        },
                        url=f"{IPFS_URL_TEMPLATE.format('a' * 64)}/12345",
                    )
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
            # The answer itself is printed, decoded from the JSON-encoded string
            assert '"p_yes": 0.38' in result.output
            assert '\\"p_yes\\"' not in result.output
            # ...alongside the URL of the file it came from
            assert f"{IPFS_URL_TEMPLATE.format('a' * 64)}/12345" in result.output

    @patch("mech_client.cli.commands.request_cmd.MarketplaceService")
    @patch("mech_client.cli.commands.request_cmd.setup_wallet_command")
    def test_request_pretty_prints_payload_without_result_key(
        self,
        mock_setup_wallet: MagicMock,
        mock_marketplace_service: MagicMock,
    ) -> None:
        """Test a delivered payload with no `result` key is pretty-printed whole."""
        mock_wallet_ctx = MagicMock()
        mock_setup_wallet.return_value = mock_wallet_ctx

        mock_service = MagicMock()
        mock_service.send_request = AsyncMock(
            return_value={
                "tx_hash": "0xoffchain123...",
                "request_ids": [1],
                "deliveries": {
                    "0xabc": DeliveryResult(
                        "0xabc",
                        data={"tool": "factual_research"},
                        url=IPFS_URL_TEMPLATE.format("a" * 64),
                    )
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
            assert '"tool": "factual_research"' in result.output

    @patch("mech_client.cli.commands.request_cmd.MarketplaceService")
    @patch("mech_client.cli.commands.request_cmd.setup_wallet_command")
    def test_request_unreadable_result_still_prints_url(
        self,
        mock_setup_wallet: MagicMock,
        mock_marketplace_service: MagicMock,
    ) -> None:
        """Test an unreadable result file reports so and still prints its URL."""
        mock_wallet_ctx = MagicMock()
        mock_setup_wallet.return_value = mock_wallet_ctx

        mock_service = MagicMock()
        mock_service.send_request = AsyncMock(
            return_value={
                "tx_hash": None,
                "request_ids": ["0xabc"],
                "deliveries": {
                    "0xabc": DeliveryResult(
                        "0xabc",
                        data=None,
                        url=f"{IPFS_URL_TEMPLATE.format('b' * 64)}/67890",
                    )
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
            assert "unavailable" in result.output
            assert f"{IPFS_URL_TEMPLATE.format('b' * 64)}/67890" in result.output

    @patch("mech_client.cli.commands.request_cmd.MarketplaceService")
    @patch("mech_client.cli.commands.request_cmd.setup_wallet_command")
    def test_request_inline_text_answer_has_no_result_file_line(
        self,
        mock_setup_wallet: MagicMock,
        mock_marketplace_service: MagicMock,
    ) -> None:
        """Test a bare text answer prints as-is, with no result-file URL line."""
        mock_wallet_ctx = MagicMock()
        mock_setup_wallet.return_value = mock_wallet_ctx

        mock_service = MagicMock()
        mock_service.send_request = AsyncMock(
            return_value={
                "tx_hash": None,
                "request_ids": ["0xabc"],
                # A result file that is not JSON comes back as raw text, and an
                # offchain mech answering inline pins no file to link to.
                "deliveries": {
                    "0xabc": DeliveryResult("0xabc", data="plain text answer")
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
            assert "Request 0xabc: plain text answer" in result.output
            assert "Result file:" not in result.output

    @patch("mech_client.cli.commands.request_cmd.MarketplaceService")
    @patch("mech_client.cli.commands.request_cmd.setup_wallet_command")
    def test_request_with_onchain_dict_delivery_result(
        self,
        mock_setup_wallet: MagicMock,
        mock_marketplace_service: MagicMock,
    ) -> None:
        """Test on-chain delivery prints the answer, not the wrapping payload."""
        mock_wallet_ctx = MagicMock()
        mock_setup_wallet.return_value = mock_wallet_ctx

        mock_service = MagicMock()
        mock_service.send_request = AsyncMock(
            return_value={
                "tx_hash": "0xonchain123...",
                "request_ids": [1],
                "deliveries": {
                    1: DeliveryResult(
                        "1",
                        data={"status": "done", "result": "on-chain answer"},
                        url=IPFS_URL_TEMPLATE.format("c" * 64) + "/1",
                    )
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
                    "Test prompt",
                    "--tools",
                    "tool1",
                    "--chain-config",
                    "gnosis",
                    "--key",
                    "key.txt",
                ],
            )

            assert result.exit_code == 0
            assert "on-chain answer" in result.output
            assert '"status": "done"' not in result.output
            assert IPFS_URL_TEMPLATE.format("c" * 64) + "/1" in result.output

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
    def test_request_without_deliveries(
        self,
        mock_setup_wallet: MagicMock,
        mock_marketplace_service: MagicMock,
    ) -> None:
        """Test request when no deliveries are returned."""
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
        chains = ["gnosis", "base", "polygon", "optimism", "robinhood"]

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


def _invoke_with_result(result: dict, *extra_args: str) -> Result:
    """Run ``mechx request`` with the service answering ``result``.

    :param result: what the mocked ``send_request`` returns
    :param extra_args: options appended to a minimal offchain invocation
    :return: the click result, with the service mock on ``.service``
    """
    service = MagicMock()
    service.send_request = AsyncMock(return_value=result)
    with (
        patch("mech_client.cli.commands.request_cmd.setup_wallet_command"),
        patch("mech_client.cli.commands.request_cmd.MarketplaceService", return_value=service),
    ):
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("key.txt", "w") as f:
                f.write("dummy_key")
            invoked = runner.invoke(
                request,
                ["--prompts", "p", "--tools", "t", "--chain-config", "gnosis", "--key", "key.txt", *extra_args],
            )
    invoked.service = service  # type: ignore[attr-defined]
    return invoked


OFFCHAIN_RESULT = {"tx_hash": None, "request_ids": ["0xabc"], "receipt": None}


class TestRequestCommandCharge:
    """The charge a mech reports is printed under its delivery."""

    def test_a_reported_charge_is_printed(self) -> None:
        """A delivery carrying a charge prints it after the answer."""
        deliveries = {"0xabc": DeliveryResult("0xabc", data="answer", actual_delivery_rate=120)}

        invoked = _invoke_with_result({**OFFCHAIN_RESULT, "deliveries": deliveries}, "--use-offchain", "true")

        assert invoked.exit_code == 0, invoked.output
        assert "Request 0xabc: answer" in invoked.output
        assert "Reported charge: 120" in invoked.output
        assert "settles it on-chain later" in invoked.output

    def test_no_charge_line_when_the_mech_reported_none(self) -> None:
        """A delivery without a charge prints no charge line rather than a placeholder."""
        deliveries = {"0xabc": DeliveryResult("0xabc", data="answer")}

        invoked = _invoke_with_result({**OFFCHAIN_RESULT, "deliveries": deliveries}, "--use-offchain", "true")

        assert invoked.exit_code == 0, invoked.output
        assert "Reported charge" not in invoked.output



class TestRequestCommandMaxCost:
    """``--max-cost`` is validated like a deposit amount and reaches the service in base units."""

    def test_omitted_means_the_service_derives_the_cap(self) -> None:
        """Without the option the service gets no cap and picks the default."""
        invoked = _invoke_with_result({**OFFCHAIN_RESULT, "deliveries": {}}, "--use-offchain", "true")

        assert invoked.exit_code == 0, invoked.output
        assert invoked.service.send_request.call_args.kwargs["max_cost"] is None

    def test_an_amount_is_passed_through_as_an_integer(self) -> None:
        """The amount is base units, so it is parsed as an integer and not scaled."""
        invoked = _invoke_with_result(
            {**OFFCHAIN_RESULT, "deliveries": {}}, "--use-offchain", "true", "--max-cost", "24000000000000000"
        )

        assert invoked.exit_code == 0, invoked.output
        assert invoked.service.send_request.call_args.kwargs["max_cost"] == 24_000_000_000_000_000

    @pytest.mark.parametrize("value", ["0", "-5", "0.01", "1e16", "abc", "", str(2**256)])
    def test_anything_but_a_positive_integer_is_refused_before_the_request(self, value: str) -> None:
        """A fraction, a sign, an exponent, text or a value wider than a uint256 is not an amount in base units."""
        invoked = _invoke_with_result({**OFFCHAIN_RESULT, "deliveries": {}}, "--use-offchain", "true", "--max-cost", value)

        assert invoked.exit_code == 1, invoked.output
        assert "max-cost" in invoked.output
        invoked.service.send_request.assert_not_called()


class TestRequestCommandNonceMode:
    """``--nonce-mode`` reaches the service, and defaults to explicit."""

    def test_defaults_to_explicit(self) -> None:
        """Without the option the service is asked for an explicit-nonce request."""
        invoked = _invoke_with_result({**OFFCHAIN_RESULT, "deliveries": {}}, "--use-offchain", "true")

        assert invoked.exit_code == 0, invoked.output
        assert invoked.service.send_request.call_args.kwargs["nonce_mode"] == "explicit"

    def test_sequential_is_passed_through(self) -> None:
        """``--nonce-mode sequential`` is passed to the service as given."""
        invoked = _invoke_with_result(
            {**OFFCHAIN_RESULT, "deliveries": {}}, "--use-offchain", "true", "--nonce-mode", "sequential"
        )

        assert invoked.exit_code == 0, invoked.output
        assert invoked.service.send_request.call_args.kwargs["nonce_mode"] == "sequential"

    def test_an_unknown_mode_is_a_usage_error(self) -> None:
        """Click rejects a mode the service does not define before anything runs."""
        invoked = _invoke_with_result({**OFFCHAIN_RESULT, "deliveries": {}}, "--nonce-mode", "random")

        assert invoked.exit_code == 2
        assert "Invalid value for '--nonce-mode'" in invoked.output
        invoked.service.send_request.assert_not_called()


FAILED_ERROR = "ValueError: Tool nope is not supported."


def _invoke_with_deliveries(
    mock_setup_wallet: MagicMock,
    mock_marketplace_service: MagicMock,
    deliveries: dict,
) -> Result:
    """Run ``mechx request`` offchain with the service returning ``deliveries``."""
    mock_setup_wallet.return_value = MagicMock(agent_mode=False)
    mock_service = MagicMock()
    mock_service.send_request = AsyncMock(
        return_value={"tx_hash": None, "request_ids": ["0xabc"], "deliveries": deliveries}
    )
    mock_marketplace_service.return_value = mock_service
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("key.txt", "w") as f:
            f.write("dummy_key")
        return runner.invoke(
            request,
            [
                "--prompts", "q", "--tools", "t", "--chain-config", "gnosis",
                "--key", "key.txt", "--use-offchain", "true",
            ],
        )


class TestRequestCommandFailedRuns:
    """A failed run prints the mech's error, who caused it and the charge."""

    @pytest.mark.parametrize(
        ("fault", "charge", "expected"),
        [
            (FAULT_CLIENT, 10**16, ["Fault: client", "full signed cap", "Charged: 10000000000000000"]),
            (FAULT_MECH, 1, ["Fault: mech", "small fixed amount", "Charged: 1 "]),
            (None, None, ["Fault: not reported", "Charged: not reported"]),
        ],
    )
    @patch("mech_client.cli.commands.request_cmd.MarketplaceService")
    @patch("mech_client.cli.commands.request_cmd.setup_wallet_command")
    def test_failed_run_output(
        self,
        mock_setup_wallet: MagicMock,
        mock_marketplace_service: MagicMock,
        fault: Any,
        charge: Any,
        expected: list,
    ) -> None:
        """The failure lines replace the answer and the generic charge line."""
        delivery = DeliveryResult(
            "0xabc",
            data={"status": "failed", "error": FAILED_ERROR},
            actual_delivery_rate=charge,
            failure=RunFailure(error=FAILED_ERROR, fault=fault),
        )
        result = _invoke_with_deliveries(
            mock_setup_wallet, mock_marketplace_service, {"0xabc": delivery}
        )

        assert result.exit_code == 0, result.output
        assert f"Request 0xabc failed: {FAILED_ERROR}" in result.output
        for text in expected:
            assert text in result.output
        assert "Reported charge" not in result.output

    @patch("mech_client.cli.commands.request_cmd.MarketplaceService")
    @patch("mech_client.cli.commands.request_cmd.setup_wallet_command")
    def test_a_successful_run_prints_no_failure(
        self, mock_setup_wallet: MagicMock, mock_marketplace_service: MagicMock
    ) -> None:
        """An answer with a charge prints as before."""
        delivery = DeliveryResult("0xabc", data={"result": "yes"}, actual_delivery_rate=5)
        result = _invoke_with_deliveries(
            mock_setup_wallet, mock_marketplace_service, {"0xabc": delivery}
        )

        assert result.exit_code == 0, result.output
        assert "Request 0xabc: yes" in result.output
        assert "Reported charge: 5" in result.output
        assert "failed" not in result.output
