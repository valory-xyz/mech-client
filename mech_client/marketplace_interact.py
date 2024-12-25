# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2024 Valory AG
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

"""This script allows sending a Request to an on-chain mech marketplace and waiting for the Deliver."""


import asyncio
import json
import time
from dataclasses import asdict, make_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast

import requests
import websocket
from aea.crypto.base import Crypto
from aea_ledger_ethereum import EthereumApi, EthereumCrypto
from web3.contract import Contract as Web3Contract

from mech_client.interact import (
    ConfirmationType,
    MAX_RETRIES,
    MechMarketplaceConfig,
    PRIVATE_KEY_FILE_PATH,
    TIMEOUT,
    WAIT_SLEEP,
    calculate_topic_id,
    get_contract,
    get_mech_config,
    verify_or_retrieve_tool,
)
from mech_client.prompt_to_ipfs import push_metadata_to_ipfs
from mech_client.wss import (
    register_event_handlers,
    watch_for_marketplace_data_url_from_wss,
    watch_for_marketplace_request_id,
)


CHAIN_TO_DEFAULT_MECH_MARKETPLACE_CONFIG = {
    100: {
        "mech_marketplace_contract": "0xfE48DbCb92EbE155054aBf6a8273f6be82D56232",
        "priority_mech_service_id": 1,
        "requester_service_id": 0,
        "response_timeout": 300,
        "payment_data": "0x",
    }
}


def get_event_signatures(abi: List) -> Tuple[str, str]:
    """Calculate `Marketplace Request` and `Marketplace Deliver` event topics"""
    marketplace_request, marketplace_deliver = "", ""
    for obj in abi:
        if obj["type"] != "event":
            continue
        if obj["name"] == "MarketplaceDeliver":
            marketplace_deliver = calculate_topic_id(event=obj)
        if obj["name"] == "MarketplaceRequest":
            marketplace_request = calculate_topic_id(event=obj)
    return marketplace_request, marketplace_deliver


def send_marketplace_request(  # pylint: disable=too-many-arguments,too-many-locals
    crypto: EthereumCrypto,
    ledger_api: EthereumApi,
    marketplace_contract: Web3Contract,
    gas_limit: int,
    prompt: str,
    tool: str,
    method_args_data: MechMarketplaceConfig,
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
    :param marketplace_contract: The mech marketplace contract instance.
    :type marketplace_contract: Web3Contract
    :param gas_limit: Gas limit.
    :type gas_limit: int
    :param prompt: The request prompt.
    :type prompt: str
    :param tool: The requested tool.
    :type tool: str
    :param method_args_data: Method data to use to call the marketplace contract request
    :type method_args_data: MechMarketplaceConfig
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
    method_args = {
        "data": v1_file_hash_hex_truncated,
        "priorityMechServiceId": method_args_data.priority_mech_service_id,
        "requesterServiceId": method_args_data.requester_service_id,
        "responseTimeout": method_args_data.response_timeout,
        "paymentData": "0x",
    }
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
                contract_instance=marketplace_contract,
                method_name=method_name,
                method_args=method_args,
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


def wait_for_marketplace_data_url(  # pylint: disable=too-many-arguments, unused-argument
    request_id: str,
    wss: websocket.WebSocket,
    marketplace_contract: Web3Contract,
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
    :param marketplace_contract: The mech marketplace contract instance.
    :type marketplace_contract: Web3Contract
    :param subgraph_url: Subgraph URL.
    :type subgraph_url: str
    :param deliver_signature: Topic signature for MarketplaceDeliver event
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
        print("Off chain to be implemented")

    if confirmation_type in (
        ConfirmationType.ON_CHAIN,
        ConfirmationType.WAIT_FOR_BOTH,
    ):
        on_chain_task = loop.create_task(
            watch_for_marketplace_data_url_from_wss(
                request_id=request_id,
                wss=wss,
                marketplace_contract=marketplace_contract,
                deliver_signature=deliver_signature,
                ledger_api=ledger_api,
                loop=loop,
            )
        )
        tasks.append(on_chain_task)

        if subgraph_url:
            print("Subgraph to be implemented")

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


def marketplace_interact(  # pylint: disable=too-many-arguments, too-many-locals
    prompt: str,
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
    Interact with mech marketplace contract.

    :param prompt: The interaction prompt.
    :type prompt: str
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
    mech_marketplace_config = mech_config.mech_marketplace_config
    chain_id = ledger_config.chain_id

    if mech_marketplace_config is None:
        config_values = CHAIN_TO_DEFAULT_MECH_MARKETPLACE_CONFIG[chain_id]
        mech_marketplace_config = make_dataclass(
            "MechMarketplaceConfig", ((k, type(v)) for k, v in config_values.items())
        )(**config_values)

    contract_address = cast(str, mech_marketplace_config.mech_marketplace_contract)

    private_key_path = private_key_path or PRIVATE_KEY_FILE_PATH
    if not Path(private_key_path).exists():
        raise FileNotFoundError(
            f"Private key file `{private_key_path}` does not exist!"
        )

    wss = websocket.create_connection(mech_config.wss_endpoint)
    crypto = EthereumCrypto(private_key_path=private_key_path)
    ledger_api = EthereumApi(**asdict(ledger_config))

    # Expected parameters: agent id and agent registry contract address
    # Note: passing service id and service registry contract address as internal function calls are same
    tool = verify_or_retrieve_tool(
        agent_id=cast(int, mech_marketplace_config.priority_mech_service_id),
        ledger_api=ledger_api,
        tool=tool,
        agent_registry_contract=mech_config.service_registry_contract,
        contract_abi_url=mech_config.contract_abi_url,
    )

    with open(
        Path(__file__).parent / "abis" / "MechMarketplace.json", encoding="utf-8"
    ) as f:
        abi = json.load(f)

    mech_marketplace_contract = get_contract(
        contract_address=contract_address, abi=abi, ledger_api=ledger_api
    )

    (
        marketplace_request_event_signature,
        marketplace_deliver_event_signature,
    ) = get_event_signatures(abi=abi)

    register_event_handlers(
        wss=wss,
        contract_address=contract_address,
        crypto=crypto,
        request_signature=marketplace_request_event_signature,
        deliver_signature=marketplace_deliver_event_signature,
    )

    print("Sending Mech Marketplace request...")
    price = mech_config.price or 10_000_000_000_000_000

    transaction_digest = send_marketplace_request(
        crypto=crypto,
        ledger_api=ledger_api,
        marketplace_contract=mech_marketplace_contract,
        gas_limit=mech_config.gas_limit,
        price=price,
        prompt=prompt,
        tool=tool,
        method_args_data=mech_marketplace_config,
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

    request_id = watch_for_marketplace_request_id(
        wss=wss,
        marketplace_contract=mech_marketplace_contract,
        ledger_api=ledger_api,
        request_signature=marketplace_request_event_signature,
    )
    print(f"  - Created on-chain request with ID {request_id}")
    print("")

    print("Waiting for Mech Marketplace deliver...")
    data_url = wait_for_marketplace_data_url(
        request_id=request_id,
        wss=wss,
        marketplace_contract=mech_marketplace_contract,
        subgraph_url=mech_config.subgraph_url,
        deliver_signature=marketplace_deliver_event_signature,
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
