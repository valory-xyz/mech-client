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
import time
import warnings
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import requests
import websocket
from aea.crypto.base import Crypto
from aea_ledger_ethereum import EthereumApi, EthereumCrypto
from web3 import Web3
from web3.contract import Contract as Web3Contract

from mech_client.acn import watch_for_data_url_from_mech
from mech_client.prompt_to_ipfs import push_metadata_to_ipfs
from mech_client.subgraph import query_agent_address, watch_for_data_url_from_subgraph
from mech_client.wss import (
    register_event_handlers,
    watch_for_data_url_from_wss,
    watch_for_request_id,
)


PRIVATE_KEY_FILE_PATH = "ethereum_private_key.txt"
MECH_CONFIGS = Path(__file__).parent / "configs" / "mechs.json"
ABI_DIR_PATH = Path(__file__).parent / "abis"
AGENT_REGISTRY_ABI_PATH = ABI_DIR_PATH / "AgentRegistry.json"
AGENT_MECH_ABI_PATH = ABI_DIR_PATH / "AgentMech.json"

MAX_RETRIES = 3
WAIT_SLEEP = 3.0
TIMEOUT = 60.0

# Ignore a specific warning message
warnings.filterwarnings("ignore", "The log with transaction hash.*")


@dataclass
class LedgerConfig:
    """Ledger configuration"""

    address: str
    chain_id: int
    poa_chain: bool
    default_gas_price_strategy: str
    is_gas_estimation_enabled: bool

    def __post_init__(self) -> None:
        """Post initialization to override with environment variables."""
        address = os.getenv("MECHX_LEDGER_ADDRESS")
        if address:
            self.address = address

        chain_id = os.getenv("MECHX_LEDGER_CHAIN_ID")
        if chain_id:
            self.chain_id = int(chain_id)

        poa_chain = os.getenv("MECHX_LEDGER_POA_CHAIN")
        if poa_chain:
            self.poa_chain = bool(poa_chain)

        default_gas_price_strategy = os.getenv(
            "MECHX_LEDGER_DEFAULT_GAS_PRICE_STRATEGY"
        )
        if default_gas_price_strategy:
            self.default_gas_price_strategy = default_gas_price_strategy

        is_gas_estimation_enabled = os.getenv("MECHX_LEDGER_IS_GAS_ESTIMATION_ENABLED")
        if is_gas_estimation_enabled:
            self.is_gas_estimation_enabled = bool(is_gas_estimation_enabled)


@dataclass
class MechMarketplaceRequestConfig:
    """Mech Marketplace Request Config"""

    mech_marketplace_contract: Optional[str] = field(default=None)
    priority_mech_address: Optional[str] = field(default=None)
    delivery_rate: Optional[int] = field(default=None)
    payment_type: Optional[str] = field(default=None)
    response_timeout: Optional[int] = field(default=None)
    payment_data: Optional[str] = field(default=None)


@dataclass
class MechConfig:  # pylint: disable=too-many-instance-attributes
    """Mech configuration"""

    agent_registry_contract: str
    service_registry_contract: str
    complementary_metadata_hash_address: str
    rpc_url: str
    wss_endpoint: str
    ledger_config: LedgerConfig
    gas_limit: int
    transaction_url: str
    subgraph_url: str
    price: int
    mech_marketplace_contract: str
    priority_mech_address: Optional[str] = field(default=None)

    def __post_init__(self) -> None:
        """Post initialization to override with environment variables."""
        agent_registry_contract = os.getenv("MECHX_AGENT_REGISTRY_CONTRACT")
        if agent_registry_contract:
            self.agent_registry_contract = agent_registry_contract

        service_registry_contract = os.getenv("MECHX_SERVICE_REGISTRY_CONTRACT")
        if service_registry_contract:
            self.service_registry_contract = service_registry_contract

        rpc_url = os.getenv("MECHX_CHAIN_RPC")
        if rpc_url:
            self.rpc_url = rpc_url

        wss_endpoint = os.getenv("MECHX_WSS_ENDPOINT")
        if wss_endpoint:
            self.wss_endpoint = wss_endpoint

        gas_limit = os.getenv("MECHX_GAS_LIMIT")
        if gas_limit:
            self.gas_limit = int(gas_limit)

        transaction_url = os.getenv("MECHX_TRANSACTION_URL")
        if transaction_url:
            self.transaction_url = transaction_url

        subgraph_url = os.getenv("MECHX_SUBGRAPH_URL")
        if subgraph_url:
            self.subgraph_url = subgraph_url


class ConfirmationType(Enum):
    """Verification type."""

    ON_CHAIN = "on-chain"
    OFF_CHAIN = "off-chain"
    WAIT_FOR_BOTH = "wait-for-both"


