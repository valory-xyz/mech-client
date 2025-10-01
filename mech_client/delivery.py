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

"""Onchain delivery helpers."""

import time
from typing import Any, Dict, List, Tuple, Optional

from aea_ledger_ethereum import EthereumApi
from eth_abi import decode
from web3.constants import ADDRESS_ZERO
from web3.contract import Contract as Web3Contract


WAIT_SLEEP = 3.0
DELIVERY_MECH_INDEX = 1
DEFAULT_TIMEOUT = 900.0  # 15mins
IPFS_URL_TEMPLATE = "https://gateway.autonolas.tech/ipfs/f01701220{}"


async def watch_for_marketplace_data(  # pylint: disable=too-many-arguments, unused-argument, too-many-locals
    request_ids: List[str],
    marketplace_contract: Web3Contract,
    timeout: Optional[float] = None,
) -> Any:
    """
    Watches for data on-chain.

    :param request_ids: The IDs of the request.
    :type request_ids: List[str]
    :param marketplace_contract: The marketplace contract instance.
    :type marketplace_contract: Web3Contract
    :return: The data received from on-chain.
    :rtype: Any
    """
    request_ids_data: Dict = {}
    start_time = time.time()
    # either use the timeout supplied by user or the default timeout of 15mins
    timeout = timeout or DEFAULT_TIMEOUT
    while True:
        for request_id in request_ids:
            request_id_info = marketplace_contract.functions.mapRequestIdInfos(
                bytes.fromhex(request_id)
            ).call()

            # return empty data which is handled in the main method
            if len(request_id_info) <= DELIVERY_MECH_INDEX:
                return request_ids_data

            delivery_mech = request_id_info[DELIVERY_MECH_INDEX]
            if not isinstance(delivery_mech, str) or not delivery_mech.startswith("0x"):
                return request_id_info

            if delivery_mech != ADDRESS_ZERO:
                request_ids_data.update({request_id: delivery_mech})

            time.sleep(WAIT_SLEEP)

            elapsed_time = time.time() - start_time
            if elapsed_time >= timeout:
                print("Timeout reached. Breaking the loop and returning empty data.")
                return request_ids_data

        if len(request_ids_data) == len(request_ids):
            return request_ids_data


async def watch_for_mech_data_url(  # pylint: disable=too-many-arguments, unused-argument, too-many-locals
    request_ids: List[str],
    from_block: int,
    mech_contract_address: str,
    mech_deliver_signature: str,
    ledger_api: EthereumApi,
) -> Any:
    """
    Watches for data on-chain.

    :param request_ids: The IDs of the request.
    :type request_ids: List[str]
    :param from_block: The from block to start searching logs.
    :type from_block: int
    :param mech_contract_address: The mech contract instance.
    :type mech_contract_address: str
    :param mech_deliver_signature: Topic signature for Deliver event
    :type mech_deliver_signature: str
    :param ledger_api: The Ethereum API used for interacting with the ledger.
    :type ledger_api: EthereumApi
    :return: The data received from on-chain.
    :rtype: Any
    """

    results = {}

    def get_logs() -> List:
        logs = ledger_api.api.eth.get_logs(
            {
                "fromBlock": from_block,
                "toBlock": "latest",
                "address": mech_contract_address,
                "topics": ["0x" + mech_deliver_signature],
            }
        )
        return logs

    def get_event_data(log: Dict) -> Tuple:
        data_types = ["bytes32", "uint256", "bytes"]
        data_bytes = bytes(log["data"])
        request_id_bytes, _, delivery_data_bytes = decode(data_types, data_bytes)
        return request_id_bytes, delivery_data_bytes

    while True:
        logs = get_logs()
        for log in logs:
            event_data = get_event_data(log)
            request_id, delivery_data = (data.hex() for data in event_data)
            if request_id in results:
                continue

            if request_id in request_ids:
                results[request_id] = IPFS_URL_TEMPLATE.format(delivery_data)

            if len(results) == len(request_ids):
                return results

        time.sleep(WAIT_SLEEP)
