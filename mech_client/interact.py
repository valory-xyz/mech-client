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

import asyncio
import json
import os
import warnings
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
import websocket
from aea.crypto.base import Crypto
from aea_ledger_ethereum import EthereumApi, EthereumCrypto
from web3.contract import Contract as Web3Contract

from mech_client.acn import (
    watch_for_data_url_from_mech,
    watch_for_data_url_from_mech_sync,
)
from mech_client.prompt_to_ipfs import push_metadata_to_ipfs
from mech_client.subgraph import query_agent_address
from mech_client.wss import (
    register_event_handlers,
    watch_for_data_url_from_wss,
    watch_for_data_url_from_wss_sync,
    watch_for_request_id,
)

AGENT_REGISTRY_CONTRACT = "0xE49CB081e8d96920C38aA7AB90cb0294ab4Bc8EA"
MECHX_CHAIN_RPC = os.environ.get(
    "MECHX_CHAIN_RPC",
    "https://rpc.eu-central-2.gateway.fm/v4/gnosis/non-archival/mainnet",
)
LEDGER_CONFIG = {
    "address": MECHX_CHAIN_RPC,
    "chain_id": 100,
    "poa_chain": False,
    "default_gas_price_strategy": "eip1559",
}
PRIVATE_KEY_FILE_PATH = "ethereum_private_key.txt"

WSS_ENDPOINT = os.getenv(
    "WEBSOCKET_ENDPOINT",
    "wss://rpc.eu-central-2.gateway.fm/ws/v4/gnosis/non-archival/mainnet",
)
GNOSISSCAN_API_URL = "https://api.gnosisscan.io/api?module=contract&action=getabi&address={contract_address}"

# Ignore a specific warning message
warnings.filterwarnings("ignore", "The log with transaction hash.*")


class ConfirmationType(Enum):
    """Verification type."""

    ON_CHAIN = "on-chain"
    OFF_CHAIN = "off-chain"
    WAIT_FOR_BOTH = "wait-for-both"


def get_contract(contract_address: str, ledger_api: EthereumApi) -> Web3Contract:
    """Returns a contract instance."""
    abi_request_url = GNOSISSCAN_API_URL.format(contract_address=contract_address)
    response = requests.get(abi_request_url).json()
    abi = json.loads(response["result"])
    return ledger_api.get_contract_instance(
        {"abi": abi, "bytecode": "0x"}, contract_address
    )


def _tool_selector_prompt(available_tools: List[str]) -> str:
    """Tool selector prompt."""

    tool_col_len = max(map(len, available_tools))
    id_col_len = max(2, len(str(len(available_tools))))
    table_len = tool_col_len + id_col_len + 5

    separator = "|" + "-" * table_len + "|"
    print("Select prompting tool")

    def format_row(row: Tuple[str, str]) -> str:
        _row = list(map(str, row))
        row_str = "| "
        row_str += _row[0]
        row_str += " " * (id_col_len - len(_row[0]))
        row_str += " | "
        row_str += _row[1]
        row_str += " " * (tool_col_len - len(_row[1]))
        row_str += " |"
        return row_str

    while True:
        print(separator)
        print(format_row(("ID", "Tool")))
        print(separator)
        print("\n".join(map(format_row, enumerate(available_tools))))
        print(separator)
        try:
            tool_id = int(input("Tool ID > "))
            return available_tools[tool_id]
        except (ValueError, TypeError, IndexError):
            print("\nPlease enter valid tool ID.")


def verify_or_retrieve_tool(
    agent_id: int, ledger_api: EthereumApi, tool: Optional[str] = None
) -> str:
    """Checks if the tool is valid and for what agent."""
    available_tools = fetch_tools(agent_id=agent_id, ledger_api=ledger_api)
    if tool is not None and tool not in available_tools:
        raise ValueError(
            f"Provided tool `{tool}` not in the list of available tools; Available tools={available_tools}"
        )
    if tool is not None:
        return tool
    return _tool_selector_prompt(available_tools=available_tools)


def fetch_tools(agent_id: int, ledger_api: EthereumApi) -> List[str]:
    """Fetch tools for specified agent ID."""
    mech_registry = get_contract(
        contract_address=AGENT_REGISTRY_CONTRACT, ledger_api=ledger_api
    )
    token_uri = mech_registry.functions.tokenURI(agent_id).call()
    response = requests.get(token_uri).json()
    return response["tools"]


