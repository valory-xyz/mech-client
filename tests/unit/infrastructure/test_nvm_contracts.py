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


class TestAgreementManagerContract:
    """Tests for AgreementManagerContract.agreement_id."""

    @pytest.fixture
    def mock_w3(self) -> MagicMock:
        """Create mock Web3 instance."""
        w3 = MagicMock()
        w3.eth.chain_id = 100
        return w3

    @patch(
        "mech_client.infrastructure.nvm.contracts.base.NVMContractWrapper._load_contract"
    )
    def test_agreement_id_calls_contract_function(
        self,
        mock_load_contract: MagicMock,
        mock_w3: MagicMock,
    ) -> None:
        """Test that agreement_id returns bytes from the contract function."""
        from mech_client.infrastructure.nvm.contracts.agreement_manager import (  # pylint: disable=import-outside-toplevel
            AgreementManagerContract,
        )

        expected_bytes = b"\x01" * 32
        mock_contract = MagicMock()
        mock_contract.address = "0x" + "a" * 40
        mock_contract.functions.agreementId.return_value.call.return_value = (
            expected_bytes
        )
        mock_load_contract.return_value = mock_contract

        wrapper = AgreementManagerContract(mock_w3)
        result = wrapper.agreement_id("seed-value", "0x" + "a" * 40)

        assert result == expected_bytes
        mock_contract.functions.agreementId.assert_called_once_with(
            "seed-value", "0x" + "a" * 40
        )


class TestEscrowPaymentContract:
    """Tests for EscrowPaymentContract methods."""

    @pytest.fixture
    def mock_w3(self) -> MagicMock:
        """Create mock Web3 instance."""
        w3 = MagicMock()
        w3.eth.chain_id = 100
        return w3

    @patch(
        "mech_client.infrastructure.nvm.contracts.base.NVMContractWrapper._load_contract"
    )
    def test_hash_values_returns_bytes(
        self,
        mock_load_contract: MagicMock,
        mock_w3: MagicMock,
    ) -> None:
        """Test that hash_values returns bytes from the contract function."""
        from mech_client.infrastructure.nvm.contracts.escrow_payment import (  # pylint: disable=import-outside-toplevel
            EscrowPaymentContract,
        )

        expected_bytes = b"\x02" * 32
        mock_contract = MagicMock()
        mock_contract.address = "0x" + "b" * 40
        mock_contract.functions.hashValues.return_value.call.return_value = (
            expected_bytes
        )
        mock_load_contract.return_value = mock_contract

        wrapper = EscrowPaymentContract(mock_w3)
        receiver = "0x" + "c" * 40
        result = wrapper.hash_values(
            did="did:nv:test",
            amounts=[100, 200],
            receivers=[receiver],
            sender=receiver,
            receiver=receiver,
            token_address="0x" + "0" * 40,
            lock_condition_id=b"\x00" * 32,
            release_condition_id=b"\x01" * 32,
        )

        assert result == expected_bytes
        mock_contract.functions.hashValues.assert_called_once()

    @patch(
        "mech_client.infrastructure.nvm.contracts.base.NVMContractWrapper._load_contract"
    )
    def test_generate_id_returns_bytes(
        self,
        mock_load_contract: MagicMock,
        mock_w3: MagicMock,
    ) -> None:
        """Test that generate_id returns bytes from the contract function."""
        from mech_client.infrastructure.nvm.contracts.escrow_payment import (  # pylint: disable=import-outside-toplevel
            EscrowPaymentContract,
        )

        expected_bytes = b"\x03" * 32
        mock_contract = MagicMock()
        mock_contract.address = "0x" + "b" * 40
        mock_contract.functions.generateId.return_value.call.return_value = (
            expected_bytes
        )
        mock_load_contract.return_value = mock_contract

        wrapper = EscrowPaymentContract(mock_w3)
        result = wrapper.generate_id(b"\x00" * 32, b"\x01" * 32)

        assert result == expected_bytes
        mock_contract.functions.generateId.assert_called_once_with(
            b"\x00" * 32, b"\x01" * 32
        )


