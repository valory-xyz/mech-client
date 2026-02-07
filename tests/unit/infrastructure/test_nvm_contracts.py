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

"""Tests for infrastructure.nvm.contracts."""

from unittest.mock import MagicMock, patch

import pytest


class TestNVMContractFactory:
    """Tests for NVMContractFactory."""

    @pytest.fixture
    def mock_w3(self) -> MagicMock:
        """Create mock Web3 instance."""
        w3 = MagicMock()
        w3.eth.chain_id = 100  # Gnosis
        return w3

    @patch(
        "mech_client.infrastructure.nvm.contracts.base.NVMContractWrapper._load_contract"
    )
    def test_create_single_contract(
        self,
        mock_load_contract: MagicMock,
        mock_w3: MagicMock,
    ) -> None:
        """Test creating a single contract."""
        from mech_client.infrastructure.nvm.contracts.factory import (
            NVMContractFactory,
        )
        from mech_client.infrastructure.nvm.contracts.lock_payment import (
            LockPaymentContract,
        )

        # Mock the contract loading
        mock_contract = MagicMock()
        mock_load_contract.return_value = mock_contract

        result = NVMContractFactory.create(mock_w3, "lock_payment")

        # Verify result is correct type
        assert isinstance(result, LockPaymentContract)
        mock_load_contract.assert_called_once()

    def test_create_unknown_contract(self, mock_w3: MagicMock) -> None:
        """Test creating unknown contract raises ValueError."""
        from mech_client.infrastructure.nvm.contracts.factory import (
            NVMContractFactory,
        )

        with pytest.raises(ValueError, match="Unknown contract name"):
            NVMContractFactory.create(mock_w3, "invalid_contract")

    @patch(
        "mech_client.infrastructure.nvm.contracts.base.NVMContractWrapper._load_contract"
    )
    def test_create_all_contracts(
        self,
        mock_load_contract: MagicMock,
        mock_w3: MagicMock,
    ) -> None:
        """Test creating all contracts."""
        from mech_client.infrastructure.nvm.contracts.factory import (
            NVMContractFactory,
        )

        # Mock the contract loading
        mock_contract = MagicMock()
        mock_load_contract.return_value = mock_contract

        contracts = NVMContractFactory.create_all(mock_w3)

        # Verify all expected contracts created
        expected_contracts = [
            "agreement_manager",
            "did_registry",
            "lock_payment",
            "escrow_payment",
            "transfer_nft",
            "nevermined_config",
            "nft_sales",
            "subscription_provider",
            "nft",
            "token",
        ]

        for contract_name in expected_contracts:
            assert contract_name in contracts
            assert contracts[contract_name] is not None

        # Verify _load_contract was called for each contract (10 times)
        assert mock_load_contract.call_count == 10
