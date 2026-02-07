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

"""NVM subscription management for mech marketplace.

DEPRECATED: This module is deprecated and will be removed in a future release.
Use mech_client.services.subscription_service.SubscriptionService instead.
"""

import warnings
from pathlib import Path
from typing import Dict, Optional

from aea_ledger_ethereum import EthereumApi, EthereumCrypto
from safe_eth.eth import EthereumClient

from mech_client.infrastructure.config import MechConfig
from mech_client.services.subscription_service import SubscriptionService


# Reference new infrastructure location for env files
BASE_ENV_PATH = Path(__file__).parent.parent / "infrastructure" / "nvm" / "resources" / "envs"

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

    DEPRECATED: This function is deprecated and will be removed in a future release.
    Use mech_client.services.subscription_service.SubscriptionService instead.

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
    # Emit deprecation warning
    warnings.warn(
        "nvm_subscribe_main() is deprecated and will be removed in a future release. "
        "Use mech_client.services.subscription_service.SubscriptionService instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    # Validate chain support
    if chain_config not in CHAIN_TO_ENVS:
        print(f"{chain_config} network not supported")
        raise ValueError(f"Network {chain_config} not supported for NVM subscriptions")

    # Validate private key file exists
    if not Path(private_key_path).exists():
        raise FileNotFoundError(
            f"Private key file `{private_key_path}` does not exist!"
        )

    # Create crypto object
    crypto = EthereumCrypto(
        private_key_path=private_key_path,
        password=private_key_password,
    )

    # Load configuration
    mech_config = MechConfig.from_chain(chain_config)

    # Create ledger API
    ledger_api = EthereumApi(**mech_config.ledger.dict())

    # Create Ethereum client for agent mode
    ethereum_client = None
    if agent_mode:
        ethereum_client = EthereumClient(mech_config.rpc_url)

    # Display sender address
    print(f"Sender address: {crypto.address}")

    # Create subscription service
    service = SubscriptionService(
        chain_config=chain_config,
        crypto=crypto,
        ledger_api=ledger_api,
        agent_mode=agent_mode,
        ethereum_client=ethereum_client,
        safe_address=safe_address,
    )

    # Execute subscription purchase
    result = service.purchase_subscription()

    # Display result
    print("Subscription created successfully")
    print(f"Agreement ID: {result['agreement_id']}")
    print(f"Agreement TX: {result['agreement_tx_hash']}")
    print(f"Fulfillment TX: {result['fulfillment_tx_hash']}")


__all__ = ["nvm_subscribe_main", "CHAIN_TO_ENVS"]
