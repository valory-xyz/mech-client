# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2024-2025 Valory AG
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
import sys
import time
from collections import defaultdict
from dataclasses import asdict, make_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast

import requests
from aea.crypto.base import Crypto
from aea_ledger_ethereum import EthereumApi, EthereumCrypto
from eth_utils import to_checksum_address
from web3._utils.events import event_abi_to_log_topic
from web3.constants import ADDRESS_ZERO
from web3.contract import Contract as Web3Contract

from mech_client.delivery import watch_for_marketplace_data, watch_for_mech_data_url
from mech_client.fetch_ipfs_hash import fetch_ipfs_hash
from mech_client.interact import (
    MAX_RETRIES,
    MechMarketplaceRequestConfig,
    PRIVATE_KEY_FILE_PATH,
    TIMEOUT,
    WAIT_SLEEP,
    get_contract,
    get_mech_config,
)
from mech_client.mech_marketplace_tool_management import get_mech_tools
from mech_client.prompt_to_ipfs import push_metadata_to_ipfs
from mech_client.safe import EthereumClient, get_safe_nonce, send_safe_tx
from mech_client.wss import wait_for_receipt, watch_for_marketplace_request_ids


# false positives for [B105:hardcoded_password_string] Possible hardcoded password
class PaymentType(Enum):
    """Payment type."""

    NATIVE = "ba699a34be8fe0e7725e93dcbce1701b0211a8ca61330aaeb8a05bf2ec7abed1"  # nosec
    TOKEN = "3679d66ef546e66ce9057c4a052f317b135bc8e8c509638f7966edfd4fcf45e9"  # nosec
    NATIVE_NVM = (
        "803dd08fe79d91027fc9024e254a0942372b92f3ccabc1bd19f4a5c2b251c316"  # nosec
    )
    TOKEN_NVM_USDC = (
        "0d6fd99afa9c4c580fab5e341922c2a5c4b61d880da60506193d7bf88944dd14"  # nosec
    )


IPFS_URL_TEMPLATE = "https://gateway.autonolas.tech/ipfs/f01701220{}"
MECH_OFFCHAIN_REQUEST_ENDPOINT = "send_signed_requests"
MECH_OFFCHAIN_DELIVER_ENDPOINT = "fetch_offchain_info"
ABI_DIR_PATH = Path(__file__).parent / "abis"
IMECH_ABI_PATH = ABI_DIR_PATH / "IMech.json"
ITOKEN_ABI_PATH = ABI_DIR_PATH / "IToken.json"
IERC1155_ABI_PATH = ABI_DIR_PATH / "IERC1155.json"
MARKETPLACE_ABI_PATH = ABI_DIR_PATH / "MechMarketplace.json"

BALANCE_TRACKER_NATIVE_ABI_PATH = ABI_DIR_PATH / "BalanceTrackerFixedPriceNative.json"
BALANCE_TRACKER_TOKEN_ABI_PATH = ABI_DIR_PATH / "BalanceTrackerFixedPriceToken.json"
BALANCE_TRACKER_NVM_NATIVE_ABI_PATH = (
    ABI_DIR_PATH / "BalanceTrackerNvmSubscriptionNative.json"
)
BALANCE_TRACKER_NVM_TOKEN_ABI_PATH = (
    ABI_DIR_PATH / "BalanceTrackerNvmSubscriptionToken.json"
)


PAYMENT_TYPE_TO_ABI_PATH: Dict[str, Path] = {
    PaymentType.NATIVE.value: BALANCE_TRACKER_NATIVE_ABI_PATH,
    PaymentType.TOKEN.value: BALANCE_TRACKER_TOKEN_ABI_PATH,
    PaymentType.NATIVE_NVM.value: BALANCE_TRACKER_NVM_NATIVE_ABI_PATH,
    PaymentType.TOKEN_NVM_USDC.value: BALANCE_TRACKER_NVM_TOKEN_ABI_PATH,
}

CHAIN_TO_PRICE_TOKEN = {
    1: "0x0001A500A6B18995B03f44bb040A5fFc28E45CB0",
    10: "0xFC2E6e6BCbd49ccf3A5f029c79984372DcBFE527",
    100: "0xcE11e14225575945b8E6Dc0D4F2dD4C570f79d9f",
    137: "0xFEF5d947472e72Efbb2E388c730B7428406F2F95",
    8453: "0x54330d28ca3357F294334BDC454a032e7f353416",
    42220: "0x96ffa56a963EC33e5bC7057B9002722D1884fc01",
}