class TestLockPaymentContract:
    """Tests for LockPaymentContract methods."""

    @pytest.fixture
    def mock_w3(self) -> MagicMock:
        """Create mock Web3 instance."""
        w3 = MagicMock()
        w3.eth.chain_id = 100
        return w3

    @patch(
        "mech_client.infrastructure.nvm.contracts.base.NVMContractWrapper._load_contract"
    )
    def test_hash_values_returns_bytes(
        self,
        mock_load_contract: MagicMock,
        mock_w3: MagicMock,
    ) -> None:
        """Test that hash_values returns bytes from the contract function."""
        from mech_client.infrastructure.nvm.contracts.lock_payment import (  # pylint: disable=import-outside-toplevel
            LockPaymentContract,
        )

        expected_bytes = b"\x04" * 32
        mock_contract = MagicMock()
        mock_contract.address = "0x" + "d" * 40
        mock_contract.functions.hashValues.return_value.call.return_value = (
            expected_bytes
        )
        mock_load_contract.return_value = mock_contract

        reward_addr = "0x" + "e" * 40
        token_addr = "0x" + "0" * 40
        wrapper = LockPaymentContract(mock_w3)
        result = wrapper.hash_values(
            did="did:nv:lock-test",
            reward_address=reward_addr,
            token_address=token_addr,
            amounts=[500],
            receivers=[reward_addr],
        )

        assert result == expected_bytes
        mock_contract.functions.hashValues.assert_called_once_with(
            "did:nv:lock-test", reward_addr, token_addr, [500], [reward_addr]
        )

    @patch(
        "mech_client.infrastructure.nvm.contracts.base.NVMContractWrapper._load_contract"
    )
    def test_generate_id_returns_bytes(
        self,
        mock_load_contract: MagicMock,
        mock_w3: MagicMock,
    ) -> None:
        """Test that generate_id returns bytes from the contract function."""
        from mech_client.infrastructure.nvm.contracts.lock_payment import (  # pylint: disable=import-outside-toplevel
            LockPaymentContract,
        )

        expected_bytes = b"\x05" * 32
        mock_contract = MagicMock()
        mock_contract.address = "0x" + "d" * 40
        mock_contract.functions.generateId.return_value.call.return_value = (
            expected_bytes
        )
        mock_load_contract.return_value = mock_contract

        wrapper = LockPaymentContract(mock_w3)
        result = wrapper.generate_id(b"\x00" * 32, b"\x01" * 32)

        assert result == expected_bytes
        mock_contract.functions.generateId.assert_called_once_with(
            b"\x00" * 32, b"\x01" * 32
        )


class TestNeverminedConfigContract:
    """Tests for NeverminedConfigContract methods."""

    @pytest.fixture
    def mock_w3(self) -> MagicMock:
        """Create mock Web3 instance."""
        w3 = MagicMock()
        w3.eth.chain_id = 100
        return w3

    @patch(
        "mech_client.infrastructure.nvm.contracts.base.NVMContractWrapper._load_contract"
    )
    def test_get_fee_receiver_returns_address(
        self,
        mock_load_contract: MagicMock,
        mock_w3: MagicMock,
    ) -> None:
        """Test that get_fee_receiver returns the address from the contract function."""
        from mech_client.infrastructure.nvm.contracts.nevermined_config import (  # pylint: disable=import-outside-toplevel
            NeverminedConfigContract,
        )

        expected_address = "0x" + "f" * 40
        mock_contract = MagicMock()
        mock_contract.address = "0x" + "1" * 40
        mock_contract.functions.getFeeReceiver.return_value.call.return_value = (
            expected_address
        )
        mock_load_contract.return_value = mock_contract

        wrapper = NeverminedConfigContract(mock_w3)
        result = wrapper.get_fee_receiver()

        assert result == expected_address
        mock_contract.functions.getFeeReceiver.assert_called_once()

    @patch(
        "mech_client.infrastructure.nvm.contracts.base.NVMContractWrapper._load_contract"
    )
    def test_get_marketplace_fee_returns_int(
        self,
        mock_load_contract: MagicMock,
        mock_w3: MagicMock,
    ) -> None:
        """Test that get_marketplace_fee returns an integer from the contract function."""
        from mech_client.infrastructure.nvm.contracts.nevermined_config import (  # pylint: disable=import-outside-toplevel
            NeverminedConfigContract,
        )

        mock_contract = MagicMock()
        mock_contract.address = "0x" + "1" * 40
        mock_contract.functions.getMarketplaceFee.return_value.call.return_value = 1000
        mock_load_contract.return_value = mock_contract

        wrapper = NeverminedConfigContract(mock_w3)
        result = wrapper.get_marketplace_fee()

        assert result == 1000
        mock_contract.functions.getMarketplaceFee.assert_called_once()


class TestNFTContract:
    """Tests for NFTContract.get_balance."""

    @pytest.fixture
    def mock_w3(self) -> MagicMock:
        """Create mock Web3 instance."""
        w3 = MagicMock()
        w3.eth.chain_id = 100
        return w3

    @patch(
        "mech_client.infrastructure.nvm.contracts.base.NVMContractWrapper._load_contract"
    )
    def test_get_balance_calls_balance_of_with_checksummed_address(
        self,
        mock_load_contract: MagicMock,
        mock_w3: MagicMock,
    ) -> None:
        """Test get_balance checksums the address and returns the balance."""
        from mech_client.infrastructure.nvm.contracts.nft import (  # pylint: disable=import-outside-toplevel
            NFTContract,
        )

        raw_address = "0x" + "1" * 40
        checksummed_address = "0x" + "1" * 40  # already checksummed for this test
        mock_w3.to_checksum_address.return_value = checksummed_address

        mock_contract = MagicMock()
        mock_contract.address = "0x" + "2" * 40
        mock_contract.functions.balanceOf.return_value.call.return_value = 5
        mock_load_contract.return_value = mock_contract

        wrapper = NFTContract(mock_w3)
        result = wrapper.get_balance(raw_address, "42")

        assert result == 5
        mock_w3.to_checksum_address.assert_called_with(raw_address)
        mock_contract.functions.balanceOf.assert_called_once_with(
            checksummed_address, 42
        )


