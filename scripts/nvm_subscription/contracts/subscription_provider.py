# subscription/contracts/subscription_provider.py
import logging
from typing import Union, List, Dict, Any
from web3 import Web3
from eth_typing import ChecksumAddress
from web3.types import ENS

from .base_contract import BaseContract

logger = logging.getLogger(__name__)


class SubscriptionProvider(BaseContract):
    """
    Wrapper for the Token smart contract. Supports token balance
    """

    def __init__(self, w3: Web3):
        """
        Initialize the Subscription provider instance.

        Args:
            w3 (Web3): A connected Web3 instance.
        """
        logger.debug("Initializing Subscription provider")
        super().__init__(w3, name="SubscriptionProvider")
        logger.info("Subscription provider initialized")

    def build_create_fulfill_tx(
        self,
        agreement_id_seed: str,
        did: str,
        fulfill_for_delegate_params: tuple,
        fulfill_params: tuple,
        sender: str,
        value_eth: float,
        gas: int = 450_000,
        chain_id: int = 100,
    ) -> Dict[str, Any]:
        """
        Build a transaction dictionary to create a fulfill tx.

        Args:
            agreement_id_seed (str): Unique identifier seed for the agreement.
            did (str): Decentralized identifier.
            condition_seeds (List[bytes]): List of hashed condition values.
            timelocks (List[int]): Time locks for each condition.
            timeouts (List[int]): Timeouts for each condition.
            publisher (str): Ethereum address of the publisher.
            service_index (int): Index of the service in the agreement.
            reward_address (str): Address to receive the reward.
            token_address (str): ERC20 token address.
            amounts (List[int]): Payment amounts.
            receivers (List[str]): List of payment receiver addresses.
            sender (str): Ethereum address initiating the transaction.
            value_eth (float): ETH value to include in the transaction.
            gas (int, optional): Gas limit. Defaults to 450,000.
            chain_id (int, optional): Ethereum network chain ID. Defaults to 100.

        Returns:
            Dict[str, Any]: Unsigned transaction dictionary.
        """
        logger.debug("Building transaction for fulfill")
        logger.debug(f"agreement_id_seed: {agreement_id_seed}")
        logger.debug(f"did: {did}")
        logger.debug(f"sender: {sender}, value_eth: {value_eth}")

        # Convert sender to a checksum address to ensure type safety
        sender_address: ChecksumAddress = self.w3.to_checksum_address(sender)
        nonce = self.w3.eth.get_transaction_count(sender_address)
        logger.debug(f"Nonce for sender {sender_address}: {nonce}")

        latest_block = self.w3.eth.get_block("latest")
        base_fee = latest_block["baseFeePerGas"]
        max_priority_fee = self.w3.eth.max_priority_fee

        logger.debug(f"fulfill_for_delegate_params: {fulfill_for_delegate_params}")
        logger.debug(f"fulfill_params: {fulfill_params}")

        # Build the transaction using the contract method
        tx = (
            self.functions()
            .fulfill(
                agreement_id_seed, did, fulfill_for_delegate_params, fulfill_params
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

        logger.info(f"Transaction built successfully for fulfill: {agreement_id_seed}")
        logger.debug(f"Transaction details: {tx}")
        return tx
