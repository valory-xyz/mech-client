# subscription/manager.py
from enum import Enum
import json
import logging
import os
import sys
import requests

import uuid
from typing import Any, Dict, List, Literal, Union
from web3 import Web3
from eth_account import Account
from eth_typing import ChecksumAddress

from .contracts.did_registry import DIDRegistryContract
from .contracts.nft_sales import NFTSalesTemplateContract
from .contracts.lock_payment import LockPaymentConditionContract
from .contracts.transfer_nft import TransferNFTConditionContract
from .contracts.escrow_payment import EscrowPaymentConditionContract
from .contracts.agreement_manager import AgreementStorageManagerContract
from .contracts.token import SubscriptionToken
from .contracts.nft import SubscriptionNFT
from .contracts.subscription_provider import SubscriptionProvider

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(BASE_DIR, 'resources', 'networks.json')
CONFIGS = json.load(open(config_path, 'r'))

class Network(Enum):
    GNOSIS = "GNOSIS"
    BASE = "BASE"


def get_variable_value(variable: str) -> str:
    try:
        var = os.getenv(variable)
        if var is None:
            raise ValueError(f"Environment variable {variable} not found")
        return var
    except Exception as e:
        raise e


class NVMSubscriptionManager:
    """
    Manages the process of creating NFT-based subscription agreements
    using a series of smart contracts.
    """

    def __init__(self, network: str, private_key: str):
        """
        Initialize the SubscriptionManager, including contract instances
        and Web3 connection.
        """
        self.url = os.getenv("MECHX_CHAIN_RPC", CONFIGS[network]["nvm"]['web3ProviderUri'])
        self.web3 = Web3(Web3.HTTPProvider(self.url))

        self.account = Account.from_key(private_key)
        self.sender: ChecksumAddress = self.web3.to_checksum_address(self.account.address)

        self.did_registry = DIDRegistryContract(self.web3)
        self.nft_sales = NFTSalesTemplateContract(self.web3)
        self.lock_payment = LockPaymentConditionContract(self.web3)
        self.transfer_nft = TransferNFTConditionContract(self.web3)
        self.escrow_payment = EscrowPaymentConditionContract(self.web3)
        self.subscription_nft = SubscriptionNFT(self.web3)
        self.subscription_provider = SubscriptionProvider(self.web3)

        # load the subscription token to be used for base
        if network == 'BASE':
            self.subscription_token = SubscriptionToken(self.web3)

        self.agreement_storage_manager = AgreementStorageManagerContract(self.web3)

        self.token_address = self.web3.to_checksum_address(get_variable_value("TOKEN_ADDRESS"))
        self.subscription_nft_address = self.web3.to_checksum_address(get_variable_value("SUBSCRIPTION_NFT_ADDRESS"))
        self.subscription_credits = int(os.getenv("SUBSCRIPTION_CREDITS", "1"))
        self.amounts = [int(os.getenv("PLAN_FEE_NVM", "0")), int(os.getenv("PLAN_PRICE_MECHS", "0"))]
        self.subscription_id = CONFIGS[network]["nvm"]["subscription_id"]

        logger.info("SubscriptionManager initialized")

    def _generate_agreement_id_seed(self, length: int = 64) -> str:
        """Generate a random hex string prefixed with 0x."""
        seed = ''
        while len(seed) < length:
            seed += uuid.uuid4().hex
        return '0x' + seed[:length]

    def create_subscription(self, did: str, wallet_pvt_key: str, chain_id: int) -> Dict[str, Any]:
        """
        Execute the workflow to create a subscription for the given DID.

        Args:
            did (str): Decentralized Identifier for the asset.

        Returns:
            Dict[str, Any]: A dictionary containing transaction status and receipt.
        """
        logger.info(f"Creating subscription for DID: {did}")

        did = did.replace("did:nv:", "0x")

        ddo = self.did_registry.get_ddo(did)
        service = next((s for s in ddo.get("service", []) if s.get("type") == "nft-sales"), None)
        if not service:
            logger.error("No nft-sales service found in DDO")
            return {"status": "error", "message": "No nft-sales service in DDO"}

        self.publisher = service["templateId"]

        conditions = service["attributes"]["serviceAgreementTemplate"]["conditions"]
        reward_address = self.escrow_payment.address
        receivers = conditions[0]["parameters"][-1]["value"]

        agreement_id_seed = self._generate_agreement_id_seed()
        agreement_id = self.agreement_storage_manager.agreement_id(agreement_id_seed, self.sender)

        # Condition hashes
        lock_hash = self.lock_payment.hash_values(did, reward_address, self.token_address, self.amounts, receivers)
        lock_id = self.lock_payment.generate_id(agreement_id, lock_hash)

        transfer_hash = self.transfer_nft.hash_values(
            did,
            ddo["owner"],
            self.sender,
            self.subscription_credits,
            lock_id,
            self.subscription_nft_address,
            False
        )
        transfer_id = self.transfer_nft.generate_id(agreement_id, transfer_hash)

        escrow_hash = self.escrow_payment.hash_values(
            did,
            self.amounts,
            receivers,
            self.sender,
            reward_address,
            self.token_address,
            lock_id,
            transfer_id
        )
        escrow_id = self.escrow_payment.generate_id(agreement_id, escrow_hash)

        user_credit_balance_before = self.subscription_nft.get_balance(
            self.sender, self.subscription_id
        )
        print(f"Sender credits Before Purchase: {user_credit_balance_before}")

        # we set value as xdai is used as subscription for gnosis
        value_eth = 1
        if chain_id == 8453:
            # for base, usdc is used and so we don't send any value
            value_eth = 0

            approve_tx = self.subscription_token.build_approve_token_tx(
                sender=self.sender,
                to=self.lock_payment.address,
                amount=10**6,
                chain_id=chain_id,
            )
            signed_tx = self.web3.eth.account.sign_transaction(approve_tx, private_key=wallet_pvt_key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)

            if receipt["status"] == 1:
                logger.info("Approve transaction validated successfully")
                logger.info({"status": "success", "tx_hash": tx_hash.hex()})
            else:
                logger.error("Approve transaction failed")
                return {"status": "failed", "receipt": dict(receipt)}

        # Build transaction
        tx = self.nft_sales.build_create_agreement_tx(
            agreement_id_seed=agreement_id_seed,
            did=did,
            condition_seeds=[lock_hash, transfer_hash, escrow_hash],
            timelocks=[0, 0, 0],
            timeouts=[0, 90, 0],
            publisher=self.sender,
            service_index=0,
            reward_address=reward_address,
            token_address=self.token_address,
            amounts=self.amounts,
            receivers=receivers,
            sender=self.sender,
            value_eth=value_eth,
            chain_id=chain_id
        )

        signed_tx = self.web3.eth.account.sign_transaction(tx, private_key=wallet_pvt_key)
        tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
        receipt = self.web3.eth.wait_for_transaction_receipt(transaction_hash=tx_hash)

        if receipt["status"] == 1:
            logger.info("Subscription transaction validated successfully")
            logger.info({"status": "success", "tx_hash": tx_hash.hex()})
        else:
            logger.error("Subscription transaction failed")
            return {"status": "failed", "receipt": dict(receipt)}

        fulfill_for_delegate_params = (
            # nftHolder
            ddo["owner"],
            # nftReceiver
            self.sender,
            # nftAmount
            self.subscription_credits,
            # lockPaymentCondition
            "0x" + lock_id.hex(),
            # nftContractAddress
            self.subscription_nft_address,
            # transfer
            False,
            # expirationBlock
            0,
        )

        fulfill_params = (
            # amounts
            self.amounts,
            # receivers
            receivers,
            # returnAddress
            self.sender,
            # lockPaymentAddress
            reward_address,
            # tokenAddress
            self.token_address,
            # lockCondition
            "0x" + lock_id.hex(),
            # releaseCondition
            "0x" + transfer_id.hex(),
        )

        fulfill_tx = self.subscription_provider.build_create_fulfill_tx(
            agreement_id_seed="0x" + agreement_id.hex(),
            did=did,
            fulfill_for_delegate_params=fulfill_for_delegate_params,
            fulfill_params=fulfill_params,
            sender=self.sender,
            value_eth=0,
            chain_id=chain_id,
        )

        signed_tx = self.web3.eth.account.sign_transaction(
            fulfill_tx, private_key=wallet_pvt_key
        )
        tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
        receipt = self.web3.eth.wait_for_transaction_receipt(transaction_hash=tx_hash)

        user_credit_balance_after = self.subscription_nft.get_balance(
            self.sender, self.subscription_id
        )
        print(f"Sender credits After Purchase: {user_credit_balance_after}")

        if receipt["status"] == 1:
            logger.info("Subscription purchased transaction successfully")
            return {"status": "success", "tx_hash": tx_hash.hex()}
        else:
            logger.error("Subscription purchase transaction failed")
            return {"status": "failed", "receipt": dict(receipt)}
