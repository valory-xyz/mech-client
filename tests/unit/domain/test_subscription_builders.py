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

"""Tests for domain.subscription builders."""

from unittest.mock import MagicMock, patch

import pytest

from mech_client.domain.subscription.agreement import AgreementBuilder
from mech_client.domain.subscription.balance_checker import SubscriptionBalanceChecker
from mech_client.domain.subscription.fulfillment import FulfillmentBuilder


class TestAgreementBuilder:
    """Tests for AgreementBuilder."""

    @pytest.fixture
    def mock_config(self) -> MagicMock:
        """Create mock NVM configuration."""
        config = MagicMock()
        config.receiver_plan = "0x" + "1" * 40
        return config

    @pytest.fixture
    def mock_contracts(self) -> dict:
        """Create mock NVM contracts."""
        did_registry = MagicMock()
        did_registry.get_ddo.return_value = {
            "owner": "0x" + "2" * 40,
            "metadata": "test",
        }

        agreement_manager = MagicMock()
        agreement_manager.agreement_id.return_value = bytes.fromhex("a" * 64)

        lock_payment = MagicMock()
        lock_payment.generate_id.return_value = bytes.fromhex("b" * 64)
        lock_payment.hash_values.return_value = bytes.fromhex("c" * 64)

        transfer_nft = MagicMock()
        transfer_nft.generate_id.return_value = bytes.fromhex("d" * 64)
        transfer_nft.hash_values.return_value = bytes.fromhex("e" * 64)

        escrow_payment = MagicMock()
        escrow_payment.generate_id.return_value = bytes.fromhex("f" * 64)
        escrow_payment.hash_values.return_value = bytes.fromhex("1" * 64)

        nevermined_config = MagicMock()
        nevermined_config.get_fee_receiver.return_value = "0x" + "3" * 40

        return {
            "did_registry": did_registry,
            "agreement_manager": agreement_manager,
            "lock_payment": lock_payment,
            "transfer_nft": transfer_nft,
            "escrow_payment": escrow_payment,
            "nevermined_config": nevermined_config,
        }

    @pytest.fixture
    def builder(self, mock_config: MagicMock, mock_contracts: dict) -> AgreementBuilder:
        """Create AgreementBuilder instance."""
        return AgreementBuilder(
            config=mock_config,
            sender="0x1234567890123456789012345678901234567890",
            did_registry=mock_contracts["did_registry"],
            agreement_manager=mock_contracts["agreement_manager"],
            lock_payment=mock_contracts["lock_payment"],
            transfer_nft=mock_contracts["transfer_nft"],
            escrow_payment=mock_contracts["escrow_payment"],
            nevermined_config_contract=mock_contracts["nevermined_config"],
        )

    def test_build_agreement_success(
        self,
        builder: AgreementBuilder,
        mock_contracts: dict,
    ) -> None:
        """Test successful agreement building."""
        plan_did = "did:nvm:test123"

        result = builder.build(plan_did)

        # Verify agreement ID generation called
        mock_contracts["agreement_manager"].agreement_id.assert_called_once()

        # Verify DDO fetched
        mock_contracts["did_registry"].get_ddo.assert_called_once_with(plan_did)

        # Verify condition IDs generated
        assert mock_contracts["lock_payment"].generate_id.called
        assert mock_contracts["transfer_nft"].generate_id.called
        assert mock_contracts["escrow_payment"].generate_id.called

        # Verify result has expected attributes
        assert hasattr(result, "agreement_id")
        assert hasattr(result, "did")
        assert hasattr(result, "ddo")
        assert result.did == plan_did

    def test_build_agreement_ddo_fetch_failure(
        self,
        builder: AgreementBuilder,
        mock_contracts: dict,
    ) -> None:
        """Test agreement building fails if DDO fetch fails."""
        mock_contracts["did_registry"].get_ddo.side_effect = RuntimeError(
            "DDO not found"
        )

        with pytest.raises(RuntimeError, match="DDO not found"):
            builder.build("did:nvm:invalid")


