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

import queue
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple, cast

from aea_ledger_ethereum import EthereumApi, EthereumCrypto
from eth_utils import to_checksum_address
from web3.contract import Contract as Web3Contract
from web3.exceptions import ABIFunctionNotFound, TimeExhausted

from mech_client.interact import (
    MAX_RETRIES,
    MechMarketplaceRequestConfig,
    TIMEOUT,
    WAIT_SLEEP,
)
from mech_client.marketplace_interact import fetch_mech_info
from mech_client.prompt_to_ipfs import push_metadata_to_ipfs

WAITING_STATUS = 1
TIMED_OUT_STATUS = 2
DELIVERED_STATUS = 3


def _pad32(hex_no_0x: str) -> bytes:
    """Left-pad hex (no 0x) to 32 bytes."""
    hx = hex_no_0x.lower().removeprefix("0x")
    return bytes.fromhex(hx.zfill(64))


def get_request_status(marketplace_contract: Web3Contract, rid_hex: str) -> int:
    """Call MechMarketplace.getRequestStatus(bytes32)."""
    return marketplace_contract.functions.getRequestStatus(_pad32(rid_hex)).call()


def get_delivery_mech(
    marketplace_contract: Web3Contract, rid_hex: str
) -> Optional[str]:
    """Get the delivery mech of the request."""
    info = marketplace_contract.functions.mapRequestIdInfos(_pad32(rid_hex)).call()
    delivery_mech = info[1] if len(info) > 1 else None
    if delivery_mech:
        # Always normalize for robust comparisons
        return (
            delivery_mech if delivery_mech.startswith("0x") else ("0x" + delivery_mech)
        )
    return None

def send_marketplace_request_nonblocking(  # pylint: disable=too-many-arguments, too-many-locals, too-many-statements, too-many-return-statements
    crypto: EthereumCrypto,
    ledger_api: EthereumApi,
    marketplace_contract: Web3Contract,
    gas_limit: int,
    prompts: tuple,
    tools: tuple,
    method_args_data: MechMarketplaceRequestConfig,
    extra_attributes: Optional[Dict[str, Any]] = None,
    retries: Optional[int] = None,
    timeout: Optional[float] = None,
    sleep: Optional[float] = None,
    tx_nonce: Optional[int] = None,
    contract_nonce: int = 0,
    max_priority_fee_wei: Optional[int] = None,
    max_fee_wei: Optional[int] = None,
) -> Tuple[str, List[str], int]:
    """Build/sign/send a request *without* waiting for receipt or delivery."""
    # --- build request data(s) exactly like send_marketplace_request ---
    num_requests = len(prompts)
    priority_mech_address = cast(str, method_args_data.priority_mech_address)
    (
        payment_type,
        _,
        max_delivery_rate,
        _,
    ) = fetch_mech_info(ledger_api, marketplace_contract, priority_mech_address)
    method_args_data.delivery_rate = max_delivery_rate
    method_args_data.payment_type = payment_type

    price = max_delivery_rate * num_requests
    method_args = {
        "maxDeliveryRate": method_args_data.delivery_rate,
        "paymentType": "0x" + cast(str, method_args_data.payment_type),
        "priorityMech": to_checksum_address(method_args_data.priority_mech_address),
        "responseTimeout": method_args_data.response_timeout,
        "paymentData": method_args_data.payment_data,
    }

    request_datas = []
    if num_requests == 1:
        v1_hash_trunc, v1_hash = push_metadata_to_ipfs(
            prompts[0], tools[0], extra_attributes
        )
        print(f"  - Prompt uploaded: https://gateway.autonolas.tech/ipfs/{v1_hash}")
        method_name = "request"
        method_args["requestData"] = v1_hash_trunc
        request_datas = [v1_hash_trunc]
    else:
        method_name = "requestBatch"
        for prompt, tool in zip(prompts, tools):
            v1_hash_trunc, v1_hash = push_metadata_to_ipfs(
                prompt, tool, extra_attributes
            )
            print(f"  - Prompt uploaded: https://gateway.autonolas.tech/ipfs/{v1_hash}")
            request_datas.append(v1_hash_trunc)
        method_args["requestDatas"] = request_datas

    # --- precompute request_id(s) using current nonce (no receipt needed) ---
    request_ids: List[str] = []
    for i, req_data in enumerate(request_datas):
        rid_bytes = marketplace_contract.functions.getRequestId(
            method_args["priorityMech"],
            crypto.address,
            req_data,
            method_args["maxDeliveryRate"],
            method_args["paymentType"],
            contract_nonce + i,
        ).call()
        request_ids.append(rid_bytes.hex())
    print(f"tx_nonce={tx_nonce} map_nonce_base={contract_nonce} rids={request_ids[:2]}")
    # choose from_block BEFORE sending (so we don't miss Deliver logs)
    w3 = ledger_api.api
    from_block = w3.eth.block_number

    # --- explicit tx NONCE from caller (required) ---
    if tx_nonce is None:
        raise RuntimeError("tx_nonce must be provided by the caller")

    # --- EIP-1559 fees (suggest if not provided) ---
    pending_block = w3.eth.get_block("pending")
    base_fee = (
        pending_block.get("baseFeePerGas")
        or w3.eth.get_block("latest")["baseFeePerGas"]
    )
    priority = max_priority_fee_wei or int(w3.eth.max_priority_fee)
    max_fee = max_fee_wei or (base_fee * 2 + priority)

    tx_args = {
        "sender_address": crypto.address,
        "value": price,
        "gas": gas_limit,
        "nonce": tx_nonce,
        "maxFeePerGas": int(max_fee),
        "maxPriorityFeePerGas": int(priority),
    }

    def _bump(x: int) -> int:
        return int(x * 1.125) + 1

    tries = 0
    retries = retries or MAX_RETRIES
    timeout = timeout or TIMEOUT
    sleep = sleep or WAIT_SLEEP
    deadline = datetime.now().timestamp() + timeout

    while tries < retries and datetime.now().timestamp() < deadline:
        tries += 1
        try:
            raw_tx = ledger_api.build_transaction(
                contract_instance=marketplace_contract,
                method_name=method_name,
                method_args=method_args,
                tx_args=tx_args,
                raise_on_try=True,
            )
            signed = crypto.sign_transaction(raw_tx)
            tx_hash = ledger_api.send_signed_transaction(signed, raise_on_try=True)
            return tx_hash, request_ids, from_block
        except TimeExhausted as e:  # type: ignore
            # keep SAME nonce; bump fees for replacement
            tx_args["maxFeePerGas"] = _bump(tx_args["maxFeePerGas"])
            tx_args["maxPriorityFeePerGas"] = _bump(tx_args["maxPriorityFeePerGas"])
            print(
                f"Error while sending tx (nonce {tx_nonce}): {e}; bumping fees and retrying in {sleep}s"
            )
            time.sleep(sleep)

    raise RuntimeError("Failed to send marketplace request after retries")


