# subscription/contracts/transfer_nft.py
import logging
from typing import Union
from web3 import Web3
from eth_typing import ChecksumAddress
from web3.types import ENS

from .base_contract import BaseContract

logger = logging.getLogger(__name__)


class TransferNFTConditionContract(BaseContract):
    """
    Wrapper for the TransferNFTCondition smart contract. Supports hash and ID generation.
    """

    def __init__(self, w3: Web3):
        """
        Initialize the TransferNFTConditionContract instance.

        Args:
            w3 (Web3): A connected Web3 instance.
        """
        logger.debug("Initializing TransferNFTConditionContract")
        super().__init__(w3, name="TransferNFTCondition")
        logger.info("TransferNFTConditionContract initialized")

    def hash_values(
        self,
        did: str,
        from_address: Union[ChecksumAddress, ENS],
        to_address: Union[ChecksumAddress, ENS],
        amount: int,
        lock_condition_id: bytes,
        nft_contract_address: Union[ChecksumAddress, ENS],
        _is_transfer: bool,
    ) -> bytes:
        """
        Compute the hash of parameters for the transfer condition.

        Args:
            did (str): Decentralized identifier.
            from_address (ChecksumAddress | ENS): Address sending the NFT.
            to_address (ChecksumAddress | ENS): Address receiving the NFT.
            amount (int): Number of tokens to transfer.
            lock_condition_id (bytes): Lock payment condition ID.
            nft_contract_address (ChecksumAddress | ENS): NFT contract address.
            is_escrow (bool): Indicates if escrow is involved.

        Returns:
            bytes: Hashed value.
        """
        logger.debug("Computing transfer NFT hash value")
        hash_ = self.functions().hashValues(
            did,
            from_address,
            to_address,
            amount,
            lock_condition_id,
            nft_contract_address,
            _is_transfer
        ).call()
        logger.debug(f"Transfer NFT hash: {hash_.hex()}")
        return hash_

    def generate_id(self, agreement_id: bytes, hash_value: bytes) -> bytes:
        """
        Generate the condition ID for the transfer NFT condition.

        Args:
            agreement_id (str): ID of the agreement.
            hash_value (bytes): Hashed condition parameters.

        Returns:
            bytes: Condition ID.
        """
        logger.debug("Generating transfer NFT condition ID")
        condition_id = self.functions().generateId(agreement_id, hash_value).call()
        logger.info(f"Transfer NFT condition ID: {condition_id.hex()}")
        return condition_id
