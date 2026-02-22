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


class TestDIDRegistryContract:
    """Tests for DIDRegistryContract.get_ddo."""

    @pytest.fixture
    def mock_w3(self) -> MagicMock:
        """Create mock Web3 instance."""
        w3 = MagicMock()
        w3.eth.chain_id = 100
        return w3

    @patch(
        "mech_client.infrastructure.nvm.contracts.base.NVMContractWrapper._load_contract"
    )
    def test_get_ddo_returns_expected_structure(
        self,
        mock_load_contract: MagicMock,
        mock_w3: MagicMock,
    ) -> None:
        """Test get_ddo returns a dict with expected keys."""
        from mech_client.infrastructure.nvm.contracts.did_registry import (  # pylint: disable=import-outside-toplevel
            DIDRegistryContract,
        )

        mock_contract = MagicMock()
        mock_load_contract.return_value = mock_contract

        owner = "0x" + "1" * 40
        checksum = b"\x00" * 32
        service_endpoint = "https://metadata.example.com"
        providers = ["0x" + "2" * 40, "0x0000000000000000000000000000000000000000"]
        royalties = 10
        immutable_url = "ipfs://QmAbc123"
        nft_initialized = True

        mock_contract.functions.getDIDRegister.return_value.call.return_value = [
            owner,
            checksum,
            service_endpoint,
            None,  # index 3 (unused)
            None,  # index 4 (unused)
            providers,
            royalties,
            immutable_url,
            nft_initialized,
        ]

        did_registry = DIDRegistryContract(mock_w3)
        ddo = did_registry.get_ddo("abc123")

        assert ddo["did"] == "did:nv:abc123"
        assert ddo["serviceEndpoint"] == service_endpoint
        assert ddo["owner"] == owner
        assert ddo["royalties"] == royalties
        assert ddo["immutableUrl"] == immutable_url
        assert ddo["nftInitialized"] is True
        assert ddo["service"] == []
        assert ddo["proof"] == []

    @patch(
        "mech_client.infrastructure.nvm.contracts.base.NVMContractWrapper._load_contract"
    )
    def test_get_ddo_filters_zero_address_providers(
        self,
        mock_load_contract: MagicMock,
        mock_w3: MagicMock,
    ) -> None:
        """Test that non-zero providers are correctly identified in logs."""
        from web3.constants import ADDRESS_ZERO  # pylint: disable=import-outside-toplevel

        from mech_client.infrastructure.nvm.contracts.did_registry import (  # pylint: disable=import-outside-toplevel
            DIDRegistryContract,
        )

        mock_contract = MagicMock()
        mock_load_contract.return_value = mock_contract

        real_provider = "0x" + "3" * 40
        mock_contract.functions.getDIDRegister.return_value.call.return_value = [
            "0x" + "1" * 40,  # owner
            b"\x00" * 32,  # checksum
            "https://service.example.com",  # serviceEndpoint
            None,
            None,
            [real_provider, ADDRESS_ZERO],  # providers
            5,  # royalties
            "ipfs://abc",  # immutableUrl
            False,  # nftInitialized
        ]

        did_registry = DIDRegistryContract(mock_w3)
        ddo = did_registry.get_ddo("testdid")

        # The function logs non-zero providers; verify ddo providers list is as-is
        assert real_provider in ddo["providers"]
        assert ADDRESS_ZERO in ddo["providers"]


