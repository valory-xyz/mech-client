# subscription/contracts/lock_payment.py
import logging
from typing import List, Union
from web3 import Web3
from eth_typing import ChecksumAddress
from web3.types import ENS

from .base_contract import BaseContract

logger = logging.getLogger(__name__)


class AgreementStorageManagerContract(BaseContract):
    """
    Wrapper class for the LockPaymentCondition smart contract.
    Provides methods for computing hash and generating IDs.
    """

    def __init__(self, w3: Web3):
        """
        Initialize the LockPaymentConditionContract.

        Args:
            w3 (Web3): An instance of Web3 connected to the target Ethereum network.
        """
        logger.debug("Initializing AgreementStoreManager")
        super().__init__(w3, name="AgreementStoreManager")
        logger.info("AgreementStoreManagerContract initialized")

    def agreement_id(self, agreement_id_seed: str, subscriber: str) -> bytes:
        """
        Generate a condition ID for a given agreement ID and hash.

        Args:
            agreement_id_seed (str): Seed for the agreement ID.
            subscriber (str): Address of the subscriber.

        Returns:
            bytes: The condition ID.
        """
        logger.debug("Generating condition ID from agreement ID and hash")
        agreement_id = self.functions().agreementId(agreement_id_seed, subscriber).call()
        logger.info(f"Generated condition ID: {agreement_id.hex()}")
        return agreement_id
