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

"""Agreement builder for NVM subscriptions."""

import logging
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List

from mech_client.infrastructure.nvm.config import NVMConfig
from mech_client.infrastructure.nvm.contracts import (
    AgreementManagerContract,
    DIDRegistryContract,
    EscrowPaymentContract,
    LockPaymentContract,
    NeverminedConfigContract,
    TransferNFTContract,
)


logger = logging.getLogger(__name__)


@dataclass
class AgreementData:  # pylint: disable=too-many-instance-attributes
    """Data structure for subscription agreement."""

    agreement_id_seed: str
    agreement_id: bytes
    did: str
    ddo: Dict[str, Any]
    condition_seeds: List[bytes]
    timelocks: List[int]
    timeouts: List[int]
    reward_address: str
    receivers: List[str]
    lock_id: bytes
    transfer_id: bytes
    escrow_id: bytes


class AgreementBuilder:  # pylint: disable=too-few-public-methods,too-many-instance-attributes
    """Builds agreement data structures for NVM subscription creation."""

    def __init__(  # pylint: disable=too-many-arguments
        self,
        config: NVMConfig,
        sender: str,
        did_registry: DIDRegistryContract,
        agreement_manager: AgreementManagerContract,
        lock_payment: LockPaymentContract,
        transfer_nft: TransferNFTContract,
        escrow_payment: EscrowPaymentContract,
        nevermined_config_contract: NeverminedConfigContract,
    ):
        """
        Initialize the agreement builder.

        :param config: NVM configuration
        :param sender: Sender address
        :param did_registry: DID registry contract
        :param agreement_manager: Agreement manager contract
        :param lock_payment: Lock payment contract
        :param transfer_nft: Transfer NFT contract
        :param escrow_payment: Escrow payment contract
        :param nevermined_config_contract: Nevermined config contract
        """
        self.config = config
        self.sender = sender
        self.did_registry = did_registry
        self.agreement_manager = agreement_manager
        self.lock_payment = lock_payment
        self.transfer_nft = transfer_nft
        self.escrow_payment = escrow_payment
        self.nevermined_config = nevermined_config_contract

    @staticmethod
    def _generate_agreement_id_seed(length: int = 64) -> str:
        """
        Generate a random hex string prefixed with 0x.

        :param length: Length of the hex string (default 64)
        :return: Random hex string
        """
        seed = ""
        while len(seed) < length:
            seed += uuid.uuid4().hex
        return "0x" + seed[:length]

    def build(self, plan_did: str) -> AgreementData:  # pylint: disable=too-many-locals
        """
        Build agreement data for subscription purchase.

        :param plan_did: Plan DID (with or without "did:nv:" prefix)
        :return: Agreement data structure
        """
        logger.info(f"Building agreement for DID: {plan_did}")

        # Normalize DID format
        did = plan_did.replace("did:nv:", "0x")

        # Fetch DDO from registry
        ddo = self.did_registry.get_ddo(did)

        # Get fee receiver from config
        fee_receiver = self.nevermined_config.get_fee_receiver()
        if not fee_receiver:
            raise ValueError("Marketplace fee receiver not found")

        # Build receivers list: [fee_receiver, plan_receiver]
        receivers: List[str] = [fee_receiver, self.config.receiver_plan]

        # Generate agreement ID
        agreement_id_seed = self._generate_agreement_id_seed()
        agreement_id = self.agreement_manager.agreement_id(
            agreement_id_seed, self.sender
        )

        # Reward address is the escrow payment contract
        reward_address = self.escrow_payment.address

        # Prepare amounts [fee, price]
        amounts = [
            int(self.config.plan_fee_nvm),
            int(self.config.plan_price_mechs),
        ]

        # Compute condition hashes
        lock_hash = self.lock_payment.hash_values(
            did,
            reward_address,
            self.config.token_address,
            amounts,
            receivers,
        )
        lock_id = self.lock_payment.generate_id(agreement_id, lock_hash)

        transfer_hash = self.transfer_nft.hash_values(
            did,
            ddo["owner"],
            self.sender,
            int(self.config.subscription_credits),
            lock_id,
            self.config.subscription_nft_address,
            False,  # is_transfer
        )
        transfer_id = self.transfer_nft.generate_id(agreement_id, transfer_hash)

        escrow_hash = self.escrow_payment.hash_values(
            did,
            amounts,
            receivers,
            self.sender,
            reward_address,
            self.config.token_address,
            lock_id,
            transfer_id,
        )
        escrow_id = self.escrow_payment.generate_id(agreement_id, escrow_hash)

        logger.info(f"Agreement ID: {agreement_id.hex()}")
        logger.info(f"Lock ID: {lock_id.hex()}")
        logger.info(f"Transfer ID: {transfer_id.hex()}")
        logger.info(f"Escrow ID: {escrow_id.hex()}")

        return AgreementData(
            agreement_id_seed=agreement_id_seed,
            agreement_id=agreement_id,
            did=did,
            ddo=ddo,
            condition_seeds=[lock_hash, transfer_hash, escrow_hash],
            timelocks=[0, 0, 0],
            timeouts=[0, 90, 0],
            reward_address=reward_address,
            receivers=receivers,
            lock_id=lock_id,
            transfer_id=transfer_id,
            escrow_id=escrow_id,
        )
