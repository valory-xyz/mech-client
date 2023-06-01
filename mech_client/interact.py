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

"""
This script allows sending a Request to an on-chain mech and waiting for the Deliver.

Usage:

python client.py <prompt> <tool>
"""

import json
import os
import time
import warnings
from typing import Any, Dict, Optional

import requests
import websocket
from aea.contracts.base import Contract
from aea_ledger_ethereum import EthereumApi, EthereumCrypto

from mech_client.prompt_to_ipfs import push_metadata_to_ipfs

CONTRACT_ADDRESS = "0xFf82123dFB52ab75C417195c5fDB87630145ae81"
ETHEREUM_TESTNET_CONFIG = {
    "address": "https://rpc.eu-central-2.gateway.fm/v4/gnosis/non-archival/mainnet",
    "chain_id": 100,
    "poa_chain": False,
    "default_gas_price_strategy": "eip1559",
}
PRIVATE_KEY_FILE_PATH = "ethereum_private_key.txt"
EVENT_SIGNATURE_REQUEST = (
    "0x4bda649efe6b98b0f9c1d5e859c29e20910f45c66dabfe6fad4a4881f7faf9cc"
)
EVENT_SIGNATURE_DELIVER = (
    "0x3ec84da2cdc1ce60c063642b69ff2e65f3b69787a2b90443457ba274e51e7c72"
)
WSS_ENDPOINT = os.getenv(
    "WEBSOCKET_ENDPOINT",
    "wss://rpc.eu-central-2.gateway.fm/ws/v4/gnosis/non-archival/mainnet",
)

# Ignore a specific warning message
warnings.filterwarnings("ignore", "The log with transaction hash.*")


def check_for_tools(tool: str) -> Optional[int]:
    """Checks if the tool is valid and for what agent."""
    # TODO - replace hardcoded logic with on-chain check against agent mech registry
    return (
        3
        if tool
        in [
            "openai-text-davinci-002",
            "openai-text-davinci-003",
            "openai-gpt-3.5-turbo",
            "openai-gpt-4",
            "stabilityai-stable-diffusion-v1-5",
            "stabilityai-stable-diffusion-xl-beta-v2-2-2",
            "stabilityai-stable-diffusion-512-v2-1",
            "stabilityai-stable-diffusion-768-v2-1",
        ]
        else None
    )


def register_event_handlers(ethereum_crypto: EthereumCrypto) -> websocket.WebSocket:
    """Register event handlers."""
    wss = websocket.create_connection(WSS_ENDPOINT)
    subscription_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_subscribe",
        "params": [
            "logs",
            {
                "address": CONTRACT_ADDRESS,
                "topics": [
                    EVENT_SIGNATURE_REQUEST,
                    ["0x" + "0" * 24 + ethereum_crypto.address[2:]],
                ],
            },
        ],
    }
    content = bytes(json.dumps(subscription_request), "utf-8")
    wss.send(content)
    # registration confirmation
    msg = wss.recv()
    subscription_deliver = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_subscribe",
        "params": [
            "logs",
            {"address": CONTRACT_ADDRESS, "topics": [EVENT_SIGNATURE_DELIVER]},
        ],
    }
    content = bytes(json.dumps(subscription_deliver), "utf-8")
    wss.send(content)
    # registration confirmation
    msg = wss.recv()
    return wss


def send_request(
    ethereum_crypto: EthereumCrypto,
    ethereum_ledger_api: EthereumApi,
    prompt: str,
    tool: str,
    contract_address: str = CONTRACT_ADDRESS,
    price: int = 10_000_000_000_000_000,
) -> Contract:
    """Sends a request to the mech."""
    mech = check_for_tools(tool)
    if mech is None:
        raise ValueError(f"Tool {tool} is not supported by any mech.")
    v1_file_hash_hex_truncated, v1_file_hash_hex = push_metadata_to_ipfs(prompt, tool)
    print(f"Prompt uploaded: https://gateway.autonolas.tech/ipfs/{v1_file_hash_hex}")

    gnosisscan_api_url = f"https://api.gnosisscan.io/api?module=contract&action=getabi&address={contract_address}"
    response = requests.get(gnosisscan_api_url)
    abi = response.json()["result"]
    abi = json.loads(abi)

    contract_instance = ethereum_ledger_api.get_contract_instance(
        {"abi": abi, "bytecode": "0x"}, contract_address
    )
    method_name = "request"
    methord_args = {
        "data": v1_file_hash_hex_truncated
    }  # bytes.fromhex(v1_file_hash_hex_truncated[2:])}
    tx_args = {"sender_address": ethereum_crypto.address, "value": price}

    raw_transaction = ethereum_ledger_api.build_transaction(
        contract_instance=contract_instance,
        method_name=method_name,
        method_args=methord_args,
        tx_args=tx_args,
    )
    raw_transaction["gas"] = 50_000
    # raw_transaction = ethereum_ledger_api.update_with_gas_estimate(raw_transaction)
    signed_transaction = ethereum_crypto.sign_transaction(raw_transaction)
    transaction_digest = ethereum_ledger_api.send_signed_transaction(signed_transaction)
    print(f"Transaction sent: https://gnosisscan.io/tx/{transaction_digest}")
    return contract_instance


def watch_for_events(
    wss: websocket.WebSocket,
    contract_instance: Contract,
    ethereum_ledger_api: EthereumApi,
    ethereum_crypto: EthereumCrypto,
) -> Dict[str, Any]:
    """Watches for events on mech."""
    is_waiting = True
    request_id = None
    while is_waiting:
        msg = wss.recv()
        data = json.loads(msg)
        tx_hash = data["params"]["result"]["transactionHash"]
        no_receipt = True
        while no_receipt:
            try:
                tx_receipt = ethereum_ledger_api._api.eth.get_transaction_receipt(
                    tx_hash
                )
                no_receipt = False
            except Exception:
                time.sleep(1)
        event_signature = tx_receipt["logs"][0]["topics"][0].hex()
        if event_signature == EVENT_SIGNATURE_REQUEST:
            rich_logs = contract_instance.events.Request().processReceipt(tx_receipt)
            request_id = rich_logs[0]["args"]["requestId"]
            print(f"Request on-chain with id: {request_id}")
        if event_signature == EVENT_SIGNATURE_DELIVER:
            rich_logs = contract_instance.events.Deliver().processReceipt(tx_receipt)
            data = rich_logs[0]["args"]["data"]
            request_id_ = rich_logs[0]["args"]["requestId"]
            if request_id != request_id_:
                continue
            data_url = "https://gateway.autonolas.tech/ipfs/f01701220" + data.hex()
            print(f"Data arrived: {data_url}")
            is_waiting = False
    response = requests.get(data_url + "/" + str(request_id))
    response_json = response.json()
    result = response_json["result"]
    print(f"Data:\n{result}")
    return response_json


def interact(prompt: str, tool: str) -> Dict[str, Any]:
    ethereum_crypto = EthereumCrypto(private_key_path=PRIVATE_KEY_FILE_PATH)
    ethereum_ledger_api = EthereumApi(**ETHEREUM_TESTNET_CONFIG)
    wss = register_event_handlers(ethereum_crypto)
    contract_instance = send_request(ethereum_crypto, ethereum_ledger_api, prompt, tool)
    response = watch_for_events(
        wss, contract_instance, ethereum_ledger_api, ethereum_crypto
    )
    return response
