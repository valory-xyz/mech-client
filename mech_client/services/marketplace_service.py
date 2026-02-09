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

from typing import Any, Dict, List, Optional, Tuple, cast

import requests
from aea_ledger_ethereum import EthereumCrypto
from eth_utils import to_checksum_address
from safe_eth.eth import EthereumClient
from web3.contract import Contract as Web3Contract

from mech_client.domain.delivery import OffchainDeliveryWatcher, OnchainDeliveryWatcher
from mech_client.domain.payment import PaymentStrategyFactory
from mech_client.domain.tools import ToolManager
from mech_client.infrastructure.blockchain.abi_loader import get_abi
from mech_client.infrastructure.blockchain.contracts import get_contract
from mech_client.infrastructure.blockchain.receipt_waiter import (
    wait_for_receipt,
    watch_for_marketplace_request_ids,
)
from mech_client.infrastructure.config import PaymentType
from mech_client.infrastructure.ipfs import IPFSClient, push_metadata_to_ipfs
from mech_client.services.base_service import BaseTransactionService


class MarketplaceService(
    BaseTransactionService
):  # pylint: disable=too-many-instance-attributes,too-few-public-methods
    """Service for orchestrating mech marketplace requests.

    Composes payment strategies, execution strategies, tool management,
    and delivery watching to provide high-level marketplace operations.
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        chain_config: str,
        agent_mode: bool,
        crypto: EthereumCrypto,
        safe_address: Optional[str] = None,
        ethereum_client: Optional[EthereumClient] = None,
    ):
        """
        Initialize marketplace service.

        :param chain_config: Chain configuration name (gnosis, base, etc.)
        :param agent_mode: True for agent mode (Safe), False for client mode (EOA)
        :param crypto: Ethereum crypto object for signing
        :param safe_address: Safe address (required for agent mode)
        :param ethereum_client: Ethereum client (required for agent mode)
        """
        super().__init__(
            chain_config=chain_config,
            agent_mode=agent_mode,
            crypto=crypto,
            safe_address=safe_address,
            ethereum_client=ethereum_client,
        )

        # Create tool manager
        self.tool_manager = ToolManager(chain_config)

        # Create IPFS client
        self.ipfs_client = IPFSClient()

    async def send_request(  # pylint: disable=too-many-arguments,too-many-locals
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

        if use_offchain and not mech_offchain_url:
            raise ValueError("mech_offchain_url required when use_offchain=True")

        # Get marketplace contract
        marketplace_contract = self._get_marketplace_contract()

        # Fetch mech info (payment type, service ID, max delivery rate)
        payment_type, service_id, max_delivery_rate = self._fetch_mech_info(
            priority_mech
        )

        # Validate tools exist for this service
        self._validate_tools(tools, service_id)

        # Get priority mech address (use configured or provided)
        priority_mech_address = priority_mech or self.mech_config.priority_mech_address
        if not priority_mech_address:
            raise ValueError("No priority mech address specified")

        # Response timeout (5 minutes, matching historic default)
        response_timeout = 300

        # Branch between on-chain and off-chain flows
        if use_offchain:
            # mech_offchain_url and timeout are validated above
            return await self._send_offchain_request(
                marketplace_contract=marketplace_contract,
                prompts=prompts,
                tools=tools,
                priority_mech_address=priority_mech_address,
                max_delivery_rate=max_delivery_rate,
                payment_type=payment_type,
                response_timeout=response_timeout,
                mech_offchain_url=cast(str, mech_offchain_url),
                extra_attributes=extra_attributes,
                timeout=timeout or 300.0,
            )

        # On-chain flow
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
                    f"Insufficient balance for token payment. Required: {price} wei. "
                    f"Please check your token balance for address: {sender}"
                )

            # Approve if needed
            payment_strategy.approve_if_needed(
                payer_address=sender,
                spender_address=balance_tracker,
                amount=price,
                executor=self.executor,
            )

        # Send on-chain marketplace request
        tx_hash = self._send_marketplace_request(
            marketplace_contract=marketplace_contract,
            data_hashes=data_hashes,
            max_delivery_rate=max_delivery_rate,
            payment_type=payment_type,
            priority_mech=priority_mech_address,
            response_timeout=response_timeout,
            use_prepaid=use_prepaid,
        )

        # Wait for receipt and get request IDs
        receipt = wait_for_receipt(tx_hash, self.ledger_api)
        request_ids = watch_for_marketplace_request_ids(
            marketplace_contract, self.ledger_api, tx_hash
        )

        # Watch for on-chain delivery
        watcher = OnchainDeliveryWatcher(marketplace_contract, self.ledger_api, timeout)
        results = await watcher.watch(request_ids)

        return {
            "tx_hash": tx_hash,
            "request_ids": request_ids,
            "delivery_results": results,
            "receipt": receipt,
        }

    async def _send_offchain_request(  # pylint: disable=too-many-arguments,too-many-locals,unused-argument
        self,
        marketplace_contract: Web3Contract,
        prompts: Tuple[str, ...],
        tools: Tuple[str, ...],
        priority_mech_address: str,
        max_delivery_rate: int,
        payment_type: PaymentType,
        response_timeout: int,
        mech_offchain_url: str,
        extra_attributes: Optional[Dict[str, Any]],
        timeout: float,
    ) -> Dict[str, Any]:
        """
        Send offchain request to mech HTTP endpoint.

        :param marketplace_contract: Marketplace contract instance
        :param prompts: Tuple of prompt strings
        :param tools: Tuple of tool identifiers
        :param priority_mech_address: Mech address
        :param max_delivery_rate: Max delivery rate from mech
        :param payment_type: Payment type
        :param response_timeout: Response timeout in seconds
        :param mech_offchain_url: Base URL of offchain mech
        :param extra_attributes: Extra attributes for metadata
        :param timeout: Delivery watching timeout
        :return: Dictionary with request results
        """
        print("Sending offchain mech marketplace request...")

        # Get current nonce from contract
        sender = self.crypto.address
        current_nonce = marketplace_contract.functions.mapNonces(sender).call()

        # Prepare and send each request
        request_ids_hex = []
        request_ids_int = []

        for i, (prompt, tool) in enumerate(zip(prompts, tools)):
            # Prepare metadata (get hash and data without uploading)
            # Import here to avoid circular dependency
            from mech_client.infrastructure.ipfs.metadata import (  # pylint: disable=import-outside-toplevel
                fetch_ipfs_hash,
            )

            data_hash, data_hash_full, ipfs_data = fetch_ipfs_hash(
                prompt, tool, extra_attributes or {}
            )
            print(
                f"  - Prompt will be uploaded to: https://gateway.autonolas.tech/ipfs/{data_hash_full}"
            )

            # Calculate request ID
            # payment_type.value is already a hex string, just add 0x prefix
            payment_type_hex = "0x" + payment_type.value
            nonce = current_nonce + i
            request_id_bytes = marketplace_contract.functions.getRequestId(
                to_checksum_address(priority_mech_address),
                sender,
                data_hash,
                max_delivery_rate,
                payment_type_hex,
                nonce,
            ).call()

            request_id_int = int.from_bytes(request_id_bytes, byteorder="big")
            request_id_hex = request_id_bytes.hex()

            # Sign the request ID
            signature = self.crypto.sign_message(
                request_id_bytes, is_deprecated_mode=True
            )

            # Prepare payload
            payload = {
                "sender": sender,
                "signature": signature,
                "ipfs_hash": data_hash,
                "request_id": request_id_int,
                "delivery_rate": max_delivery_rate,
                "nonce": nonce,
                "ipfs_data": ipfs_data,
            }

            # Send HTTP POST request
            url = f"{mech_offchain_url.rstrip('/')}/send_signed_requests"
            try:
                response = requests.post(
                    url=url,
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=30,
                )
                response.raise_for_status()
                # Response contains request confirmation but we don't need to use it
                _ = response.json()

                request_ids_hex.append(request_id_hex)
                request_ids_int.append(str(request_id_int))

                print(f"  - Created offchain request with ID {request_id_int}")

            except requests.exceptions.RequestException as e:
                raise ValueError(f"Failed to send offchain request: {e}") from e

        print("")

        # Watch for offchain delivery
        print("Waiting for offchain mech marketplace deliver...")
        watcher = OffchainDeliveryWatcher(mech_offchain_url, timeout)
        results = await watcher.watch(request_ids_hex)

        return {
            "tx_hash": None,  # No on-chain transaction for offchain requests
            "request_ids": request_ids_hex,
            "delivery_results": results,
            "receipt": None,  # No receipt for offchain requests
        }

    def _validate_tools(self, tools: Tuple[str, ...], service_id: int) -> None:
        """
        Validate that tools exist for the service.

        Fetches the available tools for the service from metadata and validates
        that all requested tools are available.

        :param tools: Tuple of tool identifiers
        :param service_id: Service ID of the mech
        :raises ValueError: If any tool is invalid or not available
        """
        # Basic validation - check for empty tools
        for tool in tools:
            if not tool:
                raise ValueError("Empty tool identifier")

        # Fetch available tools for this service
        try:
            tools_info = self.tool_manager.get_tools(service_id)
        except (AttributeError, KeyError, TypeError) as e:
            # If fetching fails due to unexpected metadata structure,
            # warn but allow request to proceed
            print(
                f"Warning: Failed to fetch tool metadata for service {service_id}: {e}. "
                f"Tool validation skipped."
            )
            return

        if not tools_info:
            # If we can't fetch tools, warn but don't fail
            # This allows requests to proceed even if metadata fetch fails
            print(
                f"Warning: Could not fetch tool metadata for service {service_id}. "
                f"Tool validation skipped."
            )
            return

        # Get list of available tool names
        available_tools = {tool.tool_name for tool in tools_info.tools}

        # Validate each requested tool
        for tool in tools:
            if tool not in available_tools:
                raise ValueError(
                    f"Tool {tool!r} not available for service {service_id}. "
                    f"Available tools: {', '.join(sorted(available_tools))}"
                )

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

    def _send_marketplace_request(  # pylint: disable=too-many-arguments,too-many-locals
        self,
        marketplace_contract: Web3Contract,
        data_hashes: List[str],
        max_delivery_rate: int,
        payment_type: PaymentType,
        priority_mech: str,
        response_timeout: int,
        use_prepaid: bool,
    ) -> str:
        """
        Send marketplace request transaction.

        :param marketplace_contract: Marketplace contract instance
        :param data_hashes: List of IPFS data hashes
        :param max_delivery_rate: Maximum delivery rate
        :param payment_type: Payment type
        :param priority_mech: Priority mech address
        :param response_timeout: Response timeout in seconds
        :param use_prepaid: Whether to use prepaid balance
        :return: Transaction hash
        """
        # Build transaction arguments
        method_name = "requestBatch" if len(data_hashes) > 1 else "request"

        sender = self.executor.get_sender_address()
        value = (
            0
            if payment_type.is_token() or use_prepaid
            else max_delivery_rate * len(data_hashes)
        )

        # Convert payment type to bytes32; allow optional 0x prefix for robustness
        payment_type_hex = payment_type.value.removeprefix("0x")
        try:
            payment_type_bytes = bytes.fromhex(payment_type_hex)
        except ValueError as e:
            raise ValueError(
                f"Invalid payment type value {payment_type.value!r}: {e}"
            ) from e

        # Payment data (empty bytes for now - can be extended for additional payment info)
        payment_data = b""

        # Ensure priority mech address is checksummed (required by web3.py)
        priority_mech_checksummed = to_checksum_address(priority_mech)

        # Build method arguments according to ABI
        if len(data_hashes) > 1:
            # requestBatch(bytes[] requestDatas, uint256 maxDeliveryRate, bytes32 paymentType,
            #              address priorityMech, uint256 responseTimeout, bytes paymentData)
            method_args = {
                "requestDatas": data_hashes,
                "maxDeliveryRate": max_delivery_rate,
                "paymentType": payment_type_bytes,
                "priorityMech": priority_mech_checksummed,
                "responseTimeout": response_timeout,
                "paymentData": payment_data,
            }
        else:
            # request(bytes requestData, uint256 maxDeliveryRate, bytes32 paymentType,
            #         address priorityMech, uint256 responseTimeout, bytes paymentData)
            method_args = {
                "requestData": data_hashes[0],
                "maxDeliveryRate": max_delivery_rate,
                "paymentType": payment_type_bytes,
                "priorityMech": priority_mech_checksummed,
                "responseTimeout": response_timeout,
                "paymentData": payment_data,
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
