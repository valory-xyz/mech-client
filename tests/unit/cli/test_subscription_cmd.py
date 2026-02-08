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

"""Tests for subscription command."""

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from mech_client.cli.commands.subscription_cmd import subscription


class TestSubscriptionPurchaseCommand:
    """Tests for subscription purchase command."""

    @patch("mech_client.cli.commands.subscription_cmd.SubscriptionService")
    @patch("mech_client.cli.commands.subscription_cmd.setup_wallet_command")
    def test_subscription_purchase_success_gnosis(
        self,
        mock_setup_wallet: MagicMock,
        mock_subscription_service: MagicMock,
    ) -> None:
        """Test successful subscription purchase on Gnosis."""
        # Mock wallet setup
        mock_wallet_ctx = MagicMock()
        mock_wallet_ctx.agent_mode = False
        mock_wallet_ctx.crypto = MagicMock()
        mock_wallet_ctx.safe_address = None
        mock_wallet_ctx.ethereum_client = None
        mock_setup_wallet.return_value = mock_wallet_ctx

        # Mock subscription service
        mock_service = MagicMock()
        mock_service.purchase_subscription.return_value = {
            "agreement_id": "0xabc123...",
            "agreement_tx_hash": "0xdef456...",
            "fulfillment_tx_hash": "0xghi789...",
            "credits_before": 0,
            "credits_after": 1000000,
        }
        mock_subscription_service.return_value = mock_service

        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create a dummy key file
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                subscription,
                ["purchase", "--chain-config", "gnosis", "--key", "key.txt"],
            )

            # Verify success
            assert result.exit_code == 0
            assert "NVM Subscription Purchased Successfully" in result.output
            assert "0xabc123" in result.output
            assert "0xdef456" in result.output
            assert "0xghi789" in result.output
            assert "Credits Before: 0" in result.output
            assert "Credits After: 1000000" in result.output
            assert "Credits Gained: 1000000" in result.output

            # Verify service was called correctly
            mock_subscription_service.assert_called_once()
            mock_service.purchase_subscription.assert_called_once()

    @patch("mech_client.cli.commands.subscription_cmd.SubscriptionService")
    @patch("mech_client.cli.commands.subscription_cmd.setup_wallet_command")
    def test_subscription_purchase_success_base(
        self,
        mock_setup_wallet: MagicMock,
        mock_subscription_service: MagicMock,
    ) -> None:
        """Test successful subscription purchase on Base."""
        # Mock wallet
        mock_wallet_ctx = MagicMock()
        mock_wallet_ctx.agent_mode = False
        mock_wallet_ctx.crypto = MagicMock()
        mock_setup_wallet.return_value = mock_wallet_ctx

        # Mock service
        mock_service = MagicMock()
        mock_service.purchase_subscription.return_value = {
            "agreement_id": "0x123abc...",
            "agreement_tx_hash": "0x456def...",
            "fulfillment_tx_hash": "0x789ghi...",
            "credits_before": 500000,
            "credits_after": 1500000,
        }
        mock_subscription_service.return_value = mock_service

        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                subscription,
                ["purchase", "--chain-config", "base", "--key", "key.txt"],
            )

            # Verify success
            assert result.exit_code == 0
            assert "NVM Subscription Purchased Successfully" in result.output
            assert "Credits Before: 500000" in result.output
            assert "Credits After: 1500000" in result.output
            assert "Credits Gained: 1000000" in result.output

    def test_subscription_purchase_unsupported_chain_polygon(self) -> None:
        """Test subscription purchase fails for unsupported chain (Polygon)."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                subscription,
                ["purchase", "--chain-config", "polygon", "--key", "key.txt"],
            )

            # Should fail with unsupported chain error
            assert result.exit_code == 1
            assert "NVM subscriptions not available" in result.output
            assert "polygon" in result.output.lower()
            assert "gnosis" in result.output.lower()
            assert "base" in result.output.lower()

    def test_subscription_purchase_unsupported_chain_optimism(self) -> None:
        """Test subscription purchase fails for unsupported chain (Optimism)."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                subscription,
                ["purchase", "--chain-config", "optimism", "--key", "key.txt"],
            )

            assert result.exit_code == 1
            assert "NVM subscriptions not available" in result.output

    def test_subscription_purchase_unsupported_chain_arbitrum(self) -> None:
        """Test subscription purchase fails for unsupported chain (Arbitrum)."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                subscription,
                ["purchase", "--chain-config", "arbitrum", "--key", "key.txt"],
            )

            assert result.exit_code == 1
            assert "NVM subscriptions not available" in result.output

    def test_subscription_purchase_invalid_chain(self) -> None:
        """Test subscription purchase with invalid chain config."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                subscription,
                ["purchase", "--chain-config", "invalid", "--key", "key.txt"],
            )

            assert result.exit_code == 1
            assert "Invalid chain configuration" in result.output

    def test_subscription_purchase_missing_chain_config(self) -> None:
        """Test subscription purchase without chain-config."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(subscription, ["purchase", "--key", "key.txt"])

            # Should fail - chain-config is required
            assert result.exit_code != 0

    @patch("mech_client.cli.commands.subscription_cmd.SubscriptionService")
    @patch("mech_client.cli.commands.subscription_cmd.setup_wallet_command")
    def test_subscription_purchase_service_failure(
        self,
        mock_setup_wallet: MagicMock,
        mock_subscription_service: MagicMock,
    ) -> None:
        """Test subscription purchase when service fails."""
        # Mock wallet
        mock_wallet_ctx = MagicMock()
        mock_setup_wallet.return_value = mock_wallet_ctx

        # Mock service to raise error
        mock_service = MagicMock()
        mock_service.purchase_subscription.side_effect = Exception(
            "Insufficient funds"
        )
        mock_subscription_service.return_value = mock_service

        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                subscription,
                ["purchase", "--chain-config", "gnosis", "--key", "key.txt"],
            )

            assert result.exit_code == 1
            assert "Insufficient funds" in result.output

    @patch("mech_client.cli.commands.subscription_cmd.SubscriptionService")
    @patch("mech_client.cli.commands.subscription_cmd.setup_wallet_command")
    def test_subscription_purchase_zero_credits_gained(
        self,
        mock_setup_wallet: MagicMock,
        mock_subscription_service: MagicMock,
    ) -> None:
        """Test subscription purchase when no credits are gained."""
        # Mock wallet
        mock_wallet_ctx = MagicMock()
        mock_setup_wallet.return_value = mock_wallet_ctx

        # Mock service with same credits before and after
        mock_service = MagicMock()
        mock_service.purchase_subscription.return_value = {
            "agreement_id": "0xabc...",
            "agreement_tx_hash": "0xdef...",
            "fulfillment_tx_hash": "0xghi...",
            "credits_before": 1000000,
            "credits_after": 1000000,
        }
        mock_subscription_service.return_value = mock_service

        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                subscription,
                ["purchase", "--chain-config", "gnosis", "--key", "key.txt"],
            )

            # Should still succeed but show 0 credits gained
            assert result.exit_code == 0
            assert "Credits Gained: 0" in result.output

    @patch("mech_client.cli.commands.subscription_cmd.SubscriptionService")
    @patch("mech_client.cli.commands.subscription_cmd.setup_wallet_command")
    def test_subscription_purchase_only_supported_chains(
        self,
        mock_setup_wallet: MagicMock,
        mock_subscription_service: MagicMock,
    ) -> None:
        """Test subscription purchase works for all supported chains."""
        supported_chains = ["gnosis", "base"]

        runner = CliRunner()
        for chain in supported_chains:
            # Mock wallet
            mock_wallet_ctx = MagicMock()
            mock_wallet_ctx.agent_mode = False
            mock_wallet_ctx.crypto = MagicMock()
            mock_setup_wallet.return_value = mock_wallet_ctx

            # Mock service
            mock_service = MagicMock()
            mock_service.purchase_subscription.return_value = {
                "agreement_id": f"0x{chain}...",
                "agreement_tx_hash": f"0x{chain}1...",
                "fulfillment_tx_hash": f"0x{chain}2...",
                "credits_before": 0,
                "credits_after": 1000000,
            }
            mock_subscription_service.return_value = mock_service

            with runner.isolated_filesystem():
                with open("key.txt", "w") as f:
                    f.write("dummy_key")

                result = runner.invoke(
                    subscription,
                    ["purchase", "--chain-config", chain, "--key", "key.txt"],
                )

                assert result.exit_code == 0, f"Failed for chain {chain}"
                assert "NVM Subscription Purchased Successfully" in result.output

    @patch("mech_client.cli.commands.subscription_cmd.SubscriptionService")
    @patch("mech_client.cli.commands.subscription_cmd.setup_wallet_command")
    def test_subscription_purchase_output_format(
        self,
        mock_setup_wallet: MagicMock,
        mock_subscription_service: MagicMock,
    ) -> None:
        """Test subscription purchase output formatting."""
        # Mock wallet
        mock_wallet_ctx = MagicMock()
        mock_setup_wallet.return_value = mock_wallet_ctx

        # Mock service
        mock_service = MagicMock()
        mock_service.purchase_subscription.return_value = {
            "agreement_id": "0x1234567890abcdef",
            "agreement_tx_hash": "0xabcdef1234567890",
            "fulfillment_tx_hash": "0x567890abcdef1234",
            "credits_before": 12345,
            "credits_after": 1012345,
        }
        mock_subscription_service.return_value = mock_service

        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                subscription,
                ["purchase", "--chain-config", "gnosis", "--key", "key.txt"],
            )

            # Verify output contains all required fields
            assert result.exit_code == 0
            assert "Agreement ID: 0x1234567890abcdef" in result.output
            assert "Agreement Transaction: 0xabcdef1234567890" in result.output
            assert "Fulfillment Transaction: 0x567890abcdef1234" in result.output
            assert "Credits Before: 12345" in result.output
            assert "Credits After: 1012345" in result.output
            assert "Credits Gained: 1000000" in result.output
            # Verify formatting with separators
            assert "=" * 70 in result.output

    @patch("mech_client.cli.commands.subscription_cmd.SubscriptionService")
    @patch("mech_client.cli.commands.subscription_cmd.setup_wallet_command")
    def test_subscription_purchase_agent_mode(
        self,
        mock_setup_wallet: MagicMock,
        mock_subscription_service: MagicMock,
    ) -> None:
        """Test subscription purchase in agent mode."""
        # Mock wallet in agent mode
        mock_wallet_ctx = MagicMock()
        mock_wallet_ctx.agent_mode = True
        mock_wallet_ctx.crypto = MagicMock()
        mock_wallet_ctx.safe_address = "0xsafe123..."
        mock_wallet_ctx.ethereum_client = MagicMock()
        mock_setup_wallet.return_value = mock_wallet_ctx

        # Mock service
        mock_service = MagicMock()
        mock_service.purchase_subscription.return_value = {
            "agreement_id": "0xabc...",
            "agreement_tx_hash": "0xdef...",
            "fulfillment_tx_hash": "0xghi...",
            "credits_before": 0,
            "credits_after": 1000000,
        }
        mock_subscription_service.return_value = mock_service

        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                subscription,
                ["purchase", "--chain-config", "gnosis", "--key", "key.txt"],
            )

            # Should succeed in agent mode
            assert result.exit_code == 0
            assert "NVM Subscription Purchased Successfully" in result.output

            # Verify service was created with agent mode parameters
            call_kwargs = mock_subscription_service.call_args[1]
            assert call_kwargs["agent_mode"] is True
            assert call_kwargs["safe_address"] == "0xsafe123..."


class TestSubscriptionCommandGroup:
    """Tests for subscription command group."""

    def test_subscription_help(self) -> None:
        """Test subscription help output."""
        runner = CliRunner()
        result = runner.invoke(subscription, ["--help"])

        assert result.exit_code == 0
        assert "Manage Nevermined (NVM) subscriptions" in result.output
        assert "purchase" in result.output
        assert "subscription-based" in result.output.lower()

    def test_subscription_purchase_help(self) -> None:
        """Test subscription purchase help output."""
        runner = CliRunner()
        result = runner.invoke(subscription, ["purchase", "--help"])

        assert result.exit_code == 0
        assert "Purchase a Nevermined (NVM) subscription" in result.output
        assert "chain-config" in result.output
        assert "Gnosis and Base" in result.output

    def test_subscription_no_subcommand(self) -> None:
        """Test subscription without subcommand shows help."""
        runner = CliRunner()
        result = runner.invoke(subscription, [])

        # Should show help or error about missing subcommand
        assert result.exit_code != 1 or "Usage:" in result.output

    def test_subscription_invalid_subcommand(self) -> None:
        """Test subscription with invalid subcommand."""
        runner = CliRunner()
        result = runner.invoke(subscription, ["invalid"])

        # Should fail with error
        assert result.exit_code != 0


class TestSubscriptionEdgeCases:
    """Tests for edge cases in subscription command."""

    def test_subscription_purchase_uppercase_chain(self) -> None:
        """Test subscription purchase with uppercase chain config."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                subscription,
                ["purchase", "--chain-config", "GNOSIS", "--key", "key.txt"],
            )

            # Should fail - validator requires lowercase
            assert result.exit_code == 1
            assert "Invalid chain configuration" in result.output

    @patch("mech_client.cli.commands.subscription_cmd.SubscriptionService")
    @patch("mech_client.cli.commands.subscription_cmd.setup_wallet_command")
    def test_subscription_purchase_large_credits(
        self,
        mock_setup_wallet: MagicMock,
        mock_subscription_service: MagicMock,
    ) -> None:
        """Test subscription purchase with very large credit values."""
        # Mock wallet
        mock_wallet_ctx = MagicMock()
        mock_setup_wallet.return_value = mock_wallet_ctx

        # Mock service with large credit values
        mock_service = MagicMock()
        mock_service.purchase_subscription.return_value = {
            "agreement_id": "0xabc...",
            "agreement_tx_hash": "0xdef...",
            "fulfillment_tx_hash": "0xghi...",
            "credits_before": 999999999999999999,
            "credits_after": 1000000999999999999,
        }
        mock_subscription_service.return_value = mock_service

        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                subscription,
                ["purchase", "--chain-config", "gnosis", "--key", "key.txt"],
            )

            # Should handle large numbers correctly
            assert result.exit_code == 0
            assert "999999999999999999" in result.output
            assert "1000000999999999999" in result.output
            # Credits gained should be calculated correctly
            assert "Credits Gained: 1000000000000" in result.output

    def test_subscription_purchase_with_extra_args(self) -> None:
        """Test subscription purchase with unexpected extra arguments."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("key.txt", "w") as f:
                f.write("dummy_key")

            result = runner.invoke(
                subscription,
                ["purchase", "extra_arg", "--chain-config", "gnosis", "--key", "key.txt"],
            )

            # Should fail - no positional arguments expected
            assert result.exit_code != 0
