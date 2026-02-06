# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2025 Valory AG
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
# ------------------------------------------------------------------------------

"""Marketplace service for orchestrating mech requests."""

from dataclasses import asdict
from typing import Any, Dict, List, Optional, Tuple

from aea.crypto.base import Crypto as EthereumCrypto
from aea_ledger_ethereum import EthereumApi
from safe_eth.eth import EthereumClient
from web3.contract import Contract as Web3Contract

from mech_client.domain.delivery import OnchainDeliveryWatcher
from mech_client.domain.execution import ExecutorFactory, TransactionExecutor
from mech_client.domain.payment import PaymentStrategyFactory
from mech_client.domain.tools import ToolManager
from mech_client.infrastructure.blockchain.abi_loader import get_abi
from mech_client.infrastructure.blockchain.contracts import get_contract
from mech_client.infrastructure.blockchain.receipt_waiter import (
    wait_for_receipt,
    watch_for_marketplace_request_ids,
)
from mech_client.infrastructure.config import MechConfig, PaymentType, get_mech_config
from mech_client.infrastructure.ipfs import IPFSClient, push_metadata_to_ipfs


class MarketplaceService:
    """Service for orchestrating mech marketplace requests.

    Composes payment strategies, execution strategies, tool management,
    and delivery watching to provide high-level marketplace operations.
    """

    def __init__(
        self,
        chain_config: str,
        agent_mode: bool,
        private_key: str,
        safe_address: Optional[str] = None,
        ethereum_client: Optional[EthereumClient] = None,
    ):
        """
        Initialize marketplace service.

        :param chain_config: Chain configuration name (gnosis, base, etc.)
        :param agent_mode: True for agent mode (Safe), False for client mode (EOA)
        :param private_key: Private key for signing transactions
        :param safe_address: Safe address (required for agent mode)
        :param ethereum_client: Ethereum client (required for agent mode)
        """
        self.chain_config = chain_config
        self.agent_mode = agent_mode
        self.private_key = private_key
        self.safe_address = safe_address
        self.ethereum_client = ethereum_client

        # Load configuration
        self.mech_config: MechConfig = get_mech_config(chain_config)
        self.ledger_api = EthereumApi(**asdict(self.mech_config.ledger_config))
        self.crypto = EthereumCrypto(private_key)

        # Create executor
        self.executor: TransactionExecutor = ExecutorFactory.create(
            agent_mode=agent_mode,
            ledger_api=self.ledger_api,
            private_key=private_key,
            safe_address=safe_address,
            ethereum_client=ethereum_client,
        )

        # Create tool manager
        self.tool_manager = ToolManager(chain_config)

        # Create IPFS client
        self.ipfs_client = IPFSClient()

    async def send_request(
        self,
        prompts: Tuple[str, ...],
        tools: Tuple[str, ...],
        priority_mech: Optional[str] = None,
        use_prepaid: bool = False,
        use_offchain: bool = False,
        mech_offchain_url: Optional[str] = None,
        extra_attributes: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Send marketplace request(s) to mech(s).

        :param prompts: Tuple of prompt strings
        :param tools: Tuple of tool identifiers
        :param priority_mech: Priority mech address (optional)
        :param use_prepaid: Use prepaid balance instead of per-request payment
        :param use_offchain: Use offchain mech (requires mech_offchain_url)
        :param mech_offchain_url: URL for offchain mech
        :param extra_attributes: Extra attributes for metadata
        :param timeout: Timeout for delivery watching
        :return: Dictionary with request results
        """
        # Validate inputs
        if len(prompts) != len(tools):
            raise ValueError(
                f"Number of prompts ({len(prompts)}) must match number of tools ({len(tools)})"
            )

        # Validate tools exist
        self._validate_tools(tools)

        # Get marketplace contract
        marketplace_contract = self._get_marketplace_contract()

        # Fetch mech info (payment type, service ID, etc.)
        payment_type, service_id, max_delivery_rate = self._fetch_mech_info(
            priority_mech
        )

        # Create payment strategy
        payment_strategy = PaymentStrategyFactory.create(
            payment_type=payment_type,
            ledger_api=self.ledger_api,
            chain_id=self.mech_config.ledger_config.chain_id,
            crypto=self.crypto,
        )

        # Prepare metadata and upload to IPFS
        data_hashes = []
        for prompt, tool in zip(prompts, tools):
            data_hash, _ = push_metadata_to_ipfs(prompt, tool, extra_attributes or {})
            data_hashes.append(data_hash)

        # Handle payment (approval if needed)
        if not use_prepaid and payment_type.is_token():
            balance_tracker = payment_strategy.get_balance_tracker_address()
            price = self.mech_config.price * len(prompts)

            # Check balance
            sender = self.executor.get_sender_address()
            if not payment_strategy.check_balance(sender, price):
                raise ValueError(
                    f"Insufficient balance. Need: {price}, Have: {payment_strategy.check_balance(sender, 0)}"
                )

            # Approve if needed
            payment_strategy.approve_if_needed(
                payer_address=sender,
                spender_address=balance_tracker,
                amount=price,
                private_key=self.private_key,
            )

        # Send marketplace request
        tx_hash = self._send_marketplace_request(
            marketplace_contract=marketplace_contract,
            data_hashes=data_hashes,
            payment_type=payment_type,
            use_prepaid=use_prepaid,
        )

        # Wait for receipt and get request IDs
        receipt = wait_for_receipt(tx_hash, self.ledger_api)
        request_ids = watch_for_marketplace_request_ids(
            marketplace_contract, self.ledger_api, tx_hash
        )

        # Watch for delivery (if not offchain)
        results = {}
        if not use_offchain:
            watcher = OnchainDeliveryWatcher(
                marketplace_contract, self.ledger_api, timeout
            )
            results = await watcher.watch(request_ids)

        return {
            "tx_hash": tx_hash,
            "request_ids": request_ids,
            "delivery_results": results,
            "receipt": receipt,
        }

    def _validate_tools(self, tools: Tuple[str, ...]) -> None:
        """
        Validate that tools exist for the service.

        :param tools: Tuple of tool identifiers
        :raises ValueError: If any tool is invalid
        """
        # For marketplace mechs, tools are validated against service metadata
        # This is a placeholder - full validation would check service metadata
        for tool in tools:
            if not tool:
                raise ValueError("Empty tool identifier")

    def _get_marketplace_contract(self) -> Web3Contract:
        """
        Get marketplace contract instance.

        :return: Marketplace contract
        :raises ValueError: If marketplace not available on this chain
        """
        if not self.mech_config.mech_marketplace_contract:
            raise ValueError(
                f"Marketplace contract not available on {self.chain_config}"
            )

        abi = get_abi("MechMarketplace.json")
        return get_contract(
            self.mech_config.mech_marketplace_contract,
            abi,
            self.ledger_api,
        )

    def _fetch_mech_info(
        self, priority_mech: Optional[str]
    ) -> Tuple[PaymentType, int, int]:
        """
        Fetch mech information from contract.

        :param priority_mech: Priority mech address
        :return: Tuple of (payment_type, service_id, max_delivery_rate)
        """
        # Get mech contract
        mech_address = priority_mech or self.mech_config.priority_mech_address
        if not mech_address:
            raise ValueError("No mech address specified")

        abi = get_abi("IMech.json")
        mech_contract = get_contract(mech_address, abi, self.ledger_api)

        # Fetch mech info
        payment_type_bytes = mech_contract.functions.paymentType().call()
        max_delivery_rate = mech_contract.functions.maxDeliveryRate().call()
        service_id = mech_contract.functions.serviceId().call()

        # Convert payment type bytes to PaymentType enum
        payment_type = PaymentType.from_value(payment_type_bytes.hex())

        return payment_type, service_id, max_delivery_rate

    def _send_marketplace_request(
        self,
        marketplace_contract: Web3Contract,
        data_hashes: List[str],
        payment_type: PaymentType,
        use_prepaid: bool,
    ) -> str:
        """
        Send marketplace request transaction.

        :param marketplace_contract: Marketplace contract instance
        :param data_hashes: List of IPFS data hashes
        :param payment_type: Payment type
        :param use_prepaid: Whether to use prepaid balance
        :return: Transaction hash
        """
        # Build transaction arguments
        method_name = "requestBatch" if len(data_hashes) > 1 else "request"

        sender = self.executor.get_sender_address()
        value = (
            0
            if payment_type.is_token() or use_prepaid
            else self.mech_config.price * len(data_hashes)
        )

        method_args = {
            "data": data_hashes if len(data_hashes) > 1 else data_hashes[0],
        }

        tx_args = {
            "sender_address": sender,
            "value": value,
            "gas": self.mech_config.gas_limit,
        }

        # Execute transaction
        return self.executor.execute_transaction(
            contract=marketplace_contract,
            method_name=method_name,
            method_args=method_args,
            tx_args=tx_args,
        )