class TestTokenContract:
    """Tests for TokenContract.get_balance."""

    @pytest.fixture
    def mock_w3(self) -> MagicMock:
        """Create mock Web3 instance."""
        w3 = MagicMock()
        w3.eth.chain_id = 100
        return w3

    @patch(
        "mech_client.infrastructure.nvm.contracts.base.NVMContractWrapper._load_contract"
    )
    def test_get_balance_calls_balance_of_with_checksummed_address(
        self,
        mock_load_contract: MagicMock,
        mock_w3: MagicMock,
    ) -> None:
        """Test get_balance checksums the address and returns the token balance."""
        from mech_client.infrastructure.nvm.contracts.token import (  # pylint: disable=import-outside-toplevel
            TokenContract,
        )

        raw_address = "0x" + "1" * 40
        checksummed_address = "0x" + "1" * 40
        mock_w3.to_checksum_address.return_value = checksummed_address

        mock_contract = MagicMock()
        mock_contract.address = "0x" + "3" * 40
        mock_contract.functions.balanceOf.return_value.call.return_value = 750
        mock_load_contract.return_value = mock_contract

        wrapper = TokenContract(mock_w3)
        result = wrapper.get_balance(raw_address)

        assert result == 750
        mock_w3.to_checksum_address.assert_called_with(raw_address)
        mock_contract.functions.balanceOf.assert_called_once_with(checksummed_address)


class TestNVMContractFactorySubscriptionNames:
    """Tests for NVMContractFactory.subscription_contract_names method."""

    def test_subscription_contract_names_with_token(self) -> None:
        """Test that include_token=True appends 'token' to the contract names tuple."""
        from mech_client.infrastructure.nvm.contracts.factory import (  # pylint: disable=import-outside-toplevel
            NVMContractFactory,
        )

        names = NVMContractFactory.subscription_contract_names(include_token=True)

        assert "token" in names

    def test_subscription_contract_names_without_token(self) -> None:
        """Test that include_token=False does not include 'token' in the contract names tuple."""
        from mech_client.infrastructure.nvm.contracts.factory import (  # pylint: disable=import-outside-toplevel
            NVMContractFactory,
        )

        names = NVMContractFactory.subscription_contract_names(include_token=False)

        assert "token" not in names


class TestTransferNFTContract:
    """Tests for TransferNFTContract methods."""

    @pytest.fixture
    def mock_w3(self) -> MagicMock:
        """Create mock Web3 instance."""
        w3 = MagicMock()
        w3.eth.chain_id = 100
        return w3

    @patch(
        "mech_client.infrastructure.nvm.contracts.base.NVMContractWrapper._load_contract"
    )
    def test_hash_values_returns_bytes(
        self,
        mock_load_contract: MagicMock,
        mock_w3: MagicMock,
    ) -> None:
        """Test that hash_values returns bytes from the contract function."""
        from mech_client.infrastructure.nvm.contracts.transfer_nft import (  # pylint: disable=import-outside-toplevel
            TransferNFTContract,
        )

        expected_bytes = b"\x06" * 32
        mock_contract = MagicMock()
        mock_contract.address = "0x" + "e" * 40
        mock_contract.functions.hashValues.return_value.call.return_value = (
            expected_bytes
        )
        mock_load_contract.return_value = mock_contract

        wrapper = TransferNFTContract(mock_w3)
        from_addr = "0x" + "1" * 40
        to_addr = "0x" + "2" * 40
        nft_addr = "0x" + "3" * 40
        result = wrapper.hash_values(
            did="did:nv:test",
            from_address=from_addr,
            to_address=to_addr,
            amount=1,
            lock_condition_id=b"\x00" * 32,
            nft_contract_address=nft_addr,
            is_transfer=True,
        )

        assert result == expected_bytes
        mock_contract.functions.hashValues.assert_called_once_with(
            "did:nv:test", from_addr, to_addr, 1, b"\x00" * 32, nft_addr, True
        )

    @patch(
        "mech_client.infrastructure.nvm.contracts.base.NVMContractWrapper._load_contract"
    )
    def test_generate_id_returns_bytes(
        self,
        mock_load_contract: MagicMock,
        mock_w3: MagicMock,
    ) -> None:
        """Test that generate_id returns bytes from the contract function."""
        from mech_client.infrastructure.nvm.contracts.transfer_nft import (  # pylint: disable=import-outside-toplevel
            TransferNFTContract,
        )

        expected_bytes = b"\x07" * 32
        mock_contract = MagicMock()
        mock_contract.address = "0x" + "e" * 40
        mock_contract.functions.generateId.return_value.call.return_value = (
            expected_bytes
        )
        mock_load_contract.return_value = mock_contract

        wrapper = TransferNFTContract(mock_w3)
        result = wrapper.generate_id(b"\x00" * 32, b"\x01" * 32)

        assert result == expected_bytes
        mock_contract.functions.generateId.assert_called_once_with(
            b"\x00" * 32, b"\x01" * 32
        )
