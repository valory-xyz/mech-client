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
import os
import time
import warnings
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
import websocket
from aea.crypto.base import Crypto
from aea_ledger_ethereum import EthereumApi, EthereumCrypto
from web3 import Web3
from web3.contract import Contract as Web3Contract

from mech_client.acn import (
    watch_for_data_url_from_mech,
    watch_for_data_url_from_mech_sync,
)
from mech_client.prompt_to_ipfs import push_metadata_to_ipfs
from mech_client.subgraph import query_agent_address, watch_for_data_url_from_subgraph
from mech_client.wss import (
    register_event_handlers,
    watch_for_data_url_from_wss,
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
    "is_gas_estimation_enabled": False,
}
PRIVATE_KEY_FILE_PATH = "ethereum_private_key.txt"

WSS_ENDPOINT = os.getenv(
    "WEBSOCKET_ENDPOINT",
    "wss://rpc.eu-central-2.gateway.fm/ws/v4/gnosis/non-archival/mainnet",
)
MANUAL_GAS_LIMIT = int(
    os.getenv(
        "MANUAL_GAS_LIMIT",
        "100_000",
    )
)
BLOCKSCOUT_API_URL = (
    "https://gnosis.blockscout.com/api/v2/smart-contracts/{contract_address}"
)

MAX_RETRIES = 3
WAIT_SLEEP = 3.0
TIMEOUT = 60.0

# Ignore a specific warning message
warnings.filterwarnings("ignore", "The log with transaction hash.*")


class ConfirmationType(Enum):
    """Verification type."""

    ON_CHAIN = "on-chain"
    OFF_CHAIN = "off-chain"
    WAIT_FOR_BOTH = "wait-for-both"


def calculate_topic_id(event: Dict) -> str:
    """Caclulate topic ID"""
    text = event["name"]
    text += "("
    for inp in event["inputs"]:
        text += inp["type"]
        text += ","
    text = text[:-1]
    text += ")"
    return Web3.keccak(text=text).hex()


def get_event_signatures(abi: List) -> Tuple[str, str]:
    """Calculate `Request` and `Deliver` event topics"""
    request, deliver = "", ""
    for obj in abi:
        if obj["type"] != "event":
            continue
        if obj["name"] == "Deliver":
            deliver = calculate_topic_id(event=obj)
        if obj["name"] == "Request":
            request = calculate_topic_id(event=obj)
    return request, deliver


def get_abi(contract_address: str) -> List:
    """Get contract abi"""
    abi_request_url = BLOCKSCOUT_API_URL.format(contract_address=contract_address)
    response = requests.get(abi_request_url).json()
    return response["abi"]


def get_contract(
    contract_address: str, abi: List, ledger_api: EthereumApi
) -> Web3Contract:
    """
    Returns a contract instance.

    :param contract_address: The address of the contract.
    :type contract_address: str
    :param abi: ABI Object
    :type abi: List
    :param ledger_api: The Ethereum API used for interacting with the ledger.
    :type ledger_api: EthereumApi
    :return: The contract instance.
    :rtype: Web3Contract
    """

    return ledger_api.get_contract_instance(
        {"abi": abi, "bytecode": "0x"}, contract_address
    )


def _tool_selector_prompt(available_tools: List[str]) -> str:
    """
    Tool selector prompt.

    :param available_tools: A list of available tools.
    :type available_tools: List[str]
    :return: The selected tool.
    :rtype: str
    """

    tool_col_len = max(map(len, available_tools))
    id_col_len = max(2, len(str(len(available_tools))))
    table_len = tool_col_len + id_col_len + 5

    separator = "|" + "-" * table_len + "|"
    print("Select prompting tool")

    def format_row(row: Tuple[Any, Any]) -> str:
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
    """
    Checks if the tool is valid and for what agent.

    :param agent_id: The ID of the agent.
    :type agent_id: int
    :param ledger_api: The Ethereum API used for interacting with the ledger.
    :type ledger_api: EthereumApi
    :param tool: The tool to verify or retrieve (optional).
    :type tool: Optional[str]
    :return: The result of the verification or retrieval.
    :rtype: str
    """
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
        contract_address=AGENT_REGISTRY_CONTRACT,
        abi=get_abi(AGENT_REGISTRY_CONTRACT),
        ledger_api=ledger_api,
    )
    token_uri = mech_registry.functions.tokenURI(agent_id).call()
    response = requests.get(token_uri).json()
    return response["tools"]