def delivery_consumer_loop_status_only(  # pylint: disable=too-many-arguments, too-many-locals, too-many-statements, too-many-return-statements
    pending: "queue.Queue[tuple[str,int,float]]",  # queue of (rid_hex, from_block, t0)
    marketplace_contract: Web3Contract,
    priority_mech_address: str,
    on_delivered: Callable,
    on_timeout: Callable,
    on_stepped_in: Callable,
    poll_interval: float = 1.0,
    max_batch: int = 500,
    response_timeout_s: Optional[float] = None,
) -> None:
    """Check for the status of a delivery in the marketplace."""

    backlog: dict[str, float] = {}  # rid_hex -> t0 (first-seen time)
    seen: set[str] = set()  # rids we've emitted a *final* outcome for
    timed_out: set[str] = set()  # rids that have hit TIMED_OUT at least once

    def _is_zero_addr(addr: str | None) -> bool:
        return (not addr) or (
            addr.lower() == "0x0000000000000000000000000000000000000000"
        )

    while True:
        # Drain producer queue
        drained = 0
        while drained < max_batch:
            try:
                rid, _fb, t0 = pending.get_nowait()
                if rid not in seen:
                    # keep earliest t0
                    backlog[rid] = (
                        min(backlog.get(rid, t0), t0) if rid in backlog else t0
                    )
                drained += 1
            except queue.Empty:
                break

        if not backlog:
            time.sleep(poll_interval)
            continue
        now = time.monotonic()
        # Poll a slice to avoid long loops
        for rid in list(backlog.keys())[:max_batch]:
            if rid in seen:
                backlog.pop(rid, None)
                continue

            try:
                st = get_request_status(marketplace_contract, rid)
            except (TimeExhausted, ABIFunctionNotFound):  # type: ignore
                # RPC hiccup; try again next tick
                continue
            t0 = backlog.get(rid, now)
            elapsed_ms = int((now - t0) * 1000)
            if response_timeout_s is not None and st == WAITING_STATUS:
                if (rid not in timed_out) and ((now - t0) >= response_timeout_s):
                    timed_out.add(rid)
                    on_timeout(rid, elapsed_ms)
                # keep in backlog and continue polling
                continue
            print(f"{rid=}:{st=}")
            if st == TIMED_OUT_STATUS:
                # First time we see timeout -> emit timeout now, but KEEP in backlog
                if rid not in timed_out:
                    t0 = backlog.get(rid, time.monotonic())
                    elapsed_ms = int((time.monotonic() - t0) * 1000)
                    timed_out.add(rid)
                    on_timeout(rid, elapsed_ms)
                # do NOT mark as seen and do NOT pop from backlog
                continue  # optional; just skip further handling this tick

            if st == DELIVERED_STATUS:
                # Finalize this RID (delivered or stepped_in)
                t0 = backlog.pop(rid, time.monotonic())
                elapsed_ms = int((time.monotonic() - t0) * 1000)
                seen.add(rid)

                mech = get_delivery_mech(marketplace_contract, rid)

                if (not _is_zero_addr(mech)) and (
                    mech.lower() != priority_mech_address.lower()  # type: ignore
                ):
                    on_stepped_in(rid, elapsed_ms)
                else:
                    on_delivered(rid, elapsed_ms)

            # WAITING_STATUS (or other) -> keep in backlog

        time.sleep(poll_interval)
