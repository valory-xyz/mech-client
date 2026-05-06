# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2025 Valory AG
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

"""Transaction receipt waiting and event polling utilities."""

import time
from typing import Dict, List, Optional

from aea_ledger_ethereum import EthereumApi
from mech_client.infrastructure.config.constants import TRANSACTION_RECEIPT_TIMEOUT
from web3.contract import Contract as Web3Contract


def wait_for_receipt(
    tx_hash: str,
    ledger_api: EthereumApi,
    timeout: float = TRANSACTION_RECEIPT_TIMEOUT,
) -> Dict:
    """
    Wait for transaction receipt via HTTP RPC endpoint with polling.

    Polls the RPC endpoint for transaction receipt with exponential backoff.
    Raises TimeoutError if timeout is exceeded.

    :param tx_hash: The transaction hash
    :param ledger_api: The Ethereum API used for interacting with the ledger
    :param timeout: Maximum time to wait for receipt in seconds (default: 300)
    :return: The receipt of the transaction
    :raises TimeoutError: If timeout is exceeded while waiting for receipt
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


def watch_for_marketplace_request_ids(
    marketplace_contract: Web3Contract,
    ledger_api: EthereumApi,
    tx_hash: str,
    tx_receipt: Optional[Dict] = None,
) -> List[str]:
    """
    Extract request IDs from marketplace request transaction logs.

    Parses MarketplaceRequest event logs to extract request IDs.
    If tx_receipt is not provided, fetches it via wait_for_receipt and
    propagates ``TimeoutError`` from there if the receipt never arrives.

    :param marketplace_contract: The marketplace contract instance
    :param ledger_api: The Ethereum API used for interacting with the ledger
    :param tx_hash: Transaction hash to wait for
    :param tx_receipt: Pre-fetched transaction receipt (avoids duplicate RPC call)
    :return: List of request IDs as hex strings (without 0x prefix)
    """
    if tx_receipt is None:
        tx_receipt = wait_for_receipt(tx_hash=tx_hash, ledger_api=ledger_api)

    rich_logs = marketplace_contract.events.MarketplaceRequest().process_receipt(
        tx_receipt
    )
    if len(rich_logs) == 0:
        raise ValueError(
            f"No MarketplaceRequest events found in transaction {tx_hash}. "
            f"The transaction may have reverted."
        )

    # Collect request IDs from ALL log entries (batch txs may emit multiple events).
    # bytes.hex() returns hex without 0x prefix, which is the canonical format
    # used by the delivery watchers. The 0x prefix stripping in watchers is
    # defensive for external callers passing prefixed IDs.
    request_ids_hex: List[str] = []
    for log_entry in rich_logs:
        for request_id in log_entry["args"]["requestIds"]:
            request_ids_hex.append(request_id.hex())
    return request_ids_hex