def send_request(  # pylint: disable=too-many-arguments,too-many-locals
    crypto: EthereumCrypto,
    ledger_api: EthereumApi,
    mech_contract: Web3Contract,
    prompt: str,
    tool: str,
    price: int = 10_000_000_000_000_000,
    retries: Optional[int] = None,
    timeout: Optional[float] = None,
    sleep: Optional[float] = None,
) -> None:
    """
    Sends a request to the mech.

    :param crypto: The Ethereum crypto object.
    :type crypto: EthereumCrypto
    :param ledger_api: The Ethereum API used for interacting with the ledger.
    :type ledger_api: EthereumApi
    :param mech_contract: The mech contract instance.
    :type mech_contract: Web3Contract
    :param prompt: The request prompt.
    :type prompt: str
    :param tool: The requested tool.
    :type tool: str
    :param price: The price for the request (default: 10_000_000_000_000_000).
    :type price: int
    :param retries: Number of retries for sending a transaction
    :type retries: int
    :param timeout: Timeout to wait for the transaction
    :type timeout: float
    :param sleep: Amount of sleep before retrying the transaction
    :type sleep: float
    """
    v1_file_hash_hex_truncated, v1_file_hash_hex = push_metadata_to_ipfs(prompt, tool)
    print(f"Prompt uploaded: https://gateway.autonolas.tech/ipfs/{v1_file_hash_hex}")
    method_name = "request"
    methord_args = {"data": v1_file_hash_hex_truncated}
    tx_args = {
        "sender_address": crypto.address,
        "value": price,
        "gas": MANUAL_GAS_LIMIT,
    }

    tries = 0
    retries = retries or MAX_RETRIES
    timeout = timeout or TIMEOUT
    sleep = sleep or WAIT_SLEEP
    deadline = datetime.now().timestamp() + timeout

    while tries < retries and datetime.now().timestamp() < deadline:
        tries += 1
        try:
            raw_transaction = ledger_api.build_transaction(
                contract_instance=mech_contract,
                method_name=method_name,
                method_args=methord_args,
                tx_args=tx_args,
                raise_on_try=True,
            )
            signed_transaction = crypto.sign_transaction(raw_transaction)
            transaction_digest = ledger_api.send_signed_transaction(
                signed_transaction,
                raise_on_try=True,
            )
            print(f"Transaction sent: https://gnosisscan.io/tx/{transaction_digest}")
            return
        except Exception as e:  # pylint: disable=broad-except
            print(
                f"Error occured while sending the transaction: {e}; Retrying in {sleep}"
            )
            time.sleep(sleep)


