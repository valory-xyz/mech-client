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

"""Websocket and transaction receipt helpers for marketplace operations."""

import time
from typing import Dict, List

from aea_ledger_ethereum import EthereumApi
from web3.contract import Contract as Web3Contract


TRANSACTION_RECEIPT_TIMEOUT = 300.0  # 5 minutes


def wait_for_receipt(
    tx_hash: str, ledger_api: EthereumApi, timeout: float = TRANSACTION_RECEIPT_TIMEOUT
) -> Dict:
    """
    Wait for receipt via HTTP RPC endpoint.

    :param tx_hash: The transaction hash.
    :type tx_hash: str
    :param ledger_api: The Ethereum API used for interacting with the ledger.
    :type ledger_api: EthereumApi
    :param timeout: Maximum time to wait for receipt in seconds (default: 300).
    :type timeout: float
    :return: The receipt of the transaction.
    :rtype: Dict
    :raises TimeoutError: If timeout is exceeded while waiting for receipt.
    """
    start_time = time.time()
    last_exception = None
    retry_count = 0

    while True:
        try:
            return ledger_api._api.eth.get_transaction_receipt(  # pylint: disable=protected-access
                tx_hash
            )
        except Exception as e:  # pylint: disable=broad-except
            last_exception = e
            retry_count += 1
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                # Get the RPC endpoint for error message
                rpc_endpoint = getattr(
                    ledger_api._api.provider,  # pylint: disable=protected-access
                    "endpoint_uri",
                    "unknown",
                )
                raise TimeoutError(
                    f"Timeout ({timeout}s) exceeded while waiting for transaction receipt via HTTP RPC. "
                    f"Transaction hash: {tx_hash}. "
                    f"RPC endpoint: {rpc_endpoint}. "
                    f"Retries attempted: {retry_count}. "
                    f"Last error: {repr(last_exception)}"
                ) from last_exception
            time.sleep(1)


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
