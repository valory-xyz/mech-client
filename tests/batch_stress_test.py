import time
import datetime
import random

from mech_client.marketplace_interact import marketplace_interact

# Constants
PRIORITY_MECH_ADDRESS = "0x601024E27f1C67B28209E24272CED8A31fc8151F"
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
LOG_FILE = "latency_log.txt"

latencies = []

with open(LOG_FILE, "w") as log:
    log.write("Request Log - UTC Timestamps and Latencies for OFF-CHAIN interactions\n")
    log.write("===========================================\n\n")

    for i in range(800):
        start_time = time.time()
        utc_timestamp = datetime.datetime.utcnow().isoformat() + "Z"
        prompts = []
        for prompt in range(1, 60):
            p = random.choice(PROMPT_LIST)
            prompts.append(p)

        tools = [TOOL_NAME] * len(prompts)
        print(len(tools), tools)
        result = marketplace_interact(
            prompts=tuple(prompts),
            priority_mech=PRIORITY_MECH_ADDRESS,
            use_offchain=USE_OFFCHAIN,
            tools=tuple(tools),
            chain_config=CHAIN_CONFIG,
        )

        end_time = time.time()
        latency = (end_time - start_time)* 1000
        latencies.append(latency)

        log_line = f"Request {i + 1}: {utc_timestamp} | Latency: {latency:.3f} ms \n"
        print(log_line.strip())
        log.write(log_line)

    average_latency = sum(latencies) / len(latencies)
    summary_line = f"\nAverage latency over 100 requests: {average_latency:.3f} ms \n"
    print(summary_line.strip())
    log.write(summary_line)
