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

"""Factory for creating NVM contract wrapper instances."""

from typing import Dict, Iterable, Optional, Sequence, Tuple, Type

from web3 import Web3

from mech_client.infrastructure.nvm.contracts.agreement_manager import (
    AgreementManagerContract,
)
from mech_client.infrastructure.nvm.contracts.base import NVMContractWrapper
from mech_client.infrastructure.nvm.contracts.did_registry import DIDRegistryContract
from mech_client.infrastructure.nvm.contracts.escrow_payment import (
    EscrowPaymentContract,
)
from mech_client.infrastructure.nvm.contracts.lock_payment import LockPaymentContract
from mech_client.infrastructure.nvm.contracts.nevermined_config import (
    NeverminedConfigContract,
)
from mech_client.infrastructure.nvm.contracts.nft import NFTContract
from mech_client.infrastructure.nvm.contracts.nft_sales import NFTSalesTemplateContract
from mech_client.infrastructure.nvm.contracts.subscription_provider import (
    SubscriptionProviderContract,
)
from mech_client.infrastructure.nvm.contracts.token import TokenContract
from mech_client.infrastructure.nvm.contracts.transfer_nft import TransferNFTContract


class NVMContractFactory:
    """Factory for creating NVM contract wrapper instances."""

    # Map contract names to wrapper classes
    _CONTRACT_CLASSES: Dict[str, Type[NVMContractWrapper]] = {
        "agreement_manager": AgreementManagerContract,
        "did_registry": DIDRegistryContract,
        "escrow_payment": EscrowPaymentContract,
        "lock_payment": LockPaymentContract,
        "nevermined_config": NeverminedConfigContract,
        "nft": NFTContract,
        "nft_sales": NFTSalesTemplateContract,
        "subscription_provider": SubscriptionProviderContract,
        "token": TokenContract,
        "transfer_nft": TransferNFTContract,
    }

    # Standard contract set used by the NVM subscription workflow.
    _SUBSCRIPTION_CONTRACTS: Tuple[str, ...] = (
        "did_registry",
        "agreement_manager",
        "lock_payment",
        "transfer_nft",
        "escrow_payment",
        "nevermined_config",
        "nft_sales",
        "subscription_provider",
        "nft",
    )

    @classmethod
    def create(cls, w3: Web3, contract_name: str) -> NVMContractWrapper:
        """
        Create a contract wrapper instance.

        :param w3: Web3 instance
        :param contract_name: Name of the contract (e.g., "nft_sales", "token")
        :return: Contract wrapper instance
        :raises ValueError: If contract name is not supported
        """
        contract_class = cls._CONTRACT_CLASSES.get(contract_name)
        if not contract_class:
            raise ValueError(
                f"Unknown contract name {contract_name!r}. "
                f"Supported contracts: {', '.join(sorted(cls._CONTRACT_CLASSES.keys()))}"
            )

        return contract_class(w3)  # type: ignore[call-arg]

    @classmethod
    def create_all(
        cls, w3: Web3, contract_names: Optional[Sequence[str]] = None
    ) -> Dict[str, NVMContractWrapper]:
        """
        Create NVM contract wrappers.

        :param w3: Web3 instance
        :param contract_names: Optional list of contract names to create. If not
            provided, all supported contracts are created.
        :return: Dictionary mapping contract names to wrapper instances
        """
        names: Iterable[str] = contract_names or cls._CONTRACT_CLASSES.keys()
        return {name: cls.create(w3, name) for name in names}

    @classmethod
    def subscription_contract_names(cls, include_token: bool) -> Tuple[str, ...]:
        """Return the contract names required by the subscription workflow."""
        if include_token:
            return cls._SUBSCRIPTION_CONTRACTS + ("token",)
        return cls._SUBSCRIPTION_CONTRACTS
