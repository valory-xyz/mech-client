#!/bin/bash

export MANUAL_GAS_LIMIT=150000
export WEBSOCKET_ENDPOINT=wss://rpc.eu-central-2.gateway.fm/ws/v4/gnosis/non-archival/mainnet
iterations=10

mechx --version

start_time=$(date +%s.%N)

# Execute the command for the specified number of iterations
for ((i=1; i<=$iterations; i++)); do
    echo "- Iteration $i"
    mechx interact "will arsenal win the premier league in 2024" 6 --tool prediction-offline --confirm on-chain

    if [ $? -ne 0 ]; then
        echo "Error: Command execution failed."
        exit 1
    fi

    echo ""
done

end_time=$(date +%s.%N)
elapsed_time=$(echo "$end_time - $start_time" | bc)
seconds_per_iteration=$(echo "$elapsed_time / $iterations" | bc)

echo "Overall execution time for $iterations iterations: $elapsed_time seconds (rate of $seconds_per_iteration seconds/iteration)."