class TestFulfillmentBuilder:
    """Tests for FulfillmentBuilder."""

    @pytest.fixture
    def mock_config(self) -> MagicMock:
        """Create mock NVM configuration."""
        config = MagicMock()
        config.subscription_credits = "100"
        config.subscription_nft_address = "0x" + "1" * 40
        config.plan_fee_nvm = "500000"
        config.plan_price_mechs = "500000"
        config.receiver_plan = "0x" + "2" * 40
        return config

    @pytest.fixture
    def mock_agreement(self) -> MagicMock:
        """Create mock agreement data."""
        agreement = MagicMock()
        agreement.ddo = {"owner": "0x" + "3" * 40}
        agreement.lock_id = bytes.fromhex("a" * 64)
        agreement.transfer_id = bytes.fromhex("b" * 64)
        agreement.escrow_id = bytes.fromhex("c" * 64)
        agreement.receivers = ["0x" + "4" * 40, "0x" + "5" * 40]
        agreement.reward_address = "0x" + "6" * 40
        return agreement

    @pytest.fixture
    def builder(self, mock_config: MagicMock) -> FulfillmentBuilder:
        """Create FulfillmentBuilder instance."""
        return FulfillmentBuilder(
            config=mock_config,
            sender="0x1234567890123456789012345678901234567890",
        )

    def test_build_fulfillment_success(
        self,
        builder: FulfillmentBuilder,
        mock_agreement: MagicMock,
    ) -> None:
        """Test successful fulfillment building."""
        result = builder.build(mock_agreement)

        # Verify result has expected attributes
        assert hasattr(result, "fulfill_for_delegate_params")
        assert hasattr(result, "fulfill_params")

        # Verify fulfill_for_delegate_params structure (tuple)
        assert isinstance(result.fulfill_for_delegate_params, tuple)
        assert len(result.fulfill_for_delegate_params) == 7

        # Verify first elements match expected values
        assert result.fulfill_for_delegate_params[0] == "0x" + "3" * 40  # nftHolder
        assert (
            result.fulfill_for_delegate_params[1]
            == "0x1234567890123456789012345678901234567890"
        )  # nftReceiver
        assert result.fulfill_for_delegate_params[2] == 100  # nftAmount

        # Verify fulfill_params structure (tuple)
        assert isinstance(result.fulfill_params, tuple)
        assert len(result.fulfill_params) == 7  # amounts, receivers, sender, reward_address, token_address, lock_id, escrow_id


class TestSubscriptionBalanceChecker:
    """Tests for SubscriptionBalanceChecker."""

    @pytest.fixture
    def mock_w3(self) -> MagicMock:
        """Create mock Web3 instance."""
        w3 = MagicMock()
        w3.eth.get_balance.return_value = 10**18  # 1 ETH
        return w3

    @pytest.fixture
    def mock_config_gnosis(self) -> MagicMock:
        """Create mock NVM configuration for Gnosis."""
        config = MagicMock()
        config.requires_token_approval.return_value = False
        config.get_total_payment_amount.return_value = 10**17  # 0.1 ETH
        config.native_token = "xDAI"
        return config

    @pytest.fixture
    def mock_config_base(self) -> MagicMock:
        """Create mock NVM configuration for Base."""
        config = MagicMock()
        config.requires_token_approval.return_value = True
        config.get_total_payment_amount.return_value = 5 * 10**6  # 5 USDC (6 decimals)
        config.native_token = "ETH"
        return config

    @pytest.fixture
    def mock_token_contract(self) -> MagicMock:
        """Create mock token contract."""
        token = MagicMock()
        token.get_balance.return_value = 10 * 10**6  # 10 USDC
        return token

    def test_check_balance_gnosis_sufficient(
        self,
        mock_w3: MagicMock,
        mock_config_gnosis: MagicMock,
    ) -> None:
        """Test balance check passes with sufficient native balance on Gnosis."""
        checker = SubscriptionBalanceChecker(
            w3=mock_w3,
            config=mock_config_gnosis,
            sender="0x1234567890123456789012345678901234567890",
            token_contract=None,
        )

        # Should not raise
        checker.check()

    def test_check_balance_gnosis_insufficient(
        self,
        mock_w3: MagicMock,
        mock_config_gnosis: MagicMock,
    ) -> None:
        """Test balance check fails with insufficient native balance on Gnosis."""
        mock_w3.eth.get_balance.return_value = 10**16  # 0.01 ETH (insufficient)

        checker = SubscriptionBalanceChecker(
            w3=mock_w3,
            config=mock_config_gnosis,
            sender="0x1234567890123456789012345678901234567890",
            token_contract=None,
        )

        with pytest.raises(ValueError, match="Insufficient .* balance"):
            checker.check()

    def test_check_balance_base_sufficient(
        self,
        mock_w3: MagicMock,
        mock_config_base: MagicMock,
        mock_token_contract: MagicMock,
    ) -> None:
        """Test balance check passes with sufficient USDC balance on Base."""
        checker = SubscriptionBalanceChecker(
            w3=mock_w3,
            config=mock_config_base,
            sender="0x1234567890123456789012345678901234567890",
            token_contract=mock_token_contract,
        )

        # Should not raise
        checker.check()

    def test_check_balance_base_insufficient(
        self,
        mock_w3: MagicMock,
        mock_config_base: MagicMock,
        mock_token_contract: MagicMock,
    ) -> None:
        """Test balance check fails with insufficient USDC balance on Base."""
        mock_token_contract.get_balance.return_value = 2 * 10**6  # 2 USDC (insufficient)

        checker = SubscriptionBalanceChecker(
            w3=mock_w3,
            config=mock_config_base,
            sender="0x1234567890123456789012345678901234567890",
            token_contract=mock_token_contract,
        )

        with pytest.raises(ValueError, match="Insufficient .* balance"):
            checker.check()

    def test_check_balance_base_missing_token_contract(
        self,
        mock_w3: MagicMock,
        mock_config_base: MagicMock,
    ) -> None:
        """Test balance check fails if token contract missing on Base."""
        checker = SubscriptionBalanceChecker(
            w3=mock_w3,
            config=mock_config_base,
            sender="0x1234567890123456789012345678901234567890",
            token_contract=None,  # Missing
        )

        with pytest.raises(ValueError, match="Token contract required"):
            checker.check()
