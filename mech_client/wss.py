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
from typing import Any, Dict, cast

import websocket
from aea.crypto.base import Crypto
from aea_ledger_ethereum import EthereumApi
from web3.contract import Contract as Web3Contract

EVENT_SIGNATURE_REQUEST = (
    "0x4bda649efe6b98b0f9c1d5e859c29e20910f45c66dabfe6fad4a4881f7faf9cc"
)
EVENT_SIGNATURE_DELIVER = (
    "0x3ec84da2cdc1ce60c063642b69ff2e65f3b69787a2b90443457ba274e51e7c72"
)


def register_event_handlers(
    wss: websocket.WebSocket, contract_address: str, crypto: Crypto
) -> None:
    """Register event handlers."""

    subscription_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_subscribe",
        "params": [
            "logs",
            {
                "address": contract_address,
                "topics": [
                    EVENT_SIGNATURE_REQUEST,
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
            {"address": contract_address, "topics": [EVENT_SIGNATURE_DELIVER]},
        ],
    }
    content = bytes(json.dumps(subscription_deliver), "utf-8")
    wss.send(content)

    # registration confirmation
    _ = wss.recv()


def wait_for_receipt(tx_hash: str, ledger_api: EthereumApi) -> Dict:
    """Wait for receipt."""
    while True:
        try:
            return ledger_api._api.eth.get_transaction_receipt(tx_hash)
        except Exception:
            time.sleep(1)


def watch_for_request_id(
    wss: websocket.WebSocket,
    mech_contract: Web3Contract,
    ledger_api: EthereumApi,
) -> str:
    """Watches for events on mech."""
    while True:
        msg = wss.recv()
        data = json.loads(msg)
        tx_hash = data["params"]["result"]["transactionHash"]
        tx_receipt = wait_for_receipt(tx_hash=tx_hash, ledger_api=ledger_api)
        event_signature = tx_receipt["logs"][0]["topics"][0].hex()
        if event_signature != EVENT_SIGNATURE_REQUEST:
            continue

        rich_logs = mech_contract.events.Request().processReceipt(tx_receipt)
        request_id = str(rich_logs[0]["args"]["requestId"])
        return request_id


async def watch_for_data_url_from_wss(
    request_id: str,
    wss: websocket.WebSocket,
    mech_contract: Web3Contract,
    ledger_api: EthereumApi,
    loop: asyncio.AbstractEventLoop,
) -> Any:
    """Watches for data on-chain."""

    with ThreadPoolExecutor() as executor:
        while True:
            msg = await loop.run_in_executor(executor=executor, func=wss.recv)
            data = json.loads(msg)
            tx_hash = data["params"]["result"]["transactionHash"]
            tx_receipt = await loop.run_in_executor(
                executor, wait_for_receipt, tx_hash, ledger_api
            )
            event_signature = tx_receipt["logs"][0]["topics"][0].hex()
            if event_signature != EVENT_SIGNATURE_DELIVER:
                continue

            rich_logs = mech_contract.events.Deliver().processReceipt(tx_receipt)
            data = cast(bytes, rich_logs[0]["args"]["data"])
            if request_id != str(rich_logs[0]["args"]["requestId"]):
                continue
            return f"https://gateway.autonolas.tech/ipfs/f01701220{data.hex()}"


def watch_for_data_url_from_wss_sync(
    request_id: str,
    wss: websocket.WebSocket,
    mech_contract: Web3Contract,
    ledger_api: EthereumApi,
) -> Any:
    """Watches for data on-chain."""
    loop = asyncio.new_event_loop()
    task = loop.create_task(
        watch_for_data_url_from_wss(
            request_id=request_id,
            wss=wss,
            mech_contract=mech_contract,
            ledger_api=ledger_api,
            loop=loop,
        )
    )
    loop.run_until_complete(task)
    return task.result()