def send_request(
    crypto: EthereumCrypto,
    ledger_api: EthereumApi,
    mech_contract: Web3Contract,
    prompt: str,
    tool: str,
    price: int = 10_000_000_000_000_000,
) -> None:
    """Sends a request to the mech."""
    v1_file_hash_hex_truncated, v1_file_hash_hex = push_metadata_to_ipfs(prompt, tool)
    print(f"Prompt uploaded: https://gateway.autonolas.tech/ipfs/{v1_file_hash_hex}")

    method_name = "request"
    methord_args = {"data": v1_file_hash_hex_truncated}
    tx_args = {"sender_address": crypto.address, "value": price}
    raw_transaction = ledger_api.build_transaction(
        contract_instance=mech_contract,
        method_name=method_name,
        method_args=methord_args,
        tx_args=tx_args,
    )
    raw_transaction["gas"] = 50_000
    signed_transaction = crypto.sign_transaction(raw_transaction)
    transaction_digest = ledger_api.send_signed_transaction(signed_transaction)
    print(f"Transaction sent: https://gnosisscan.io/tx/{transaction_digest}")


def wait_for_data_url(
    request_id: str,
    wss: websocket.WebSocket,
    mech_contract: Web3Contract,
    ledger_api: EthereumApi,
    crypto: Crypto,
) -> Any:
    """Wait for data from on-chain/off-chain"""
    loop = asyncio.new_event_loop()
    off_chain_task = loop.create_task(watch_for_data_url_from_mech(crypto=crypto))
    on_chain_task = loop.create_task(
        watch_for_data_url_from_wss(
            request_id=request_id,
            wss=wss,
            mech_contract=mech_contract,
            ledger_api=ledger_api,
            loop=loop,
        )
    )

    async def _wait_for_tasks() -> Any:
        """Wait for tasks to finish."""
        (finished, *_), unfinished = await asyncio.wait(
            [off_chain_task, on_chain_task], return_when=asyncio.FIRST_COMPLETED
        )
        for task in unfinished:
            task.cancel()
        await asyncio.wait(unfinished)
        return finished.result()

    result = loop.run_until_complete(_wait_for_tasks())
    return result


def interact(
    prompt: str,
    agent_id: int,
    tool: Optional[str] = None,
    private_key_path: Optional[str] = None,
    confirmation_type: ConfirmationType = ConfirmationType.WAIT_FOR_BOTH,
) -> Dict[str, Any]:
    """Interact with agent mech contract."""
    contract_address = query_agent_address(agent_id=agent_id)
    if contract_address is None:
        raise ValueError(f"Agent with ID {agent_id} does not exist!")

    private_key_path = private_key_path or PRIVATE_KEY_FILE_PATH
    if not Path(private_key_path).exists():
        raise FileNotFoundError(
            f"Private key file `{private_key_path}` does not exist!"
        )

    wss = websocket.create_connection(WSS_ENDPOINT)
    crypto = EthereumCrypto(private_key_path=private_key_path)
    ledger_api = EthereumApi(**LEDGER_CONFIG)

    tool = verify_or_retrieve_tool(agent_id=agent_id, ledger_api=ledger_api, tool=tool)
    mech_contract = get_contract(
        contract_address=contract_address, ledger_api=ledger_api
    )
    register_event_handlers(wss=wss, contract_address=contract_address, crypto=crypto)
    send_request(
        crypto=crypto,
        ledger_api=ledger_api,
        mech_contract=mech_contract,
        prompt=prompt,
        tool=tool,
    )
    request_id = watch_for_request_id(
        wss=wss, mech_contract=mech_contract, ledger_api=ledger_api
    )
    print(f"Created on-chain request with ID {request_id}")
    if confirmation_type == ConfirmationType.OFF_CHAIN:
        data_url = watch_for_data_url_from_mech_sync(crypto=crypto)
    elif confirmation_type == ConfirmationType.ON_CHAIN:
        data_url = watch_for_data_url_from_wss_sync(
            request_id=request_id,
            wss=wss,
            mech_contract=mech_contract,
            ledger_api=ledger_api,
        )
    else:
        data_url = wait_for_data_url(
            request_id=request_id,
            wss=wss,
            mech_contract=mech_contract,
            ledger_api=ledger_api,
            crypto=crypto,
        )
    print(f"Data arrived: {data_url}")
    data = requests.get(f"{data_url}/{request_id}").json()
    print(f"Data from agent: {data}")
