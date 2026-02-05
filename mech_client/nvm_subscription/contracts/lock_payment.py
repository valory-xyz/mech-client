# subscription/contracts/lock_payment.py
import logging
from typing import List, Union
from web3 import Web3
from eth_typing import ChecksumAddress
from web3.types import ENS

from .base_contract import BaseContract

logger = logging.getLogger(__name__)


class LockPaymentConditionContract(BaseContract):
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
        logger.debug("Initializing LockPaymentConditionContract")
        super().__init__(w3, name="LockPaymentCondition")
        logger.info("LockPaymentConditionContract initialized")

    def hash_values(
        self,
        did: str,
        reward_address: Union[ChecksumAddress, ENS],
        token_address: Union[ChecksumAddress, ENS],
        amounts: List[int],
        receivers: List[Union[ChecksumAddress, ENS]]
    ) -> bytes:
        """
        Compute the hash of the condition parameters.

        Args:
            did (str): The decentralized identifier.
            reward_address (ChecksumAddress | ENS): Address to receive the reward.
            token_address (ChecksumAddress | ENS): ERC20 token address.
            amounts (List[int]): List of amounts for each receiver.
            receivers (List[ChecksumAddress | ENS]): List of receiver addresses.

        Returns:
            bytes: The keccak256 hash of the encoded values.
        """
        logger.debug("Computing hash for lock payment condition")
        hash_ = self.functions().hashValues(
            did,
            reward_address,
            token_address,
            amounts,
            receivers
        ).call()
        logger.debug(f"Computed hash: {hash_.hex()}")
        return hash_

    def generate_id(self, agreement_id: bytes, hash_value: bytes) -> bytes:
        """
        Generate a condition ID for a given agreement ID and hash.

        Args:
            agreement_id (str): ID of the agreement.
            hash_value (bytes): Hashed condition parameters.

        Returns:
            bytes: The condition ID.
        """
        logger.debug("Generating condition ID from agreement ID and hash")
        condition_id = self.functions().generateId(agreement_id, hash_value).call()
        logger.info(f"Generated condition ID: {condition_id.hex()}")
        return condition_id
