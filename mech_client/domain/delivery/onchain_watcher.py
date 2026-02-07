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

"""On-chain delivery watcher for marketplace mechs."""

import asyncio
import time
from typing import Any, Dict, List, Optional

from aea_ledger_ethereum import EthereumApi
from eth_abi import decode
from eth_utils import keccak
from web3.constants import ADDRESS_ZERO
from web3.contract import Contract as Web3Contract

from mech_client.domain.delivery.base import DeliveryWatcher
from mech_client.domain.delivery.constants import DEFAULT_TIMEOUT, WAIT_SLEEP
from mech_client.infrastructure.blockchain.abi_loader import get_abi
from mech_client.infrastructure.config import IPFS_URL_TEMPLATE


DELIVERY_MECH_INDEX = 1


class OnchainDeliveryWatcher(DeliveryWatcher):
    """Watcher for on-chain mech response delivery.

    Polls the marketplace contract for delivery events and extracts
    response data from on-chain logs.
    """

    def __init__(
        self,
        marketplace_contract: Web3Contract,
        ledger_api: EthereumApi,
        timeout: Optional[float] = None,
    ):
        """
        Initialize on-chain delivery watcher.

        :param marketplace_contract: Marketplace contract instance
        :param ledger_api: Ethereum API for blockchain interactions
        :param timeout: Maximum time to wait for delivery (default: 15 minutes)
        """
        super().__init__(timeout or DEFAULT_TIMEOUT)
        self.marketplace_contract = marketplace_contract
        self.ledger_api = ledger_api

    async def watch(self, request_ids: List[str]) -> Dict[str, Any]:
        """
        Watch for marketplace delivery and extract IPFS URLs.

        First polls marketplace to see which mechs delivered, then polls
        each mech's contract to extract the actual IPFS URLs with response data.

        :param request_ids: List of request IDs to watch for
        :return: Dictionary mapping request ID to IPFS URL with response data
        """
        # Step 1: Wait for marketplace delivery (get mech addresses)
        request_id_to_mech = await self._wait_for_marketplace_delivery(request_ids)

        if not request_id_to_mech:
            return {}

        # Step 2: Get IPFS URLs from mech contracts
        return await self._fetch_data_urls_from_mechs(request_ids, request_id_to_mech)

    async def _wait_for_marketplace_delivery(
        self, request_ids: List[str]
    ) -> Dict[str, str]:
        """
        Wait for marketplace to register delivery from mechs.

        :param request_ids: List of request IDs to watch for
        :return: Dictionary mapping request ID to delivery mech address
        """
        request_ids_data: Dict[str, str] = {}
        start_time = time.time()

        while True:
            for request_id in request_ids:
                request_id_info = self.marketplace_contract.functions.mapRequestIdInfos(
                    bytes.fromhex(request_id)
                ).call()

                # Return empty data if structure is unexpected
                if len(request_id_info) <= DELIVERY_MECH_INDEX:
                    return request_ids_data

                delivery_mech = request_id_info[DELIVERY_MECH_INDEX]
                if not isinstance(delivery_mech, str) or not delivery_mech.startswith(
                    "0x"
                ):
                    return {}

                if delivery_mech != ADDRESS_ZERO:
                    request_ids_data[request_id] = delivery_mech

            # All requests delivered
            if len(request_ids_data) == len(request_ids):
                return request_ids_data

            # Sleep once per polling cycle, not per request ID
            await asyncio.sleep(WAIT_SLEEP)

            # Check timeout once per polling cycle
            elapsed_time = time.time() - start_time
            if elapsed_time >= self.timeout:
                print(
                    "Timeout reached while waiting for marketplace delivery. "
                    "Returning partial data."
                )
                return request_ids_data

    async def _fetch_data_urls_from_mechs(
        self, request_ids: List[str], request_id_to_mech: Dict[str, str]
    ) -> Dict[str, str]:
        """
        Fetch IPFS URLs from mech contracts.

        Groups requests by mech and fetches Deliver events from each mech
        to extract IPFS URLs with response data.

        :param request_ids: List of request IDs
        :param request_id_to_mech: Mapping of request ID to mech address
        :return: Dictionary mapping request ID to IPFS URL
        """
        # Group request IDs by mech
        mech_to_request_ids: Dict[str, List[str]] = {}
        for request_id in request_ids:
            mech = request_id_to_mech.get(request_id)
            if mech:
                mech_to_request_ids.setdefault(mech, []).append(request_id)

        # Get Deliver event signature from IMech ABI
        mech_deliver_signature = self._get_deliver_event_signature()

        # Get current block
        current_block = self.ledger_api.api.eth.block_number

        # Fetch data URLs from each mech
        all_results: Dict[str, str] = {}
        for mech_address, mech_request_ids in mech_to_request_ids.items():
            results = await self.watch_for_data_urls(
                request_ids=mech_request_ids,
                from_block=current_block - 100,  # Look back 100 blocks
                mech_contract_address=mech_address,
                mech_deliver_signature=mech_deliver_signature,
            )
            all_results.update(results)

        return all_results

    def _get_deliver_event_signature(self) -> str:  # pylint: disable=no-self-use
        """
        Calculate Deliver event signature from IMech ABI.

        :return: Event signature hash (without 0x prefix)
        """
        abi = get_abi("IMech.json")
        for item in abi:
            if item.get("type") == "event" and item.get("name") == "Deliver":
                # Build event signature: Deliver(uint256,bytes32,bytes)
                param_types = [param["type"] for param in item.get("inputs", [])]
                event_signature = f"Deliver({','.join(param_types)})"
                # Calculate keccak256 hash
                return keccak(text=event_signature).hex()

        raise ValueError("Deliver event not found in IMech ABI")

    async def watch_for_data_urls(  # pylint: disable=too-many-locals
        self,
        request_ids: List[str],
        from_block: int,
        mech_contract_address: str,
        mech_deliver_signature: str,
    ) -> Dict[str, str]:
        """
        Watch for delivery events and extract IPFS URLs.

        Polls blockchain logs for Deliver events and extracts IPFS hash
        from event data.

        :param request_ids: List of request IDs to watch for
        :param from_block: Block number to start searching from
        :param mech_contract_address: Mech contract address
        :param mech_deliver_signature: Topic signature for Deliver event
        :return: Dictionary mapping request ID to IPFS URL
        """
        results = {}
        start_time = time.time()

        def get_logs(from_block_: int) -> List:
            logs = self.ledger_api.api.eth.get_logs(
                {
                    "fromBlock": from_block_,
                    "toBlock": "latest",
                    "address": mech_contract_address,
                    "topics": ["0x" + mech_deliver_signature],
                }
            )
            return logs

        def get_event_data(log: Dict) -> tuple:
            data_types = ["bytes32", "uint256", "bytes"]
            data_bytes = bytes(log["data"])
            request_id_bytes, _, delivery_data_bytes = decode(data_types, data_bytes)
            return request_id_bytes, delivery_data_bytes

        while True:
            logs = get_logs(from_block)
            latest_block = from_block
            for log in logs:
                latest_block = max(latest_block, log["blockNumber"])
                event_data = get_event_data(log)
                request_id, delivery_data = (data.hex() for data in event_data)

                if request_id in results:
                    continue

                if request_id in request_ids:
                    results[request_id] = IPFS_URL_TEMPLATE.format(delivery_data)

                if len(results) == len(request_ids):
                    return results

            from_block = latest_block + 1
            await asyncio.sleep(WAIT_SLEEP)
            elapsed_time = time.time() - start_time
            if elapsed_time >= self.timeout:
                print("Timeout reached. Returning partial results.")
                return results
