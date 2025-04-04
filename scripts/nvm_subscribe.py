import os
import sys
from dotenv import load_dotenv
from typing import Optional, Dict
from pathlib import Path
from mech_client.interact import PRIVATE_KEY_FILE_PATH
from web3 import Web3
from scripts.nvm_subscription.manager import NVMSubscriptionManager

BASE_ENV_PATH = Path(__file__).parent / "nvm_subscription" / "envs"

CHAIN_TO_ENVS: Dict[str, Path] = {
    "gnosis": BASE_ENV_PATH / "gnosis.env",
    "base": BASE_ENV_PATH / "base.env",
}


def main(
    private_key_path: str,
    chain_config: str,
) -> None:

    chain_env = CHAIN_TO_ENVS.get(chain_config)
    if chain_env:
        load_dotenv(chain_env)
    else:
        print(f"{chain_config} network not supported")
        sys.exit(1)

    private_key_path = private_key_path or PRIVATE_KEY_FILE_PATH
    if not Path(private_key_path).exists():
        raise FileNotFoundError(
            f"Private key file `{private_key_path}` does not exist!"
        )

    with open(private_key_path, "r") as file:
        content = file.read()

    WALLET_PVT_KEY = content
    PLAN_DID = os.environ["PLAN_DID"]
    NETWORK = os.environ["NETWORK_NAME"]
    CHAIN_ID = int(os.environ["CHAIN_ID"])
    SENDER = Web3().eth.account.from_key(WALLET_PVT_KEY).address

    print(f"Sender address: {SENDER}")

    manager = NVMSubscriptionManager(NETWORK, WALLET_PVT_KEY)
    tx_receipt = manager.create_subscription(PLAN_DID, WALLET_PVT_KEY, CHAIN_ID)

    print("Subscription created successfully")
    print(tx_receipt)
