import logging
from typing import Dict, Any
from web3 import Web3

from .base_contract import BaseContract

logger = logging.getLogger(__name__)


class NeverminedConfigContract(BaseContract):
    """
    Wrapper for the NeverminedConfig contract.
    Exposes marketplace fee and fee receiver.
    """

    def __init__(self, w3: Web3):
        logger.debug("Initializing NeverminedConfig contract")
        super().__init__(w3, name="NeverminedConfig")
        logger.info("NeverminedConfig initialized")

    def get_fee_receiver(self) -> str:
        """Return the configured fee receiver address."""
        return self.functions().getFeeReceiver().call()

    def get_marketplace_fee(self) -> int:
        """Return the marketplace fee in ppm (1e6 = 100%)."""
        return self.functions().getMarketplaceFee().call()