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

import asyncio
import json
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, cast

import websocket
from aea.crypto.base import Crypto
from aea_ledger_ethereum import EthereumApi
from web3.contract import Contract as Web3Contract


def register_event_handlers(
    wss: websocket.WebSocket,
    contract_address: str,
    crypto: Crypto,
    request_signature: str,
    deliver_signature: str,
) -> None:
    """
    Register event handlers.

    :param wss: The WebSocket connection object.
    :type wss: websocket.WebSocket
    :param contract_address: The address of the contract.
    :type contract_address: str
    :param crypto: The cryptographic object.
    :type crypto: Crypto
    :param request_signature: Topic signature for Request event
    :type request_signature: str
    :param deliver_signature: Topic signature for Deliver event
    :type deliver_signature: str
    """

    subscription_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_subscribe",
        "params": [
            "logs",
            {
                "address": contract_address,
                "topics": [
                    request_signature,
                    ["0x" + "0" * 24 + crypto.address[2:]],
                ],
            },
        ],
    }
    content = bytes(json.dumps(subscription_request), "utf-8")
    wss.send(content)

    # registration confirmation
    _ = wss.recv()
    subscription_deliver = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_subscribe",
        "params": [
            "logs",
            {"address": contract_address, "topics": [deliver_signature]},
        ],
    }
    content = bytes(json.dumps(subscription_deliver), "utf-8")
    wss.send(content)

    # registration confirmation
    _ = wss.recv()


def wait_for_receipt(tx_hash: str, ledger_api: EthereumApi) -> Dict:
    """
    Wait for receipt.

    :param tx_hash: The transaction hash.
    :type tx_hash: str
    :param ledger_api: The Ethereum API used for interacting with the ledger.
    :type ledger_api: EthereumApi
    :return: The receipt of the transaction.
    :rtype: Dict
    """
    while True:
        try:
            return ledger_api._api.eth.get_transaction_receipt(  # pylint: disable=protected-access
                tx_hash
            )
        except Exception:  # pylint: disable=broad-except
            time.sleep(1)


def watch_for_request_id(  # pylint: disable=too-many-arguments
    wss: websocket.WebSocket,
    mech_contract: Web3Contract,
    ledger_api: EthereumApi,
    request_signature: str,
) -> str:
    """
    Watches for events on mech.

    :param wss: The WebSocket connection object.
    :type wss: websocket.WebSocket
    :param mech_contract: The mech contract instance.
    :type mech_contract: Web3Contract
    :param ledger_api: The Ethereum API used for interacting with the ledger.
    :type ledger_api: EthereumApi
    :return: The requested ID.
    :param request_signature: Topic signature for Request event
    :type request_signature: str
    :rtype: str
    """
    while True:
        msg = wss.recv()
        data = json.loads(msg)
        tx_hash = data["params"]["result"]["transactionHash"]
        tx_receipt = wait_for_receipt(tx_hash=tx_hash, ledger_api=ledger_api)
        event_signature = tx_receipt["logs"][0]["topics"][0].hex()
        if event_signature != request_signature:
            continue

        rich_logs = mech_contract.events.Request().process_receipt(tx_receipt)
        request_id = str(rich_logs[0]["args"]["requestId"])
        return request_id


def watch_for_marketplace_request_ids(  # pylint: disable=too-many-arguments, unused-argument
    marketplace_contract: Web3Contract,
    ledger_api: EthereumApi,
    tx_hash: str,
) -> List[str]:
    """
    Watches for events on mech.

    :param marketplace_contract: The marketplace contract instance.
    :type marketplace_contract: Web3Contract
    :param ledger_api: The Ethereum API used for interacting with the ledger.
    :type ledger_api: EthereumApi
    :param tx_hash: Tx hash to wait for
    :type tx_hash: str
    :return: The requested ID.
    :rtype: str
    """
    while True:
        tx_receipt = wait_for_receipt(tx_hash=tx_hash, ledger_api=ledger_api)

        rich_logs = marketplace_contract.events.MarketplaceRequest().process_receipt(
            tx_receipt
        )
        if len(rich_logs) == 0:
            return ["Empty Logs"]

        request_ids = rich_logs[0]["args"]["requestIds"]
        request_ids_hex = [request_id.hex() for request_id in request_ids]
        return request_ids_hex


