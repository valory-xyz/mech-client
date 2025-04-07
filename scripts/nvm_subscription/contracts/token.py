# subscription/contracts/transfer_nft.py
import logging
from typing import Union
from web3 import Web3
from eth_typing import ChecksumAddress
from web3.types import ENS

from .base_contract import BaseContract

logger = logging.getLogger(__name__)


class SubscriptionToken(BaseContract):
    """
    Wrapper for the Token smart contract. Supports approve token
    """

    def __init__(self, w3: Web3):
        """
        Initialize the Token instance.

        Args:
            w3 (Web3): A connected Web3 instance.
        """
        logger.debug("Initializing Subscription Token")
        super().__init__(w3, name="SubscriptionToken")
        logger.info("Token initialized")

    def build_approve_token_tx(
        self,
        sender: Union[ChecksumAddress, ENS],
        to: Union[ChecksumAddress, ENS],
        amount: int,
        gas: int = 60_000,
        chain_id: int = 100,
    ) -> bytes:
        """
        Compute the hash of parameters for the transfer condition.

        Args:
            sender (ChecksumAddress | ENS): Address sending the approve tx.
            to_address (ChecksumAddress | ENS): Address getting the approval.
            amount (int): Number of tokens to approve.
            gas (int, optional): Gas limit. Defaults to 60,000.
            chain_id (int, optional): Ethereum network chain ID. Defaults to 100.

        Returns:
            Dict[str, Any]: Unsigned transaction dictionary.
        """
        logger.debug("Approving token...")
        sender_address: ChecksumAddress = self.w3.to_checksum_address(sender)
        to_address: ChecksumAddress = self.w3.to_checksum_address(to)
        nonce = self.w3.eth.get_transaction_count(sender_address)
        logger.debug(f"Nonce for sender {sender_address}: {nonce}")

        latest_block = self.w3.eth.get_block("latest")
        base_fee = latest_block["baseFeePerGas"]
        max_priority_fee = self.w3.eth.max_priority_fee

        tx = (
            self.functions()
            .approve(
                to_address,
                amount,
            )
            .build_transaction(
                {
                    "from": sender,
                    "value": 0,
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

        logger.info("Transaction built successfully for token approve")
        logger.debug(f"Transaction details: {tx}")
        return tx
