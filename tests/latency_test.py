import time
import datetime
from mech_client.marketplace_interact import marketplace_interact

# Constants
PRIORITY_MECH_ADDRESS = "0xFaCaa9dD513Af6b5A79B73353dafF041925d0101"
PROMPT_TEXT = "Say Hi"
TOOL_NAME = "openai-gpt-4o-2024-08-06"
CHAIN_CONFIG = "gnosis"
USE_OFFCHAIN = True
LOG_FILE = "latency_log.txt"

latencies = []

with open(LOG_FILE, "w") as log:
    log.write("Request Log - UTC Timestamps and Latencies for OFF-CHAIN interactions\n")
    log.write("===========================================\n\n")

    for i in range(1):
        start_time = time.time()
        utc_timestamp = datetime.datetime.utcnow().isoformat() + "Z"

        result = marketplace_interact(
            prompts=(PROMPT_TEXT,),
            priority_mech=PRIORITY_MECH_ADDRESS,
            use_offchain=USE_OFFCHAIN,
            tools=(TOOL_NAME,),
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