async def watch_for_data_url_from_wss(  # pylint: disable=too-many-arguments
    request_id: str,
    wss: websocket.WebSocket,
    mech_contract: Web3Contract,
    deliver_signature: str,
    ledger_api: EthereumApi,
    loop: asyncio.AbstractEventLoop,
) -> Any:
    """
    Watches for data on-chain.

    :param request_id: The ID of the request.
    :type request_id: str
    :param wss: The WebSocket connection object.
    :type wss: websocket.WebSocket
    :param mech_contract: The mech contract instance.
    :type mech_contract: Web3Contract
    :param deliver_signature: Topic signature for Deliver event
    :type deliver_signature: str
    :param ledger_api: The Ethereum API used for interacting with the ledger.
    :type ledger_api: EthereumApi
    :param loop: The event loop used for asynchronous operations.
    :type loop: asyncio.AbstractEventLoop
    :return: The data received from on-chain.
    :rtype: Any
    """
    with ThreadPoolExecutor() as executor:
        try:
            while True:
                msg = await loop.run_in_executor(executor=executor, func=wss.recv)
                data = json.loads(msg)
                tx_hash = data["params"]["result"]["transactionHash"]
                tx_receipt = await loop.run_in_executor(
                    executor, wait_for_receipt, tx_hash, ledger_api
                )
                event_signature = tx_receipt["logs"][0]["topics"][0].hex()
                if event_signature != deliver_signature:
                    continue

                rich_logs = mech_contract.events.Deliver().process_receipt(tx_receipt)
                data = cast(bytes, rich_logs[0]["args"]["data"])
                if request_id != str(rich_logs[0]["args"]["requestId"]):
                    continue
                return f"https://gateway.autonolas.tech/ipfs/f01701220{data.hex()}"
        except websocket.WebSocketConnectionClosedException as e:
            print(f"WebSocketConnectionClosedException {repr(e)}")
            print(
                "Error: The WSS connection was likely closed by the remote party. Please, try using another WSS provider."
            )
            return None


async def watch_for_marketplace_data_url_from_wss(  # pylint: disable=too-many-arguments, unused-argument
    request_id: str,
    wss: websocket.WebSocket,
    mech_contract: Web3Contract,
    deliver_signature: str,
    ledger_api: EthereumApi,
    loop: asyncio.AbstractEventLoop,
) -> Any:
    """
    Watches for data on-chain.

    :param request_id: The ID of the request.
    :type request_id: str
    :param wss: The WebSocket connection object.
    :type wss: websocket.WebSocket
    :param mech_contract: The mech contract instance.
    :type mech_contract: Web3Contract
    :param deliver_signature: Topic signature for Deliver event
    :type deliver_signature: str
    :param ledger_api: The Ethereum API used for interacting with the ledger.
    :type ledger_api: EthereumApi
    :param loop: The event loop used for asynchronous operations.
    :type loop: asyncio.AbstractEventLoop
    :return: The data received from on-chain.
    :rtype: Any
    """
    with ThreadPoolExecutor() as executor:
        try:
            while True:
                msg = await loop.run_in_executor(executor=executor, func=wss.recv)
                data = json.loads(msg)
                tx_hash = data["params"]["result"]["transactionHash"]
                tx_receipt = await loop.run_in_executor(
                    executor, wait_for_receipt, tx_hash, ledger_api
                )

                rich_logs = mech_contract.events.Deliver().process_receipt(tx_receipt)
                if len(rich_logs) == 0:
                    print("Empty logs")
                    return None

                data = rich_logs[0]["args"]
                tx_request_id = data["requestId"]
                deliver_data = data["data"]

                if request_id != tx_request_id.hex():
                    continue

                return (
                    f"https://gateway.autonolas.tech/ipfs/f01701220{deliver_data.hex()}"
                )
        except websocket.WebSocketConnectionClosedException as e:
            print(f"WebSocketConnectionClosedException {repr(e)}")
            print(
                "Error: The WSS connection was likely closed by the remote party. Please, try using another WSS provider."
            )
            return None