CHAIN_TO_DEFAULT_MECH_MARKETPLACE_REQUEST_CONFIG = {
    100: {
        "response_timeout": 300,
        "payment_data": "0x",
    },
    8453: {
        "response_timeout": 300,
        "payment_data": "0x",
    },
}


def fetch_mech_deliver_event_signature(
    ledger_api: EthereumApi,
    priority_mech_address: str,
) -> str:
    """
    Fetchs the mech's deliver event signature.

    :param ledger_api: The Ethereum API used for interacting with the ledger.
    :type ledger_api: EthereumApi
    :param priority_mech_address: Requested mech address
    :type priority_mech_address: str
    :return: The event signature.
    :rtype: str
    """
    with open(IMECH_ABI_PATH, encoding="utf-8") as f:
        abi = json.load(f)

    mech_contract = get_contract(
        contract_address=priority_mech_address, abi=abi, ledger_api=ledger_api
    )
    deliver_event_abi = mech_contract.events.Deliver().abi
    mech_deliver_event_signature = event_abi_to_log_topic(deliver_event_abi)
    return mech_deliver_event_signature.hex()


def fetch_mech_info(
    ledger_api: EthereumApi,
    mech_marketplace_contract: Web3Contract,
    priority_mech_address: str,
) -> Tuple[str, int, int, str]:
    """
    Fetchs the info of the requested mech.

    :param ledger_api: The Ethereum API used for interacting with the ledger.
    :type ledger_api: EthereumApi
    :param mech_marketplace_contract: The mech marketplace contract instance.
    :type mech_marketplace_contract: Web3Contract
    :param priority_mech_address: Requested mech address
    :type priority_mech_address: str
    :return: The mech info containing payment_type, service_id, max_delivery_rate and mech_payment_balance_tracker.
    :rtype: Tuple[str, int, int, str]
    """

    with open(IMECH_ABI_PATH, encoding="utf-8") as f:
        abi = json.load(f)

    mech_contract = get_contract(
        contract_address=priority_mech_address, abi=abi, ledger_api=ledger_api
    )
    payment_type_bytes = mech_contract.functions.paymentType().call()
    max_delivery_rate = mech_contract.functions.maxDeliveryRate().call()
    service_id = mech_contract.functions.serviceId().call()
    payment_type = payment_type_bytes.hex()

    mech_payment_balance_tracker = (
        mech_marketplace_contract.functions.mapPaymentTypeBalanceTrackers(
            payment_type_bytes
        ).call()
    )

    if payment_type not in PaymentType._value2member_map_:  # pylint: disable=W0212
        print("  - Invalid mech type detected.")
        sys.exit(1)

    return (
        payment_type,
        service_id,
        max_delivery_rate,
        mech_payment_balance_tracker,
    )


