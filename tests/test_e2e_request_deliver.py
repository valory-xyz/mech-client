import json
import os
import re
import subprocess
import sys
from pathlib import Path
import requests


CLIENT_DIR = Path(__file__).resolve().parents[1]


def _run(cmd: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(CLIENT_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=timeout,
        check=False,
    )


def _assert_ok(proc: subprocess.CompletedProcess, context: str):
    if proc.returncode != 0:
        raise AssertionError(
            f"{context} failed with exit code {proc.returncode}.\nOutput:\n{proc.stdout}"
        )


def test_python_client_request_and_optional_deliver():
    # Required files
    eth_key = CLIENT_DIR / "ethereum_private_key.txt"
    mech_key = CLIENT_DIR / "mech_private_key.txt"
    assert eth_key.exists(), f"Missing {eth_key}"
    assert mech_key.exists(), f"Missing {mech_key}"

    # Test configuration from environment variables
    priority_mech = os.environ["TEST_PRIORITY_MECH"]
    safe_address = os.environ["TEST_SAFE_ADDRESS"]

    # Request (post-only)
    req_cmd = [
        sys.executable,
        "-m",
        "mech_client.cli",
        "interact",
        "--prompts",
        "e2e test (python)",
        "--priority-mech",
        priority_mech,
        "--tools",
        "openai-gpt-3.5-turbo",
        "--chain-config",
        "base",
        "--post-only",
        "--key",
        "ethereum_private_key.txt",
    ]
    proc_req = _run(req_cmd)
    _assert_ok(proc_req, "python request")

    # Validate result.json
    result_path = CLIENT_DIR / "result.json"
    assert result_path.exists(), "result.json not created"
    data = json.loads(result_path.read_text())
    assert str(data.get("requestId", "")).strip() != ""

    # Extract request IPFS URL from logs and verify content
    m = re.search(r"Prompt uploaded:\s*(https://gateway\.autonolas\.tech/ipfs/\S+)", proc_req.stdout)
    assert m is not None, "Did not find request IPFS URL in output"
    request_ipfs_url = m.group(1)
    resp = requests.get(request_ipfs_url, timeout=60)
    assert resp.status_code == 200, f"Request IPFS fetch failed: {resp.status_code}"
    ipfs_json = resp.json()
    assert ipfs_json.get("prompt") == "e2e test (python)"
    assert ipfs_json.get("tool") == "openai-gpt-3.5-turbo"

    if os.getenv("RUN_ONCHAIN_E2E") == "1":
        # Prepare deliver payload
        result_path.write_text(
            json.dumps(
                {
                    "requestId": str(data["requestId"]),
                    "result": "test delivered (python)",
                    "metadata": {"tool": "openai-gpt-3.5-turbo"},
                }
            )
        )

        del_cmd = [
            sys.executable,
            "-m",
            "mech_client.cli",
            "deliver",
            "--request-id",
            str(data["requestId"]),
            "--result-file",
            "result.json",
            "--target-mech",
            priority_mech,
            "--multisig",
            safe_address,
            "--key",
            "mech_private_key.txt",
            "--chain-config",
            "base",
        ]
        proc_del = _run(del_cmd, timeout=240)
        _assert_ok(proc_del, "python deliver")
        assert "Transaction Hash:" in proc_del.stdout or "tx_hash" in proc_del.stdout

        # Parse JSON output from deliver CLI to extract CID
        deliver_out = proc_del.stdout.strip()
        try:
            deliver_json = json.loads(deliver_out)
            cid = deliver_json.get("cid")
        except json.JSONDecodeError:
            cid = None
        assert cid, "Delivery output missing CID"

        # Verify deliver content on IPFS resolves and matches result.json content
        deliver_url = f"https://gateway.autonolas.tech/ipfs/{cid}/{data['requestId']}"
        deliver_resp = requests.get(deliver_url, timeout=60)
        assert deliver_resp.status_code == 200, f"Deliver IPFS fetch failed: {deliver_resp.status_code}"
        delivered = deliver_resp.json()
        expected = json.loads((CLIENT_DIR / "result.json").read_text())
        assert delivered == expected