def get_mech_config(chain_config: Optional[str] = None) -> MechConfig:
    """Get `MechConfig` configuration"""
    with open(MECH_CONFIGS, "r", encoding="UTF-8") as file:
        data = json.load(file)

        if chain_config is None:
            chain_config = next(iter(data))

        entry = data[chain_config].copy()
        ledger_config = LedgerConfig(**entry.pop("ledger_config"))

        mech_config = MechConfig(
            **entry,
            ledger_config=ledger_config,
        )
        return mech_config


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


def get_abi(contract_abi_path: Path) -> List:
    """Get contract abi"""
    with open(contract_abi_path, encoding="utf-8") as f:
        abi = json.load(f)

    return abi if abi else []


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
    agent_id: int,
    ledger_api: EthereumApi,
    agent_registry_contract: str,
    contract_abi_path: Path,
    tool: Optional[str] = None,
) -> str:
    """
    Checks if the tool is valid and for what agent.

    :param agent_id: The ID of the agent.
    :type agent_id: int
    :param ledger_api: The Ethereum API used for interacting with the ledger.
    :type ledger_api: EthereumApi
    :param agent_registry_contract: Agent registry contract address.
    :type agent_registry_contract: str
    :param contract_abi_path: Path to agent registry abi.
    :type contract_abi_path: Path
    :param tool: The tool to verify or retrieve (optional).
    :type tool: Optional[str]
    :return: The result of the verification or retrieval.
    :rtype: str
    """
    # Fetch tools, possibly including metadata
    tools_data = fetch_tools(
        agent_id=agent_id,
        ledger_api=ledger_api,
        agent_registry_contract=agent_registry_contract,
        contract_abi_path=contract_abi_path,
        include_metadata=False,  # Ensure this is False to only get the list of tools
    )
    # Ensure only the list of tools is used
    available_tools = tools_data if isinstance(tools_data, list) else tools_data[0]
    if tool is not None and tool not in available_tools:
        raise ValueError(
            f"Provided tool `{tool}` not in the list of available tools; Available tools={available_tools}"
        )
    if tool is not None:
        return tool
    return _tool_selector_prompt(available_tools=available_tools)


def fetch_tools(
    agent_id: int,
    ledger_api: EthereumApi,
    agent_registry_contract: str,
    contract_abi_path: Path,
    include_metadata: bool = False,
) -> Union[List[str], Tuple[List[str], Dict[str, Any]]]:
    """Fetch tools for specified agent ID, optionally include metadata."""
    mech_registry = get_contract(
        contract_address=agent_registry_contract,
        abi=get_abi(contract_abi_path),
        ledger_api=ledger_api,
    )
    token_uri = mech_registry.functions.tokenURI(agent_id).call()
    response = requests.get(token_uri).json()
    tools = response.get("tools", [])

    if include_metadata:
        tool_metadata = response.get("toolMetadata", {})
        return tools, tool_metadata
    return tools


