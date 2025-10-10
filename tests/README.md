# Locust Stress Test

This test simulates load on the mech marketplace using [Locust](https://locust.io/).

## Setup

1. Create a file named `ethereum_private_key.txt` under the `tests/` folder.  
   This file should contain your private key used for signing requests.

2. Run Locust with the following command:

```bash
locust -f tests/locustfile.py
````

You should see output similar to:

```text
Starting web interface at http://0.0.0.0:8089, press enter to open your default browser.
```

Then open your browser and start the test via the Locust web UI.

---

## Running Locust Headless (No Web Interface)

To run Locust entirely from the terminal, use:

```bash
locust -f tests/locustfile.py --headless -u 1 -r 1 -t 25m
```

**Flags explained:**

* `-f tests/locustfile.py` → Path to the Locust file.
* `--headless` → Disables the web UI and runs in CLI mode.
* `-u 1` → Number of users (clients).
* `-r 1` → Spawn rate (users per second).
* `-t 25m` → Total run time (25 minutes).

---

## Optional but Useful Flags

* `--csv results` → Export results to CSV files (`results_stats.csv`, etc.).
* `--only-summary` → Print only the summary table at the end.
* `--logfile locust.log` → Log output to a file.
* `--loglevel INFO` → Set logging verbosity (`DEBUG`, `INFO`, `ERROR`, etc.).

---

### 💡 Tip

For CI pipelines or remote servers, use:

```bash
locust -f tests/locustfile.py --headless --only-summary
```

This keeps logs clean and prevents the process from waiting for UI interaction.

