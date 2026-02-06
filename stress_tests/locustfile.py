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

import os
import time
import queue
from dataclasses import asdict
import random
import json

from gevent.pool import Pool
from itertools import cycle

from locust import User, task, between, events
import gevent

from mech_client.interact import get_mech_config
from aea_ledger_ethereum import EthereumApi, EthereumCrypto
from web3.contract import Contract as Web3Contract

from mech_client.marketplace_interact import (
    fetch_mech_deliver_event_signature,
    get_contract,
    MechMarketplaceRequestConfig,
    MARKETPLACE_ABI_PATH,
    ABI_DIR_PATH,
    CHAIN_TO_DEFAULT_MECH_MARKETPLACE_REQUEST_CONFIG
)
from stress_tests.helpers.marketplace_helpers import send_marketplace_request_nonblocking, delivery_consumer_loop_status_only
from stress_tests.helpers.nonce_manager import MapNonceAllocator, NonceAllocator
from stress_tests.helpers.query_generation import make_prompts

# -------------------- TEST PARAMS --------------------
PRIORITY_MECH_ADDRESS = os.environ.get("PRIORITY_MECH", "0x601024E27f1C67B28209E24272CED8A31fc8151F")
CHAIN_CONFIG = os.environ.get("CHAIN_CONFIG", "gnosis")
TOOL_NAME = os.environ.get("TOOL_NAME", "superforcaster")

TARGET_SUBMISSIONS = int(os.environ.get("TARGET_SUBMISSIONS", "25000"))
TARGET_COMPLETIONS = int(os.environ.get("TARGET_COMPLETIONS", "25000"))
WORKER_POOL_SIZE = int(os.environ.get("WORKER_POOL_SIZE", "200"))

# rotate across multiple private keys to avoid per-account pending limits
PKEYS = [p for p in os.environ.get("PRIVATE_KEYS", "./tests/ethereum_private_key.txt").split(",")]
KEY_CYCLE = cycle(PKEYS)


PROMPTS = make_prompts(25_000)

# -------------------- METRICS STATE --------------------
pending_q: "queue.Queue[tuple[str,int,float]]" = queue.Queue()  # (request_id_hex, from_block, t0)
sent_at = {}                # request_id_hex -> monotonic send time
sent_count = 0
done_count = 0
consumer_started = False

# cap in-flight txs
worker_pool = Pool(size=WORKER_POOL_SIZE)

# -------------------- LOCUST EVENT --------------------

@events.init.add_listener
def _install_sigint_handler(environment, **kwargs):
    import signal, gevent
    def _sigint_handler(sig, frame):
        print("Caught SIGINT, quitting runner gracefully...")
        if environment.runner:
            environment.runner.quit()     # graceful: triggers test_stop and UI refresh loop
            gevent.sleep(2.0)            # let last stats push reach the web UI
    signal.signal(signal.SIGINT, _sigint_handler)


