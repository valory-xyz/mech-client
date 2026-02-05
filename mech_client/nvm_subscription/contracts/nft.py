# subscription/contracts/transfer_nft.py
import logging
from typing import Union
from web3 import Web3
from eth_typing import ChecksumAddress
from web3.types import ENS

from .base_contract import BaseContract

logger = logging.getLogger(__name__)


class SubscriptionNFT(BaseContract):
    """
    Wrapper for the Token smart contract. Supports token balance
    """

    def __init__(self, w3: Web3):
        """
        Initialize the Subscription NFT instance.

        Args:
            w3 (Web3): A connected Web3 instance.
        """
        logger.debug("Initializing Subscription NFT")
        super().__init__(w3, name="SubscriptionNFT")
        logger.info("Subscription NFT initialized")

    def get_balance(
        self, sender: Union[ChecksumAddress, ENS], subscription_id: str
    ) -> int:
        """
        Gets the user subscription credit balance.

        Args:
            sender (ChecksumAddress | ENS): User address.

        Returns:
            int: The user's credit balance.
        """
        sender_address: ChecksumAddress = self.w3.to_checksum_address(sender)

        balance = (
            self.functions().balanceOf(sender_address, int(subscription_id)).call()
        )
        logger.debug(f"Fetched Balance: {balance}")
        return balance
