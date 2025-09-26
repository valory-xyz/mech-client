# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2023 Valory AG
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

"""Websocket helpers."""

import time
from typing import Any, List

from aea_ledger_ethereum import EthereumApi
from eth_abi import decode
from web3.constants import ADDRESS_ZERO
from web3.contract import Contract as Web3Contract


WAIT_SLEEP = 3.0
DELIVERY_MECH_INDEX = 1
IPFS_URL_TEMPLATE = "https://gateway.autonolas.tech/ipfs/f01701220{}"


async def watch_for_marketplace_data(  # pylint: disable=too-many-arguments, unused-argument, too-many-locals
    request_ids: List[str],
    marketplace_contract: Web3Contract,
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
    try:
        request_ids_data = {}
        while True:
            for request_id in request_ids:
                request_id_info = marketplace_contract.functions.mapRequestIdInfos(
                    bytes.fromhex(request_id)
                ).call()
                delivery_mech = request_id_info[DELIVERY_MECH_INDEX]
                if delivery_mech != ADDRESS_ZERO:
                    request_ids_data.update({request_id: delivery_mech})

                time.sleep(WAIT_SLEEP)

            if len(request_ids_data) == len(request_ids):
                return request_ids_data

    except Exception as e:
        print(f"Exception {repr(e)}")
        return None


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
    :param mech_contract_address: The mech contract instance.
    :type mech_contract_address: str
    :param mech_deliver_signature: Topic signature for Deliver event
    :type mech_deliver_signature: str
    :param loop: The event loop used for asynchronous operations.
    :type loop: asyncio.AbstractEventLoop
    :return: The data received from on-chain.
    :rtype: Any
    """

    results = {}

    def get_logs():
        logs = ledger_api.api.eth.get_logs(
            {
                "fromBlock": from_block,
                "toBlock": "latest",
                "address": mech_contract_address,
                "topics": ["0x" + mech_deliver_signature],
            }
        )
        return logs

    def get_event_data(log):
        data_types = ["bytes32", "uint256", "bytes"]
        data_bytes = bytes(log["data"])
        request_id_bytes, _, delivery_data_bytes = decode(data_types, data_bytes)
        return request_id_bytes, delivery_data_bytes

    try:
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

    except Exception as e:
        print(f"Exception {repr(e)}")
        return None