# -------------------- LOCUST USER --------------------
class MechUser(User):
    wait_time = between(0.1, 0.2)

    def __init__(self, environment):
        super().__init__(environment)
        self.mech_config = None
        self.ledger_api = None
        self.crypto = None
        self.marketplace = None
        self.mapnonce_alloc = None
        self.nonce_alloc = None
        self.deliver_sig = None
        self.req_cfg = None

    def on_start(self):
        global consumer_started
        # --- chain + contracts ---
        self.mech_config = get_mech_config(CHAIN_CONFIG)
        ledger_cfg = self.mech_config.ledger_config
        self.ledger_api = EthereumApi(**asdict(ledger_cfg))
        self.crypto = EthereumCrypto(private_key_path=next(KEY_CYCLE))

        # marketplace contract
        with open(MARKETPLACE_ABI_PATH, "r", encoding="utf-8") as _:
            pass

        self.marketplace: Web3Contract = get_contract(
            contract_address=self.mech_config.mech_marketplace_contract,
            abi=self._load_abi(ABI_DIR_PATH / "MechMarketplace.json"),
            ledger_api=self.ledger_api,
        )

        self.mapnonce_alloc = MapNonceAllocator(self.marketplace, self.crypto.address)

        # mech deliver signature (for consumer)
        self.deliver_sig = fetch_mech_deliver_event_signature(
            self.ledger_api, PRIORITY_MECH_ADDRESS
        )

        # prepare request config (timeout/payment data defaults)
        chain_id = ledger_cfg.chain_id
        cfg_values = CHAIN_TO_DEFAULT_MECH_MARKETPLACE_REQUEST_CONFIG[chain_id].copy()
        cfg_values.update({
            "priority_mech_address": PRIORITY_MECH_ADDRESS,
            "mech_marketplace_contract": self.mech_config.mech_marketplace_contract,
        })
        self.req_cfg = MechMarketplaceRequestConfig(
            **{k: v for k, v in cfg_values.items()}
        )

        # nonce allocator per sender
        self.nonce_alloc = NonceAllocator(self.ledger_api.api, self.crypto.address)

        # start one consumer for the whole test
        if not consumer_started:
            consumer_started = True
            gevent.spawn(self._start_consumer)

    def _load_abi(self, path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _start_consumer(self):

        def _emit(name: str, rid_hex: str, ms: int, exc=None):
            events.request.fire(
                request_type="mech",
                name=name,  # "delivered" | "timeout" | "stepped_in"
                response_time=ms,
                response_length=0,
                exception=exc,
            )
            self._bump_done()

        gevent.spawn(
            delivery_consumer_loop_status_only,
            pending=pending_q,
            marketplace_contract=self.marketplace,
            priority_mech_address=PRIORITY_MECH_ADDRESS,
            on_delivered=lambda rid, ms: _emit("delivered", rid, ms, None),
            on_timeout=lambda rid, ms: _emit("timeout", rid, ms, None),
            on_stepped_in=lambda rid, ms: _emit("stepped_in", rid, ms, None),
            poll_interval=1.0,
            max_batch=500,
            response_timeout_s=float(self.req_cfg.response_timeout),  # <<< here
        )

    def _bump_done(self):
        global done_count
        done_count += 1
        if done_count >= TARGET_COMPLETIONS:
            env = events.locust_environment  # available in listeners; or pass environment around
            if env and env.runner:
                env.runner.quit()  # graceful stop -> UI gets final snapshot
            gevent.sleep(2.0)  # give UI time to pull latest stats

    @task
    def submit(self):
        """
        Producer task: builds & submits a tx, enqueues request IDs immediately,
        and fires a 'submitted' metric. Non-blocking.
        """
        global sent_count
        if sent_count >= TARGET_SUBMISSIONS:
            return

        prompt = random.choice(PROMPTS)
        tools = (os.environ.get("TOOL_NAME", "superforcaster"),)
        prompts = (prompt,)

        # For single-request txs, batch_size = 1
        batch_size = 1

        base_eth_nonce = self.nonce_alloc.allocate_batch(batch_size)
        base_map_nonce = self.mapnonce_alloc.allocate_batch(batch_size)

        tx_hash, request_ids, from_block = _send_nonblocking_with_explicit_nonce(
            crypto=self.crypto,
            ledger_api=self.ledger_api,
            marketplace_contract=self.marketplace,
            gas_limit=self.mech_config.gas_limit,
            prompts=prompts,
            tools=tools,
            method_args_data=self.req_cfg,
            extra_attributes=None,
            base_nonce=base_eth_nonce,
            contract_nonce=base_map_nonce,
        )

        t0 = time.monotonic()
        for rid in request_ids:
            sent_at[rid] = t0
            pending_q.put((rid, from_block, t0))

        events.request.fire(
            request_type="mech",
            name="submitted",
            response_time=0,
            response_length=len(request_ids),
            exception=None,
        )

        sent_count += len(request_ids)
        if sent_count >= TARGET_SUBMISSIONS:
            # Let the consumer drain; completion will trigger quit
            pass


# ------------- small adapter to enforce explicit nonce -------------
def _send_nonblocking_with_explicit_nonce(
    crypto,
    ledger_api,
    marketplace_contract,
    gas_limit,
    prompts,
    tools,
    method_args_data,
    extra_attributes,
    base_nonce,
    contract_nonce,
):
    """
    Wrapper around send_marketplace_request_nonblocking that injects 'nonce'
    into tx_args. For a single-request tx, base_nonce is the nonce.
    """
    tx_hash, request_ids, from_block = send_marketplace_request_nonblocking(
        crypto=crypto,
        ledger_api=ledger_api,
        marketplace_contract=marketplace_contract,
        gas_limit=gas_limit,
        prompts=prompts,
        tools=tools,
        method_args_data=method_args_data,
        extra_attributes=extra_attributes,
        tx_nonce=base_nonce,
        contract_nonce = contract_nonce,
    )

    return tx_hash, request_ids, from_block
