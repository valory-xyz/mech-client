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

"""NVM subscription management for mech marketplace."""

import os
import sys
from pathlib import Path
from typing import Dict, Optional

from aea_ledger_ethereum import EthereumCrypto
from dotenv import load_dotenv
from web3 import Web3

from mech_client.nvm_subscription.manager import NVMSubscriptionManager
from mech_client.utils.constants import (
    DEFAULT_PRIVATE_KEY_FILE as PRIVATE_KEY_FILE_PATH,
)


BASE_ENV_PATH = Path(__file__).parent / "envs"

CHAIN_TO_ENVS: Dict[str, Path] = {
    "gnosis": BASE_ENV_PATH / "gnosis.env",
    "base": BASE_ENV_PATH / "base.env",
}


def nvm_subscribe_main(
    agent_mode: bool,
    private_key_path: str,
    private_key_password: Optional[str],
    chain_config: str,
    safe_address: Optional[str] = None,
) -> None:
    """
    Main function for purchasing NVM subscriptions.

    :param agent_mode: Specifies whether agent mode is active or not.
    :type agent_mode: bool
    :param private_key_path: Path to the private key file.
    :type private_key_path: str
    :param private_key_password: Password for encrypted private key.
    :type private_key_password: Optional[str]
    :param chain_config: Chain configuration identifier.
    :type chain_config: str
    :param safe_address: Safe address for agent mode.
    :type safe_address: Optional[str]
    """
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

    crypto = EthereumCrypto(
        private_key_path=private_key_path,
        password=private_key_password,
    )
    wallet_pvt_key = crypto.private_key
    plan_did = os.environ["PLAN_DID"]
    network = os.environ["NETWORK_NAME"]
    chain_id = int(os.environ["CHAIN_ID"])
    # NVM Subscription has to be purchased for the safe and EOA pays for gas
    # so for agent mode, sender has to be safe
    eoa = Web3().eth.account.from_key(wallet_pvt_key).address
    sender = safe_address or eoa

    print(f"Sender address: {sender}")

    manager = NVMSubscriptionManager(network, sender, agent_mode, safe_address)
    tx_receipt = manager.create_subscription(plan_did, wallet_pvt_key, chain_id)

    print("Subscription created successfully")
    print(tx_receipt)


__all__ = ["nvm_subscribe_main", "CHAIN_TO_ENVS", "NVMSubscriptionManager"]
