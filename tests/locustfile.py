import datetime
import os
import time
import queue
from dataclasses import asdict
import random

import gevent
from gevent.pool import Pool
from itertools import cycle

from locust import User, task, between, events
import signal, gevent
from gevent import event as gevent_event

# === bring your functions/types into scope ===
# Assuming this locustfile lives next to your interact module; adjust imports as needed.
from mech_client.interact import get_mech_config
from aea_ledger_ethereum import EthereumApi, EthereumCrypto
from web3.contract import Contract as Web3Contract

# These are the helpers you shared/added
from mech_client.marketplace_interact import (  # <-- change to the actual module path
    send_marketplace_request_nonblocking,
    delivery_consumer_loop_status_only,
    fetch_mech_deliver_event_signature,
    get_contract,
    MechMarketplaceRequestConfig,
    MARKETPLACE_ABI_PATH,
    ABI_DIR_PATH,
    CHAIN_TO_DEFAULT_MECH_MARKETPLACE_REQUEST_CONFIG, PaymentType,
)

# -------------------- TEST PARAMS --------------------
PRIORITY_MECH_ADDRESS = os.environ.get("PRIORITY_MECH", "0x601024E27f1C67B28209E24272CED8A31fc8151F")
# PRIORITY_MECH_ADDRESS = os.environ.get("PRIORITY_MECH", "0x0649F2aeE1b2a6fdcf00B308B58A795D7460c430")
# 0x0649F2aeE1b2a6fdcf00B308B58A795D7460c430
CHAIN_CONFIG = os.environ.get("CHAIN_CONFIG", "gnosis")
TOOL_NAME = os.environ.get("TOOL_NAME", "superforcaster")

TARGET_SUBMISSIONS = int(os.environ.get("TARGET_SUBMISSIONS", "25000"))
TARGET_COMPLETIONS = int(os.environ.get("TARGET_COMPLETIONS", "25000"))
WORKER_POOL_SIZE = int(os.environ.get("WORKER_POOL_SIZE", "200"))

# rotate across multiple private keys to avoid per-account pending limits
PKEYS = [p for p in os.environ.get("PRIVATE_KEYS", "./tests/ethereum_private_key.txt").split(",")]
KEY_CYCLE = cycle(PKEYS)

# Prompt source: keep it simple here; you can import your generator
ASSETS = [
    "S&P 500", "Bitcoin", "Ethereum", "Gold", "Silver",
    "Oil", "NASDAQ 100", "Dow Jones", "EUR/USD", "GBP/USD",
]
THRESHOLDS = ["4,500", "5,000", "10,000", "50,000", "2,000"]
DURATIONS = [
    "tomorrow", "in 3 days", "next Monday", "by end of the week",
    "by the end of the month",
]
EVENTS = [
    "closes above", "drops below", "volatility exceeds",
    "volume exceeds", "daily range exceeds",
]
TEMPLATES = [
    "What is the probability that {asset} {event} {threshold} {when}?",
    "Estimate the chance that {asset} {event} {threshold} {when}.",
    "What are the odds that {asset} {event} {threshold} {when}?",
    "By what probability will {asset} {event} {threshold} {when}?",
]

def next_n_business_days(start: datetime.date, n: int):
    days = []
    d = start
    while len(days) < n:
        d += datetime.timedelta(days=1)
        if d.weekday() < 5:
            days.append(d.isoformat())
    return days

DATES = next_n_business_days(datetime.date.today(), 100)

def make_prompts(n: int):
    pool = []
    while len(pool) < n:
        asset = random.choice(ASSETS)
        event = random.choice(EVENTS)
        threshold = random.choice(THRESHOLDS)
        when = random.choice(DATES + DURATIONS)
        template = random.choice(TEMPLATES)
        pool.append(template.format(
            asset=asset,
            event=event,
            threshold=threshold,
            when=when,
        ))
    return pool


PROMPTS = make_prompts(25_000)

# -------------------- METRICS STATE --------------------
pending_q: "queue.Queue[tuple[str,int,float]]" = queue.Queue()  # (request_id_hex, from_block, t0)
sent_at = {}                # request_id_hex -> monotonic send time
sent_count = 0
done_count = 0
consumer_started = False

# cap in-flight txs
worker_pool = Pool(size=WORKER_POOL_SIZE)

# -------------------- NONCE MANAGEMENT --------------------
class NonceAllocator:
    """
    Thread/greenlet-safe nonce allocator per account.
    Uses 'pending' count so unmined txs are included.
    """
    def __init__(self, w3, address: str):
        self._w3 = w3
        self._addr = address
        self._lock = gevent.lock.Semaphore()
        self._next = self._w3.eth.get_transaction_count(address, "pending")

    def allocate_batch(self, n: int) -> int:
        """Reserve n sequential nonces, returning the base nonce."""
        with self._lock:
            base = self._next
            self._next += n
            return base

class MapNonceAllocator:
    def __init__(self, marketplace_contract, address: str):
        self._c = marketplace_contract
        self._addr = address
        self._lock = gevent.lock.Semaphore()
        self._next = self._c.functions.mapNonces(address).call()
    def allocate_batch(self, n: int) -> int:
        with self._lock:
            base = self._next
            self._next += n
            return base

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

    def on_start(self):
        global consumer_started
        # --- chain + contracts ---
        self.mech_config = get_mech_config(CHAIN_CONFIG)
        ledger_cfg = self.mech_config.ledger_config
        self.ledger_api = EthereumApi(**asdict(ledger_cfg))
        self.crypto = EthereumCrypto(private_key_path=next(KEY_CYCLE))

        # marketplace contract
        with open(MARKETPLACE_ABI_PATH, "r", encoding="utf-8") as _:
            pass  # not needed if your get_contract loads from your constants

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
        import json
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

        # Build args similar to your send_marketplace_request_nonblocking()
        # We’ll allocate nonces up-front and pass them through tx_args.
        # For single-request txs, batch_size = 1
        batch_size = 1

        base_eth_nonce = self.nonce_alloc.allocate_batch(batch_size)
        base_map_nonce = self.mapnonce_alloc.allocate_batch(batch_size)
        # We reuse your helper, but we need it to accept an explicit nonce.
        # If you've added 'nonce' support inside build_transaction via tx_args,
        # pass it in by monkey-patching tx_args through the helper (see below).
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
    Wrapper around your send_marketplace_request_nonblocking that injects 'nonce'
    into tx_args. For a single-request tx, base_nonce is the nonce.
    If you batch N, use base_nonce..base_nonce+N-1 inside the helper.
    """
    # We’ll reuse your helper but we need to pin nonce(s). Easiest is to copy the
    # last step here: rebuild & sign with explicit tx_args['nonce'].
    # If you modify your helper to accept 'base_nonce', do that instead and remove this wrapper.

    # 1) Precompute request_ids and method_args exactly as your helper does.
    #    To avoid duplication, call your helper up to the point of returning raw tx fields.
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
    # NOTE:
    # If your helper already broadcasted with its own nonce, you should
    # instead *edit the helper* to accept a 'base_nonce' and set:
    #   tx_args = {"sender_address": crypto.address, "value": price, "gas": gas_limit, "nonce": base_nonce}
    # before sending. That is the recommended approach.
    return tx_hash, request_ids, from_block
