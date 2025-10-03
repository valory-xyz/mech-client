import time
import random
from locust import User, task, between, events, LoadTestShape
from locust.exception import StopUser
from itertools import cycle

from mech_client.cli import interact  # wherever your interact lives
from mech_client.interact import ConfirmationType
from mech_client.marketplace_interact import marketplace_interact

import datetime
import random

# PRIORITY_MECH_ADDRESS = "0x601024E27f1C67B28209E24272CED8A31fc8151F"
# 0x0649F2aeE1b2a6fdcf00B308B58A795D7460c430
# PRIORITY_MECH_ADDRESS = "0xFaCaa9dD513Af6b5A79B73353dafF041925d0101"
PRIORITY_MECH_ADDRESS = "0xB3C6319962484602b00d5587e965946890b82101"
TOOL_NAME = "superforcaster"
CHAIN_CONFIG = "gnosis"
USE_OFFCHAIN = False
LOG_FILE = "latency_log.txt"


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

# Example: generate 50,000 prompts
PROMPT_LIST = make_prompts(50000)

pkeys = [
    "./tests/ethereum_private_key.txt",
    # "./tests/stress_test1_key.txt",
    # "./tests/stress_test2_key.txt",
    # "./tests/stress_test3_key.txt"]
]
key_cycle = cycle(pkeys)

class MechUserSmoke(User):
    wait_time = between(1.5, 5)

    def on_start(self):
        # each virtual user grabs its own key from the cycle
        self.private_key = next(key_cycle)


    @task
    def call_mech(self):
        prompt = random.choice(PROMPT_LIST)
        start = time.monotonic()
        try:
            result = marketplace_interact(
                prompts=(prompt,),
                priority_mech=PRIORITY_MECH_ADDRESS,
                tools=(TOOL_NAME,),
                chain_config="gnosis",
                private_key_path=self.private_key,
                confirmation_type=ConfirmationType.ON_CHAIN
            )
            duration_ms = int((time.monotonic() - start) * 1000)
            # report success to Locust
            events.request.fire(
                request_type="mech",
                name="call_mech",
                response_time=duration_ms,
                response_length=len(str(result) or 0),
                exception=None,
            )
        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            # report failure to Locust
            events.request.fire(
                request_type="mech",
                name="call_mech",
                response_time=duration_ms,
                response_length=0,
                exception=e,
            )

TARGET_REQUESTS = 50000
request_count = 0

@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    global request_count
    request_count += 1
    if request_count >= TARGET_REQUESTS:
        # this will cleanly shut down the test
        events.quitting.fire()