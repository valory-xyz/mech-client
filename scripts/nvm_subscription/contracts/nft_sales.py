# subscription/contracts/nft_sales.py
import logging
from typing import List, Any, Dict, Union
from web3 import Web3
from eth_typing import ChecksumAddress
from web3.types import ENS

from .base_contract import BaseContract

logger = logging.getLogger(__name__)


class NFTSalesTemplateContract(BaseContract):
    """
    Wrapper class for the NFTSalesTemplate smart contract. Provides a method
    to build a transaction for creating an agreement and paying escrow.
    """

    def __init__(self, w3: Web3):
        """
        Initialize the NFTSalesTemplateContract.

        Args:
            w3 (Web3): An instance of Web3 connected to an Ethereum network.
        """
        logger.debug("Initializing NFTSalesTemplateContract")
        super().__init__(w3, name="NFTSalesTemplate")
        logger.info("NFTSalesTemplateContract initialized")

    def build_create_agreement_tx(
        self,
        agreement_id_seed: str,
        did: str,
        condition_seeds: List[bytes],
        timelocks: List[int],
        timeouts: List[int],
        publisher: str,
        service_index: int,
        reward_address: str,
        token_address: str,
        amounts: List[int],
        receivers: List[str],
        sender: str,
        value_eth: float,
        gas: int = 600_000,
        chain_id: int = 100
    ) -> Dict[str, Any]:
        """
        Build a transaction dictionary to create an agreement and pay escrow.

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
            gas (int, optional): Gas limit. Defaults to 600,000.
            chain_id (int, optional): Ethereum network chain ID. Defaults to 100.

        Returns:
            Dict[str, Any]: Unsigned transaction dictionary.
        """
        logger.debug("Building transaction for createAgreementAndPayEscrow")
        logger.debug(f"agreement_id_seed: {agreement_id_seed}")
        logger.debug(f"did: {did}")
        logger.debug(f"condition_seeds: {condition_seeds}")
        logger.debug(f"timelocks: {timelocks}, timeouts: {timeouts}")
        logger.debug(f"publisher: {publisher}, service_index: {service_index}")
        logger.debug(f"reward_address: {reward_address}, token_address: {token_address}")
        logger.debug(f"amounts: {amounts}, receivers: {receivers}")
        logger.debug(f"sender: {sender}, value_eth: {value_eth}")

        # Convert sender to a checksum address to ensure type safety
        sender_address: ChecksumAddress = self.w3.to_checksum_address(sender)
        nonce = self.w3.eth.get_transaction_count(sender_address)
        logger.debug(f"Nonce for sender {sender_address}: {nonce}")

        latest_block = self.w3.eth.get_block("latest")
        base_fee = latest_block["baseFeePerGas"]
        max_priority_fee = self.w3.eth.max_priority_fee

        # Build the transaction using the contract method
        tx = self.functions().createAgreementAndPayEscrow(
            agreement_id_seed,
            did,
            condition_seeds,
            timelocks,
            timeouts,
            self.w3.to_checksum_address(publisher),
            service_index,
            self.w3.to_checksum_address(reward_address),
            self.w3.to_checksum_address(token_address),
            amounts,
            [self.w3.to_checksum_address(r) for r in receivers]
        ).build_transaction({
            "from": sender_address,
            "value": self.w3.to_wei(value_eth, "ether"),
            "chainId": chain_id,
            "gas": gas,
            "nonce": nonce,
        })
        gas = self.w3.eth.estimate_gas(tx)
        tx.update({
            "gas": gas,
            "maxFeePerGas": base_fee + max_priority_fee,
            "maxPriorityFeePerGas": max_priority_fee,
        })

        logger.info(f"Transaction built successfully for agreement ID: {agreement_id_seed}")
        logger.debug(f"Transaction details: {tx}")
        return tx
