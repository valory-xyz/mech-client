# subscription/contracts/escrow_payment.py
import logging
from typing import List, Union
from web3 import Web3
from eth_typing import ChecksumAddress
from web3.types import ENS

from .base_contract import BaseContract

logger = logging.getLogger(__name__)


class EscrowPaymentConditionContract(BaseContract):
    """
    Wrapper for the EscrowPaymentCondition smart contract.
    Provides methods to hash values and generate condition IDs.
    """

    def __init__(self, w3: Web3):
        """
        Initialize the EscrowPaymentConditionContract.

        Args:
            w3 (Web3): A connected Web3 instance.
        """
        logger.debug("Initializing EscrowPaymentConditionContract")
        super().__init__(w3, name="EscrowPaymentCondition")
        logger.info("EscrowPaymentConditionContract initialized")

    def hash_values(
        self,
        did: str,
        amounts: List[int],
        receivers: List[Union[ChecksumAddress, ENS]],
        sender: Union[ChecksumAddress, ENS],
        receiver: Union[ChecksumAddress, ENS],
        token_address: Union[ChecksumAddress, ENS],
        lock_condition_id: bytes,
        release_condition_id: bytes
    ) -> bytes:
        """
        Compute the hash of parameters for escrow condition.

        Args:
            did (str): Decentralized identifier.
            amounts (List[int]): Payment amounts.
            receivers (List[ChecksumAddress | ENS]): Receiver addresses.
            sender (ChecksumAddress | ENS): Sender address.
            receiver (ChecksumAddress | ENS): Receiver address.
            token_address (ChecksumAddress | ENS): Token contract address.
            lock_condition_id (bytes): ID of the lock payment condition.
            release_condition_id (bytes): ID of the release condition.

        Returns:
            bytes: Hashed values.
        """
        logger.debug("Computing hash for escrow payment condition")
        hash_ = self.functions().hashValues(
            did,
            amounts,
            receivers,
            sender,
            receiver,
            token_address,
            lock_condition_id,
            release_condition_id
        ).call()
        logger.debug(f"Escrow payment hash: {hash_.hex()}")
        return hash_

    def generate_id(self, agreement_id: bytes, hash_value: bytes) -> bytes:
        """
        Generate the condition ID for the escrow payment.

        Args:
            agreement_id (str): Agreement identifier.
            hash_value (bytes): Hash of condition inputs.

        Returns:
            bytes: Generated condition ID.
        """
        logger.debug("Generating escrow payment condition ID")
        condition_id = self.functions().generateId(agreement_id, hash_value).call()
        logger.info(f"Escrow payment condition ID: {condition_id.hex()}")
        return condition_id