def approve_price_tokens(  # pylint: disable=too-many-arguments, too-many-locals
    crypto: EthereumCrypto,
    ledger_api: EthereumApi,
    ethereum_client: EthereumClient,
    agent_mode: bool,
    safe_address: str,
    wrapped_token: str,
    mech_payment_balance_tracker: str,
    price: int,
) -> str:
    """
    Sends the approve tx for wrapped token of the sender to the requested mech's balance payment tracker contract.

    :param crypto: The Ethereum crypto object.
    :type crypto: EthereumCrypto
    :param ledger_api: The Ethereum API used for interacting with the ledger.
    :type ledger_api: EthereumApi
    :param ethereum_client: The Ethereum Client used for interacting with the safe.
    :type ethereum_client: EthereumClient
    :param agent_mode: Specifies whether agent mode is active or not.
    :type agent_mode: bool
    :param safe_address: Specifies the safe address related to the configured service, empty is client mode.
    :type safe_address: str
    :param wrapped_token: The wrapped token contract address.
    :type wrapped_token: str
    :param mech_payment_balance_tracker: Requested mech's balance tracker contract address
    :type mech_payment_balance_tracker: str
    :param price: Amount of wrapped_token to approve
    :type price: int
    :return: The transaction digest.
    :rtype: str
    """
    # Tokens will be on the safe and EOA pays for gas
    # so for agent mode, sender has to be safe
    sender = safe_address or crypto.address

    with open(ITOKEN_ABI_PATH, encoding="utf-8") as f:
        abi = json.load(f)

    token_contract = get_contract(
        contract_address=wrapped_token, abi=abi, ledger_api=ledger_api
    )

    user_token_balance = token_contract.functions.balanceOf(sender).call()
    if user_token_balance < price:
        print(
            f"  - Sender Token balance low. Needed: {price}, Actual: {user_token_balance}"
        )
        print(f"  - Sender Address: {sender}")
        sys.exit(1)

    tx_args = {"sender_address": sender, "value": 0, "gas": 60000}
    method_name = "approve"
    method_args = {"_to": mech_payment_balance_tracker, "_value": price}

    if not agent_mode:
        raw_transaction = ledger_api.build_transaction(
            contract_instance=token_contract,
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

    function = token_contract.functions[method_name](**method_args)
    transaction = function.build_transaction(
        {
            "chainId": int(ledger_api._chain_id),  # pylint: disable=protected-access
            "gas": 0,
            "nonce": get_safe_nonce(ethereum_client, safe_address),
        }
    )
    transaction_digest = send_safe_tx(
        ethereum_client=ethereum_client,
        tx_data=transaction["data"],
        to_adress=token_contract.address,
        safe_address=safe_address,
        signer_pkey=crypto.private_key,
        value=0,
    )
    return transaction_digest.hex()


def fetch_requester_nvm_subscription_balance(
    requester: str,
    ledger_api: EthereumApi,
    mech_payment_balance_tracker: str,
    payment_type: str,
) -> int:
    """
    Fetches the requester nvm subscription balance.

    :param requester: The requester's address.
    :type requester: str
    :param ledger_api: The Ethereum API used for interacting with the ledger.
    :type ledger_api: EthereumApi
    :param mech_payment_balance_tracker: Requested mech's balance tracker contract address
    :type mech_payment_balance_tracker: str
    :param payment_type: Requested mech's payment type
    :type payment_type: str
    :return: The requester balance.
    :rtype: int
    """
    with open(
        PAYMENT_TYPE_TO_ABI_PATH[payment_type],
        encoding="utf-8",
    ) as f:
        abi = json.load(f)

    nvm_balance_tracker_contract = get_contract(
        contract_address=mech_payment_balance_tracker, abi=abi, ledger_api=ledger_api
    )
    requester_balance_tracker_balance = (
        nvm_balance_tracker_contract.functions.mapRequesterBalances(requester).call()
    )
    subscription_nft_address = (
        nvm_balance_tracker_contract.functions.subscriptionNFT().call()
    )
    subscription_id = (
        nvm_balance_tracker_contract.functions.subscriptionTokenId().call()
    )

    with open(IERC1155_ABI_PATH, encoding="utf-8") as f:
        abi = json.load(f)

    subscription_nft_contract = get_contract(
        contract_address=subscription_nft_address, abi=abi, ledger_api=ledger_api
    )
    requester_balance = subscription_nft_contract.functions.balanceOf(
        requester, subscription_id
    ).call()

    return requester_balance_tracker_balance + requester_balance


def send_marketplace_request(  # pylint: disable=too-many-arguments,too-many-locals
    crypto: EthereumCrypto,
    ledger_api: EthereumApi,
    ethereum_client: EthereumClient,
    marketplace_contract: Web3Contract,
    gas_limit: int,
    prompts: tuple,
    tools: tuple,
    agent_mode: bool,
    safe_address: str,
    method_args_data: MechMarketplaceRequestConfig,
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
    :param ethereum_client: The Ethereum Client used for interacting with the safe.
    :type ethereum_client: EthereumClient
    :param marketplace_contract: The mech marketplace contract instance.
    :type marketplace_contract: Web3Contract
    :param gas_limit: Gas limit.
    :type gas_limit: int
    :param prompts: The request prompts.
    :type prompts: tuple
    :param tools: The requested tools.
    :type tools: tuple
    :param agent_mode: Specifies whether agent mode is active or not.
    :type agent_mode: bool
    :param safe_address: Specifies the safe address related to the configured service, empty is client mode.
    :type safe_address: str
    :param method_args_data: Method data to use to call the marketplace contract request
    :type method_args_data: MechMarketplaceRequestConfig
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
    num_requests = len(prompts)

    method_args = {
        "maxDeliveryRate": method_args_data.delivery_rate,
        "paymentType": "0x" + cast(str, method_args_data.payment_type),
        "priorityMech": to_checksum_address(method_args_data.priority_mech_address),
        "responseTimeout": method_args_data.response_timeout,
        "paymentData": method_args_data.payment_data,
    }

    if num_requests == 1:
        v1_file_hash_hex_truncated, v1_file_hash_hex = push_metadata_to_ipfs(
            prompts[0], tools[0], extra_attributes
        )
        print(
            f"  - Prompt uploaded: https://gateway.autonolas.tech/ipfs/{v1_file_hash_hex}"
        )
        method_name = "request"
        method_args["requestData"] = v1_file_hash_hex_truncated

    else:
        request_datas = []
        for prompt, tool in zip(prompts, tools):
            v1_file_hash_hex_truncated, v1_file_hash_hex = push_metadata_to_ipfs(
                prompt, tool, extra_attributes
            )
            print(
                f"  - Prompt uploaded: https://gateway.autonolas.tech/ipfs/{v1_file_hash_hex}"
            )
            request_datas.append(v1_file_hash_hex_truncated)

        method_name = "requestBatch"
        method_args["requestDatas"] = request_datas

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
            if not agent_mode:
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

            function = marketplace_contract.functions[method_name](**method_args)
            transaction = function.build_transaction(
                {
                    "chainId": int(
                        ledger_api._chain_id  # pylint: disable=protected-access
                    ),
                    "gas": 0,
                    "nonce": get_safe_nonce(ethereum_client, safe_address),
                }
            )
            transaction_digest = send_safe_tx(
                ethereum_client=ethereum_client,
                tx_data=transaction["data"],
                to_adress=marketplace_contract.address,
                safe_address=safe_address,
                signer_pkey=crypto.private_key,
                value=price,
            )
            return transaction_digest.hex()
        except Exception as e:  # pylint: disable=broad-except
            print(
                f"Error occured while sending the transaction: {e}; Retrying in {sleep}"
            )
            time.sleep(sleep)
    return None


def send_offchain_marketplace_request(  # pylint: disable=too-many-arguments,too-many-locals
    crypto: EthereumCrypto,
    marketplace_contract: Web3Contract,
    mech_offchain_url: str,
    prompt: str,
    tool: str,
    method_args_data: MechMarketplaceRequestConfig,
    nonce: int,
    extra_attributes: Optional[Dict[str, Any]] = None,
    retries: Optional[int] = None,
    timeout: Optional[float] = None,
    sleep: Optional[float] = None,
) -> Optional[Dict]:
    """
    Sends an offchain request to the mech.

    :param crypto: The Ethereum crypto object.
    :type crypto: EthereumCrypto
    :param marketplace_contract: The mech marketplace contract instance.
    :type marketplace_contract: Web3Contract
    :param mech_offchain_url: mech url to connect to.
    :type mech_offchain_url: str
    :param prompt: The request prompt.
    :type prompt: str
    :param tool: The requested tool.
    :type tool: str
    :param method_args_data: Method data to use to call the marketplace contract request
    :type method_args_data: MechMarketplaceRequestConfig
    :param nonce: Nonce to use to order offchain tasks
    :type nonce: int
    :param extra_attributes: Extra attributes to be included in the request metadata.
    :type extra_attributes: Optional[Dict[str,Any]]
    :param retries: Number of retries for sending a transaction
    :type retries: int
    :param timeout: Timeout to wait for the transaction
    :type timeout: float
    :param sleep: Amount of sleep before retrying the transaction
    :type sleep: float
    :return: The dict containing request info.
    :rtype: Optional[Dict]
    """
    v1_file_hash_hex_truncated, v1_file_hash_hex, ipfs_data = fetch_ipfs_hash(
        prompt, tool, extra_attributes
    )
    print(
        f"  - Prompt will shortly be uploaded to: https://gateway.autonolas.tech/ipfs/{v1_file_hash_hex}"
    )
    method_args = {
        "requestData": v1_file_hash_hex_truncated,
        "maxDeliveryRate": method_args_data.delivery_rate,
        "paymentType": "0x" + cast(str, method_args_data.payment_type),
        "priorityMech": to_checksum_address(method_args_data.priority_mech_address),
        "responseTimeout": method_args_data.response_timeout,
        "paymentData": method_args_data.payment_data,
    }

    tries = 0
    retries = retries or MAX_RETRIES
    timeout = timeout or TIMEOUT
    sleep = sleep or WAIT_SLEEP
    deadline = datetime.now().timestamp() + timeout

    while tries < retries and datetime.now().timestamp() < deadline:
        tries += 1
        try:
            delivery_rate = method_args["maxDeliveryRate"]
            request_id = marketplace_contract.functions.getRequestId(
                method_args["priorityMech"],
                crypto.address,
                method_args["requestData"],
                method_args["maxDeliveryRate"],
                method_args["paymentType"],
                nonce,
            ).call()
            request_id_int = int.from_bytes(request_id, byteorder="big")
            signature = crypto.sign_message(request_id, is_deprecated_mode=True)

            payload = {
                "sender": crypto.address,
                "signature": signature,
                "ipfs_hash": v1_file_hash_hex_truncated,
                "request_id": request_id_int,
                "delivery_rate": delivery_rate,
                "nonce": nonce,
                "ipfs_data": ipfs_data,
            }
            url = mech_offchain_url + MECH_OFFCHAIN_REQUEST_ENDPOINT
            response = requests.post(
                url=url,
                data=payload,
                headers={"Content-Type": "application/json"},
            ).json()
            return response

        except Exception as e:  # pylint: disable=broad-except
            print(
                f"Error occured while sending the offchain request: {e}; Retrying in {sleep}"
            )
            time.sleep(sleep)
    return None


def wait_for_marketplace_data_url(  # pylint: disable=too-many-arguments, unused-argument
    request_ids: List[str],
    from_block: int,
    marketplace_contract: Web3Contract,
    deliver_signature: str,
    ledger_api: EthereumApi,
    timeout: Optional[float] = None,
) -> Any:
    """
    Wait for data from on-chain/off-chain.

    :param request_ids: The IDs of the request.
    :type request_ids: List[str]
    :param from_block: The from block to start searching logs.
    :type from_block: int
    :param marketplace_contract: The mech contract instance.
    :type marketplace_contract: Web3Contract
    :param deliver_signature: Topic signature for Deliver event
    :type deliver_signature: str
    :param ledger_api: The Ethereum API used for interacting with the ledger.
    :type ledger_api: EthereumApi
    :param timeout: Timeout to wait for the onchain data
    :type timeout: float
    :return: The data received from on-chain.
    :rtype: Any
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def _wait_for_marketplace_delivery_event() -> Any:  # type: ignore
        data = await watch_for_marketplace_data(
            request_ids=request_ids,
            marketplace_contract=marketplace_contract,
            timeout=timeout,
        )
        return data

    async def _wait_for_mech_data(future) -> Any:  # type: ignore
        marketplace_data_result = await future
        requests_by_delivery_mech = defaultdict(list)
        results: Dict = {}

        # return with empty data is result is unexpected
        if len(marketplace_data_result) == 0:
            return results

        for request_id, delivery_mech in marketplace_data_result.items():
            requests_by_delivery_mech[delivery_mech].append(request_id)

        for delivery_mech, request_ids in requests_by_delivery_mech.items():
            data = await watch_for_mech_data_url(
                request_ids=request_ids,
                from_block=from_block,
                mech_contract_address=delivery_mech,
                mech_deliver_signature=deliver_signature,
                ledger_api=ledger_api,
                timeout=timeout,
            )
            results.update(data)

        return results

    marketplace_delivery_event_future = loop.create_task(
        _wait_for_marketplace_delivery_event()
    )
    mech_data_future = loop.create_task(
        _wait_for_mech_data(marketplace_delivery_event_future)
    )

    loop.run_until_complete(
        asyncio.gather(marketplace_delivery_event_future, mech_data_future)
    )
    loop.close()

    return mech_data_future.result()


def wait_for_offchain_marketplace_data(mech_offchain_url: str, request_id: str) -> Any:
    """
    Watches for data off-chain on mech.

    :param mech_offchain_url: mech url to connect to.
    :type mech_offchain_url: str
    :param request_id: The ID of the request.
    :type request_id: str
    :return: The data returned by the mech.
    :rtype: Any
    """
    while True:
        try:
            url = mech_offchain_url + MECH_OFFCHAIN_DELIVER_ENDPOINT
            response = requests.get(
                url=url,
                data={"request_id": request_id},
            ).json()
            if response:
                return response

            time.sleep(WAIT_SLEEP)
        except Exception:  # pylint: disable=broad-except
            time.sleep(WAIT_SLEEP)


def check_prepaid_balances(  # pylint: disable=too-many-arguments
    crypto: Crypto,
    ledger_api: EthereumApi,
    safe_address: str,
    mech_payment_balance_tracker: str,
    payment_type: str,
    max_delivery_rate: int,
) -> None:
    """
    Checks the requester's prepaid balances for native and token mech.

    :param crypto: The cryptographic object.
    :type crypto: Crypto
    :param ledger_api: The Ethereum API used for interacting with the ledger.
    :type ledger_api: EthereumApi
    :param safe_address: Specifies the safe address related to the configured service, empty is client mode.
    :type safe_address: str
    :param mech_payment_balance_tracker: The mech's balance tracker contract address.
    :type mech_payment_balance_tracker: str
    :param payment_type: The payment type of the mech.
    :type payment_type: str
    :param max_delivery_rate: The max_delivery_rate of the mech
    :type max_delivery_rate: int
    """
    requester = safe_address or crypto.address

    if payment_type in [PaymentType.NATIVE.value, PaymentType.TOKEN.value]:
        payment_type_name = PaymentType(payment_type).name.lower()
        payment_type_abi_path = PAYMENT_TYPE_TO_ABI_PATH[payment_type]

        with open(payment_type_abi_path, encoding="utf-8") as f:
            abi = json.load(f)

        balance_tracker_contract = get_contract(
            contract_address=mech_payment_balance_tracker,
            abi=abi,
            ledger_api=ledger_api,
        )
        requester_balance = balance_tracker_contract.functions.mapRequesterBalances(
            requester
        ).call()
        if requester_balance < max_delivery_rate:
            print(
                f"  - Sender {payment_type_name} deposited balance low. Needed: {max_delivery_rate}, Actual: {requester_balance}"
            )
            print(f"  - Sender Address: {requester}")
            print(
                f"  - Please use scripts/deposit_{payment_type_name}.py to add balance"
            )
            sys.exit(1)


def verify_tools(tools: tuple, service_id: int, chain_config: Optional[str]) -> None:
    """
    Verifies user supplied tool(s) with the mech's metadata

    :param tools: The user supplied tools.
    :type tools: tuple
    :param service_id: Service id of the mech.
    :type service_id: int
    :param chain_config: Id of the mech's chain configuration (stored configs/mechs.json)
    :type chain_config: str
    :rtype: None
    """
    mech_tools_data = get_mech_tools(service_id=service_id, chain_config=chain_config)
    if not mech_tools_data:
        raise ValueError("Error while fetching mech tools data")

    mech_tools = mech_tools_data.get("tools", [])
    invalid_tools = [tool for tool in tools if tool not in mech_tools]
    if invalid_tools:
        raise ValueError(
            f"Tool(s) {invalid_tools} not found in mech tools: {mech_tools}"
        )


def marketplace_interact(  # pylint: disable=too-many-arguments, too-many-locals, too-many-statements, too-many-return-statements
    prompts: tuple,
    priority_mech: str,
    agent_mode: bool,
    safe_address: str,
    use_prepaid: bool = False,
    use_offchain: bool = False,
    mech_offchain_url: str = "",
    tools: tuple = (),
    extra_attributes: Optional[Dict[str, Any]] = None,
    private_key_path: Optional[str] = None,
    retries: Optional[int] = None,
    timeout: Optional[float] = None,
    sleep: Optional[float] = None,
    chain_config: Optional[str] = None,
) -> Any:
    """
    Interact with mech marketplace contract.

    :param prompts: The interaction prompts.
    :type prompts: tuple
    :param priority_mech: Priority mech address to use
    :type priority_mech: str
    :param agent_mode: Specifies whether agent mode is active or not.
    :type agent_mode: bool
    :param safe_address: Specifies the safe address related to the configured service, empty is client mode.
    :type safe_address: str
    :param use_prepaid: Whether to use prepaid model or not.
    :type use_prepaid: bool
    :param use_offchain: Whether to use offchain model or not.
    :type use_offchain: bool
    :param mech_offchain_url: mech url to connect to.
    :type mech_offchain_url: str
    :param tools: The tools to interact with (optional).
    :type tools: tuple
    :param extra_attributes: Extra attributes to be included in the request metadata (optional).
    :type extra_attributes: Optional[Dict[str, Any]]
    :param private_key_path: The path to the private key file (optional).
    :type private_key_path: Optional[str]
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
    ledger_rpc = mech_config.ledger_config.address
    ethereum_client = EthereumClient(ledger_rpc)
    ledger_config = mech_config.ledger_config
    priority_mech_address = priority_mech
    mech_marketplace_contract = mech_config.mech_marketplace_contract
    chain_id = ledger_config.chain_id
    num_requests = len(prompts)

    if mech_marketplace_contract == ADDRESS_ZERO:
        print(f"Mech Marketplace not yet supported on {chain_config}")
        return None

    config_values = CHAIN_TO_DEFAULT_MECH_MARKETPLACE_REQUEST_CONFIG[chain_id].copy()
    if priority_mech_address is None:
        print("Priority Mech Address not provided")
        return None

    config_values.update(
        {
            "priority_mech_address": priority_mech_address,
            "mech_marketplace_contract": mech_marketplace_contract,
        }
    )
    mech_marketplace_request_config: MechMarketplaceRequestConfig = make_dataclass(
        "MechMarketplaceRequestConfig",
        ((k, type(v)) for k, v in config_values.items()),
    )(**config_values)

    marketplace_contract_address = cast(
        str, mech_marketplace_request_config.mech_marketplace_contract
    )

    private_key_path = private_key_path or PRIVATE_KEY_FILE_PATH
    if not Path(private_key_path).exists():
        raise FileNotFoundError(
            f"Private key file `{private_key_path}` does not exist!"
        )

    crypto = EthereumCrypto(private_key_path=private_key_path)
    ledger_api = EthereumApi(**asdict(ledger_config))

    with open(MARKETPLACE_ABI_PATH, encoding="utf-8") as f:
        abi = json.load(f)

    mech_marketplace_contract = get_contract(
        contract_address=marketplace_contract_address, abi=abi, ledger_api=ledger_api
    )

    print("Fetching Mech Info...")
    priority_mech_address = cast(
        str, mech_marketplace_request_config.priority_mech_address
    )
    (
        payment_type,
        service_id,
        max_delivery_rate,
        mech_payment_balance_tracker,
    ) = fetch_mech_info(
        ledger_api,
        mech_marketplace_contract,
        priority_mech_address,
    )
    mech_marketplace_request_config.delivery_rate = max_delivery_rate
    mech_marketplace_request_config.payment_type = payment_type

    mech_deliver_event_signature = fetch_mech_deliver_event_signature(
        ledger_api, priority_mech_address
    )

    verify_tools(tools, service_id, chain_config)

    if not use_prepaid:
        price = max_delivery_rate * num_requests
        if payment_type == PaymentType.TOKEN.value:
            print("Token Mech detected, approving wrapped token for price payment...")
            price_token = CHAIN_TO_PRICE_TOKEN[chain_id]
            approve_tx = approve_price_tokens(
                crypto,
                ledger_api,
                ethereum_client,
                agent_mode,
                safe_address,
                price_token,
                mech_payment_balance_tracker,
                price,
            )
            if not approve_tx:
                print("Unable to approve allowance")
                return None

            transaction_url_formatted = mech_config.transaction_url.format(
                transaction_digest=approve_tx
            )
            print(f"  - Transaction sent: {transaction_url_formatted}")
            print("  - Waiting for transaction receipt...")
            wait_for_receipt(approve_tx, ledger_api)
            # set price 0 to not send any msg.value in request transaction for token type mech
            price = 0

    else:
        print("Prepaid request to be used, skipping payment")
        price = 0

        check_prepaid_balances(
            crypto,
            ledger_api,
            safe_address,
            mech_payment_balance_tracker,
            payment_type,
            max_delivery_rate,
        )

    is_nvm_mech = payment_type in [
        PaymentType.NATIVE_NVM.value,
        PaymentType.TOKEN_NVM_USDC.value,
    ]
    if is_nvm_mech:
        nvm_mech_type = PaymentType(payment_type).name.lower()
        print(
            f"{nvm_mech_type} Nevermined Mech detected, subscription credits to be used"
        )
        requester = crypto.address
        requester_total_balance_before = fetch_requester_nvm_subscription_balance(
            requester, ledger_api, mech_payment_balance_tracker, payment_type
        )
        if requester_total_balance_before < price:
            print(
                f"  - Sender Subscription balance low. Needed: {price}, Actual: {requester_total_balance_before}"
            )
            print(f"  - Sender Address: {requester}")
            sys.exit(1)

        print(
            f"  - Sender Subscription balance before request: {requester_total_balance_before}"
        )
        # set price 0 to not send any msg.value in request transaction for nvm type mech
        price = 0

    # from block to be used to search for onchain events
    # and is selected before the request is sent
    # so searching for deliver events in the logs will not be missed
    w3 = ledger_api.api.eth
    latest_block = w3.block_number

    if not use_offchain:
        print("Sending Mech Marketplace request...")
        transaction_digest = send_marketplace_request(
            crypto=crypto,
            ledger_api=ledger_api,
            ethereum_client=ethereum_client,
            marketplace_contract=mech_marketplace_contract,
            gas_limit=mech_config.gas_limit,
            price=price,
            prompts=prompts,
            tools=tools,
            agent_mode=agent_mode,
            safe_address=safe_address,
            method_args_data=mech_marketplace_request_config,
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

        request_ids = watch_for_marketplace_request_ids(
            marketplace_contract=mech_marketplace_contract,
            ledger_api=ledger_api,
            tx_hash=transaction_digest,
        )
        request_id_ints = [
            int.from_bytes(bytes.fromhex(request_id), byteorder="big")
            for request_id in request_ids
        ]
        if len(request_id_ints) == 1:
            print(f"  - Created on-chain request with ID {request_id_ints[0]}")
        else:
            print(
                f"  - Created on-chain requests with IDs: {', '.join(str(rid) for rid in request_id_ints)}"
            )
        print("")

        data_urls = wait_for_marketplace_data_url(
            request_ids=request_ids,
            from_block=latest_block,
            marketplace_contract=mech_marketplace_contract,
            deliver_signature=mech_deliver_event_signature,
            ledger_api=ledger_api,
            timeout=timeout,
        )

        if not data_urls:
            print("Cannot find any data urls for the request(s)")
            return None

        if is_nvm_mech:
            requester_total_balance_after = fetch_requester_nvm_subscription_balance(
                requester,
                ledger_api,
                mech_payment_balance_tracker,
                payment_type,
            )
            print(
                f"  - Sender Subscription balance after delivery: {requester_total_balance_after}"
            )

        for request_id, data_url in data_urls.items():
            request_id_int = int.from_bytes(bytes.fromhex(request_id), byteorder="big")
            print(f"  - Data arrived: {data_url}")
            data = requests.get(f"{data_url}/{request_id_int}", timeout=30).json()
            print("  - Data from agent:")
            print(json.dumps(data, indent=2))
        return None

    print("Sending Offchain Mech Marketplace request...")
    curr_nonce = mech_marketplace_contract.functions.mapNonces(crypto.address).call()  # type: ignore
    responses = []

    for i in range(num_requests):
        response = send_offchain_marketplace_request(
            crypto=crypto,
            marketplace_contract=mech_marketplace_contract,
            mech_offchain_url=mech_offchain_url,
            prompt=prompts[0],
            tool=tools[0],
            method_args_data=mech_marketplace_request_config,
            nonce=curr_nonce + i,
            extra_attributes=extra_attributes,
            retries=retries,
            timeout=timeout,
            sleep=sleep,
        )
        responses.append(response)

    if not responses and len(responses) != num_requests:
        return None

    request_ids = [resp["request_id"] for resp in responses if resp is not None]
    if len(request_ids) == 1:
        print(f"  - Created off-chain request with ID {request_ids[0]}")
    else:
        print(
            f"  - Created off-chain requests with IDs: {', '.join(str(rid) for rid in request_ids)}"
        )
    print("")

    # @note as we are directly querying data from done task list, we get the full data instead of the ipfs hash
    print("Waiting for Offchain Mech Marketplace deliver...")

    for request_id in request_ids:
        data = wait_for_offchain_marketplace_data(
            mech_offchain_url=mech_offchain_url,
            request_id=request_id,
        )

        if data:
            task_result = data["task_result"]
            data_url = IPFS_URL_TEMPLATE.format(task_result)
            print(f"  - Data arrived: {data_url}")
            data = requests.get(f"{data_url}/{request_id}", timeout=30).json()
            print("  - Data from agent:")
            print(json.dumps(data, indent=2))
    return None
