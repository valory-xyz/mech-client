# subscription/contracts/transfer_nft.py
import logging
from typing import Union, List, Any, Dict
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

    def build_fulfill_for_delegate_tx(
        self,
        agreement_id: str,
        data: List,
        lock_payment_condition: str,
        sender: str,
        value_eth: float,
        gas: int = 600_000,
        chain_id: int = 100,
    ) -> Dict[str, Any]:
        sender_address: ChecksumAddress = self.w3.to_checksum_address(sender)
        nonce = self.w3.eth.get_transaction_count(sender_address)
        logger.debug(f"Nonce for sender {sender_address}: {nonce}")

        latest_block = self.w3.eth.get_block("latest")
        base_fee = latest_block["baseFeePerGas"]
        max_priority_fee = self.w3.eth.max_priority_fee

        # Build the transaction using the contract method
        tx = (
            self.functions()
            .fulfillForDelegate(
                agreement_id,
                "0x" + data[0],
                data[3],
                sender,
                int(data[2]),
                lock_payment_condition,
                data[4],
                False,
                int(data[7]),
            )
            .build_transaction(
                {
                    "from": sender_address,
                    "value": self.w3.to_wei(value_eth, "ether"),
                    "chainId": chain_id,
                    "gas": gas,
                    "nonce": nonce,
                }
            )
        )
        gas = self.w3.eth.estimate_gas(tx)
        tx.update(
            {
                "gas": gas,
                "maxFeePerGas": base_fee + max_priority_fee,
                "maxPriorityFeePerGas": max_priority_fee,
            }
        )

        logger.info("Transaction built successfully for fulfill for delegate")
        logger.debug(f"Transaction details: {tx}")
        return tx
