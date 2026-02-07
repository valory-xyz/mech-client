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

"""NVM subscription contract wrappers."""

from mech_client.infrastructure.nvm.contracts.agreement_manager import (
    AgreementManagerContract,
)
from mech_client.infrastructure.nvm.contracts.base import NVMContractWrapper
from mech_client.infrastructure.nvm.contracts.did_registry import DIDRegistryContract
from mech_client.infrastructure.nvm.contracts.escrow_payment import (
    EscrowPaymentContract,
)
from mech_client.infrastructure.nvm.contracts.factory import NVMContractFactory
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


__all__ = [
    "NVMContractWrapper",
    "NVMContractFactory",
    "AgreementManagerContract",
    "DIDRegistryContract",
    "EscrowPaymentContract",
    "LockPaymentContract",
    "NeverminedConfigContract",
    "NFTContract",
    "NFTSalesTemplateContract",
    "SubscriptionProviderContract",
    "TokenContract",
    "TransferNFTContract",
]