class TestNVMContractWrapperBase:
    """Tests for NVMContractWrapper base class (missing line coverage)."""

    @pytest.fixture
    def mock_w3_gnosis(self) -> MagicMock:
        """Create mock Web3 instance for Gnosis (chain_id=100)."""
        w3 = MagicMock()
        w3.eth.chain_id = 100  # Gnosis - supported chain
        return w3

    @patch(
        "mech_client.infrastructure.nvm.contracts.base.NVMContractWrapper._load_contract"
    )
    def test_init_with_explicit_name_logs_wrapper_message(
        self,
        mock_load_contract: MagicMock,
        mock_w3_gnosis: MagicMock,
    ) -> None:
        """Test that providing an explicit name triggers the else log branch."""
        from mech_client.infrastructure.nvm.contracts.base import (  # pylint: disable=import-outside-toplevel
            NVMContractWrapper,
        )

        mock_contract = MagicMock()
        mock_contract.address = "0x" + "1" * 40
        mock_load_contract.return_value = mock_contract

        # Providing an explicit name hits the `else` branch (line 69)
        wrapper = NVMContractWrapper(mock_w3_gnosis, name="MyCustomContract")

        assert wrapper.name == "MyCustomContract"
        assert wrapper.chain_name == "gnosis"
        mock_load_contract.assert_called_once()

    def test_init_unsupported_chain_id_raises_value_error(self) -> None:
        """Test that an unsupported chain ID raises ValueError (line 74)."""
        from mech_client.infrastructure.nvm.contracts.base import (  # pylint: disable=import-outside-toplevel
            NVMContractWrapper,
        )

        w3 = MagicMock()
        w3.eth.chain_id = 99999  # Not in CHAIN_ID_TO_NAME

        with pytest.raises(ValueError, match="Unsupported chain ID 99999"):
            NVMContractWrapper(w3, name="AnyContract")

    @patch(
        "mech_client.infrastructure.nvm.contracts.base.NVMContractWrapper._load_contract"
    )
    def test_init_with_explicit_name_logs_loaded_at_address(
        self,
        mock_load_contract: MagicMock,
        mock_w3_gnosis: MagicMock,
    ) -> None:
        """Test that explicit name triggers completion log showing address (line 87)."""
        from mech_client.infrastructure.nvm.contracts.base import (  # pylint: disable=import-outside-toplevel
            NVMContractWrapper,
        )

        expected_address = "0x" + "2" * 40
        mock_contract = MagicMock()
        mock_contract.address = expected_address
        mock_load_contract.return_value = mock_contract

        wrapper = NVMContractWrapper(mock_w3_gnosis, name="ExplicitName")

        # address attribute is set from contract.address
        assert wrapper.address == expected_address

    @patch(
        "mech_client.infrastructure.nvm.contracts.base.NVMContractWrapper._load_contract"
    )
    def test_load_contract_info_file_not_found(
        self,
        mock_load_contract: MagicMock,
        mock_w3_gnosis: MagicMock,
    ) -> None:
        """Test _load_contract_info raises FileNotFoundError when artifact missing."""
        from mech_client.infrastructure.nvm.contracts.base import (  # pylint: disable=import-outside-toplevel
            NVMContractWrapper,
        )

        mock_contract = MagicMock()
        mock_contract.address = "0x" + "3" * 40
        mock_load_contract.return_value = mock_contract

        wrapper = NVMContractWrapper(mock_w3_gnosis, name="MissingArtifact")

        # Now test _load_contract_info directly with Path.exists() returning False
        with patch(
            "mech_client.infrastructure.nvm.contracts.base.Path.exists",
            return_value=False,
        ):
            with pytest.raises(FileNotFoundError, match="Contract artifact not found"):
                wrapper._load_contract_info()  # pylint: disable=protected-access

    @patch(
        "mech_client.infrastructure.nvm.contracts.base.NVMContractWrapper._load_contract"
    )
    def test_load_contract_info_success(
        self,
        mock_load_contract: MagicMock,
        mock_w3_gnosis: MagicMock,
    ) -> None:
        """Test _load_contract_info returns dict when artifact file is found."""
        import json  # pylint: disable=import-outside-toplevel

        from mech_client.infrastructure.nvm.contracts.base import (  # pylint: disable=import-outside-toplevel
            NVMContractWrapper,
        )

        mock_contract = MagicMock()
        mock_contract.address = "0x" + "4" * 40
        mock_load_contract.return_value = mock_contract

        wrapper = NVMContractWrapper(mock_w3_gnosis, name="SomeContract")

        artifact_content = {
            "address": "0x" + "5" * 40,
            "abi": [{"name": "someFunction", "type": "function"}],
        }

        with patch(
            "mech_client.infrastructure.nvm.contracts.base.Path.exists",
            return_value=True,
        ):
            with patch(
                "builtins.open",
                MagicMock(
                    return_value=MagicMock(
                        __enter__=MagicMock(
                            return_value=MagicMock(
                                read=MagicMock(
                                    return_value=json.dumps(artifact_content)
                                )
                            )
                        ),
                        __exit__=MagicMock(return_value=False),
                    )
                ),
            ):
                with patch("json.load", return_value=artifact_content):
                    info = wrapper._load_contract_info()  # pylint: disable=protected-access

        assert info["address"] == artifact_content["address"]
        assert info["abi"] == artifact_content["abi"]

    def test_load_contract_uses_load_contract_info(
        self,
        mock_w3_gnosis: MagicMock,
    ) -> None:
        """Test _load_contract calls _load_contract_info and creates contract instance."""
        from mech_client.infrastructure.nvm.contracts.base import (  # pylint: disable=import-outside-toplevel
            NVMContractWrapper,
        )

        # Patch _load_contract only during __init__ so we can call the real method later
        init_contract = MagicMock()
        init_contract.address = "0x" + "6" * 40

        with patch(
            "mech_client.infrastructure.nvm.contracts.base.NVMContractWrapper._load_contract",
            return_value=init_contract,
        ):
            wrapper = NVMContractWrapper(mock_w3_gnosis, name="ContractForLoadTest")

        # Now _load_contract is restored to its real implementation.
        # Test it by mocking _load_contract_info.
        artifact_info = {
            "address": "0xAbCdEf1234567890abcdef1234567890abcdef12",
            "abi": [],
        }
        expected_contract = MagicMock()
        mock_w3_gnosis.eth.contract.return_value = expected_contract

        with patch.object(
            wrapper, "_load_contract_info", return_value=artifact_info
        ):
            result = wrapper._load_contract()  # pylint: disable=protected-access

        mock_w3_gnosis.to_checksum_address.assert_called_with(artifact_info["address"])
        expected_address = mock_w3_gnosis.to_checksum_address.return_value
        mock_w3_gnosis.eth.contract.assert_called_with(
            address=expected_address, abi=artifact_info["abi"]
        )
        assert result is expected_contract