def wait_for_data_url(  # pylint: disable=too-many-arguments
    request_id: str,
    wss: websocket.WebSocket,
    mech_contract: Web3Contract,
    deliver_signature: str,
    ledger_api: EthereumApi,
    crypto: Crypto,
    confirmation_type: ConfirmationType = ConfirmationType.WAIT_FOR_BOTH,
) -> Any:
    """
    Wait for data from on-chain/off-chain.

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
    :param crypto: The cryptographic object.
    :type crypto: Crypto
    :param confirmation_type: The confirmation type for the interaction (default: ConfirmationType.WAIT_FOR_BOTH).
    :type confirmation_type: ConfirmationType
    :return: The data received from on-chain/off-chain.
    :rtype: Any
    """
    loop = asyncio.new_event_loop()
    tasks = []

    if confirmation_type in (
        ConfirmationType.OFF_CHAIN,
        ConfirmationType.WAIT_FOR_BOTH,
    ):
        off_chain_task = loop.create_task(watch_for_data_url_from_mech(crypto=crypto))
        tasks.append(off_chain_task)

    if confirmation_type in (
        ConfirmationType.ON_CHAIN,
        ConfirmationType.WAIT_FOR_BOTH,
    ):
        on_chain_task = loop.create_task(
            watch_for_data_url_from_wss(
                request_id=request_id,
                wss=wss,
                mech_contract=mech_contract,
                deliver_signature=deliver_signature,
                ledger_api=ledger_api,
                loop=loop,
            )
        )
        mech_task = loop.create_task(
            watch_for_data_url_from_subgraph(request_id=request_id)
        )
        tasks.append(mech_task)
        tasks.append(on_chain_task)

    async def _wait_for_tasks() -> Any:  # type: ignore
        """Wait for tasks to finish."""
        (finished, *_), unfinished = await asyncio.wait(
            tasks,
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in unfinished:
            task.cancel()
        await asyncio.wait(unfinished)
        return finished.result()

    result = loop.run_until_complete(_wait_for_tasks())
    return result


def interact(  # pylint: disable=too-many-arguments,too-many-locals
    prompt: str,
    agent_id: int,
    tool: Optional[str] = None,
    private_key_path: Optional[str] = None,
    confirmation_type: ConfirmationType = ConfirmationType.WAIT_FOR_BOTH,
    retries: Optional[int] = None,
    timeout: Optional[float] = None,
    sleep: Optional[float] = None,
) -> Any:
    """
    Interact with agent mech contract.

    :param prompt: The interaction prompt.
    :type prompt: str
    :param agent_id: The ID of the agent.
    :type agent_id: int
    :param tool: The tool to interact with (optional).
    :type tool: Optional[str]
    :param private_key_path: The path to the private key file (optional).
    :type private_key_path: Optional[str]
    :param confirmation_type: The confirmation type for the interaction (default: ConfirmationType.WAIT_FOR_BOTH).
    :type confirmation_type: ConfirmationType
    :return: The data received from on-chain/off-chain.
    :param retries: Number of retries for sending a transaction
    :type retries: int
    :param timeout: Timeout to wait for the transaction
    :type timeout: float
    :param sleep: Amount of sleep before retrying the transaction
    :type sleep: float
    :rtype: Any
    """
    contract_address = query_agent_address(agent_id=agent_id, timeout=timeout)
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
    abi = get_abi(contract_address=contract_address)
    mech_contract = get_contract(
        contract_address=contract_address, abi=abi, ledger_api=ledger_api
    )
    request_event_signature, deliver_event_signature = get_event_signatures(abi=abi)
    register_event_handlers(
        wss=wss,
        contract_address=contract_address,
        crypto=crypto,
        request_signature=request_event_signature,
        deliver_signature=deliver_event_signature,
    )
    send_request(
        crypto=crypto,
        ledger_api=ledger_api,
        mech_contract=mech_contract,
        prompt=prompt,
        tool=tool,
        retries=retries,
        timeout=timeout,
        sleep=sleep,
    )
    request_id = watch_for_request_id(
        wss=wss,
        mech_contract=mech_contract,
        ledger_api=ledger_api,
        request_signature=request_event_signature,
    )
    print(f"Created on-chain request with ID {request_id}")
    if confirmation_type == ConfirmationType.OFF_CHAIN:
        data_url = watch_for_data_url_from_mech_sync(crypto=crypto)
    elif confirmation_type == ConfirmationType.ON_CHAIN:
        data_url = wait_for_data_url(
            request_id=request_id,
            wss=wss,
            mech_contract=mech_contract,
            deliver_signature=deliver_event_signature,
            ledger_api=ledger_api,
            crypto=crypto,
            confirmation_type=confirmation_type,
        )
    else:
        data_url = wait_for_data_url(
            request_id=request_id,
            wss=wss,
            mech_contract=mech_contract,
            deliver_signature=deliver_event_signature,
            ledger_api=ledger_api,
            crypto=crypto,
            confirmation_type=confirmation_type,
        )
    print(f"Data arrived: {data_url}")
    data = requests.get(f"{data_url}/{request_id}").json()
    print(f"Data from agent: {data}")
    return data