def send_request(  # pylint: disable=too-many-arguments,too-many-locals
    crypto: EthereumCrypto,
    ledger_api: EthereumApi,
    mech_contract: Web3Contract,
    gas_limit: int,
    prompt: str,
    tool: str,
    extra_attributes: Optional[Dict[str, Any]] = None,
    price: int = 10_000_000_000_000_000,
    retries: Optional[int] = None,
    timeout: Optional[float] = None,
    sleep: Optional[float] = None,
) -> Optional[str]:
    """
    Sends a request to the mech.

    :param crypto: The Ethereum crypto object.
    :type crypto: EthereumCrypto
    :param ledger_api: The Ethereum API used for interacting with the ledger.
    :type ledger_api: EthereumApi
    :param mech_contract: The mech contract instance.
    :type mech_contract: Web3Contract
    :param gas_limit: Gas limit.
    :type gas_limit: int
    :param prompt: The request prompt.
    :type prompt: str
    :param tool: The requested tool.
    :type tool: str
    :param extra_attributes: Extra attributes to be included in the request metadata.
    :type extra_attributes: Optional[Dict[str,Any]]
    :param price: The price for the request (default: 10_000_000_000_000_000).
    :type price: int
    :param retries: Number of retries for sending a transaction
    :type retries: int
    :param timeout: Timeout to wait for the transaction
    :type timeout: float
    :param sleep: Amount of sleep before retrying the transaction
    :type sleep: float
    :return: The transaction hash.
    :rtype: Optional[str]
    """
    v1_file_hash_hex_truncated, v1_file_hash_hex = push_metadata_to_ipfs(
        prompt, tool, extra_attributes
    )
    print(
        f"  - Prompt uploaded: https://gateway.autonolas.tech/ipfs/{v1_file_hash_hex}"
    )
    method_name = "request"
    methord_args = {"data": v1_file_hash_hex_truncated}
    tx_args = {
        "sender_address": crypto.address,
        "value": price,
        "gas": gas_limit,
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
            return transaction_digest
        except Exception as e:  # pylint: disable=broad-except
            print(
                f"Error occured while sending the transaction: {e}; Retrying in {sleep}"
            )
            time.sleep(sleep)
    return None


def wait_for_data_url(  # pylint: disable=too-many-arguments
    request_id: str,
    wss: websocket.WebSocket,
    mech_contract: Web3Contract,
    subgraph_url: str,
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
    :param subgraph_url: Subgraph URL.
    :type subgraph_url: str
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
    asyncio.set_event_loop(loop)
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
        tasks.append(on_chain_task)

        if subgraph_url:
            mech_task = loop.create_task(
                watch_for_data_url_from_subgraph(
                    request_id=request_id, url=subgraph_url
                )
            )
            tasks.append(mech_task)

    async def _wait_for_tasks() -> Any:  # type: ignore
        """Wait for tasks to finish."""
        (finished, *_), unfinished = await asyncio.wait(
            tasks,
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in unfinished:
            task.cancel()
        if unfinished:
            await asyncio.wait(unfinished)
        return finished.result()

    result = loop.run_until_complete(_wait_for_tasks())
    return result


def interact(  # pylint: disable=too-many-arguments,too-many-locals
    prompt: str,
    agent_id: int,
    tool: Optional[str] = None,
    extra_attributes: Optional[Dict[str, Any]] = None,
    private_key_path: Optional[str] = None,
    confirmation_type: ConfirmationType = ConfirmationType.WAIT_FOR_BOTH,
    retries: Optional[int] = None,
    timeout: Optional[float] = None,
    sleep: Optional[float] = None,
    chain_config: Optional[str] = None,
) -> Any:
    """
    Interact with agent mech contract.

    :param prompt: The interaction prompt.
    :type prompt: str
    :param agent_id: The ID of the agent.
    :type agent_id: int
    :param tool: The tool to interact with (optional).
    :type tool: Optional[str]
    :param extra_attributes: Extra attributes to be included in the request metadata (optional).
    :type extra_attributes: Optional[Dict[str, Any]]
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
    :param chain_config: Id of the mech's chain configuration (stored configs/mechs.json)
    :type chain_config: str:
    :rtype: Any
    """
    mech_config = get_mech_config(chain_config)
    ledger_config = mech_config.ledger_config
    contract_address = query_agent_address(
        agent_id=agent_id,
        chain_config=chain_config,
    )
    if contract_address is None:
        raise ValueError(f"Agent with ID {agent_id} does not exist!")

    private_key_path = private_key_path or PRIVATE_KEY_FILE_PATH
    if not Path(private_key_path).exists():
        raise FileNotFoundError(
            f"Private key file `{private_key_path}` does not exist!"
        )

    wss = websocket.create_connection(mech_config.wss_endpoint)
    crypto = EthereumCrypto(private_key_path=private_key_path)
    ledger_api = EthereumApi(**asdict(ledger_config))

    tool = verify_or_retrieve_tool(
        agent_id=agent_id,
        ledger_api=ledger_api,
        tool=tool,
        agent_registry_contract=mech_config.agent_registry_contract,
        contract_abi_path=AGENT_REGISTRY_ABI_PATH,
    )
    abi = get_abi(AGENT_MECH_ABI_PATH)
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
    print("Sending Mech request...")
    price = mech_config.price or 10_000_000_000_000_000
    transaction_digest = send_request(
        crypto=crypto,
        ledger_api=ledger_api,
        mech_contract=mech_contract,
        gas_limit=mech_config.gas_limit,
        price=price,
        prompt=prompt,
        tool=tool,
        extra_attributes=extra_attributes,
        retries=retries,
        timeout=timeout,
        sleep=sleep,
    )

    if not transaction_digest:
        print("Unable to send request")
        return None

    transaction_url_formatted = mech_config.transaction_url.format(
        transaction_digest=transaction_digest
    )
    print(f"  - Transaction sent: {transaction_url_formatted}")
    print("  - Waiting for transaction receipt...")
    request_id = watch_for_request_id(
        wss=wss,
        mech_contract=mech_contract,
        ledger_api=ledger_api,
        request_signature=request_event_signature,
    )
    print(f"  - Created on-chain request with ID {request_id}")
    print("")

    print("Waiting for Mech deliver...")
    data_url = wait_for_data_url(
        request_id=request_id,
        wss=wss,
        mech_contract=mech_contract,
        subgraph_url=mech_config.subgraph_url,
        deliver_signature=deliver_event_signature,
        ledger_api=ledger_api,
        crypto=crypto,
        confirmation_type=confirmation_type,
    )
    if data_url:
        print(f"  - Data arrived: {data_url}")
        data = requests.get(f"{data_url}/{request_id}", timeout=30).json()
        print("  - Data from agent:")
        print(json.dumps(data, indent=2))
        return data
    return None
