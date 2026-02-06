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

"""Key management utilities for agent mode."""

import os
from typing import Optional, Tuple

from operate.cli import logger as operate_logger
from operate.services.manage import KeysManager

from mech_client.infrastructure.operate.manager import OperateManager


def fetch_agent_mode_keys(chain_config: str) -> Tuple[str, str, Optional[str]]:
    """
    Fetch agent mode Safe address, keystore path, and password.

    Retrieves the Safe multisig address and private key file path for
    agent mode operations on the specified chain.

    :param chain_config: Chain configuration name (gnosis, base, polygon, optimism)
    :return: Tuple of (safe_address, key_path, password)
    :raises Exception: If no deployed service found for chain
    """
    manager = OperateManager()
    operate = manager.operate

    # Ensure password is loaded for key decryption
    manager.get_password()

    # Access keys manager
    keys_manager = KeysManager(
        path=operate._keys,  # pylint: disable=protected-access
        logger=operate_logger,
        password=operate.password,
    )

    # Find service for this chain
    service_manager = operate.service_manager()
    service_config_id = None
    for service in service_manager.json:
        if service["home_chain"] == chain_config:
            service_config_id = service["service_config_id"]
            break

    if not service_config_id:
        raise Exception(
            f"Cannot find deployed service id for chain {chain_config}. "
            f"Setup agent mode for this chain using 'mechx setup' command."
        )

    # Load service and extract keys
    service = operate.service_manager().load(service_config_id)
    agent_address = service.agent_addresses[0]
    key_path = keys_manager.get_private_key_file(agent_address)
    safe_address = service.chain_configs[chain_config].chain_data.multisig

    return safe_address, str(key_path), os.getenv("OPERATE_PASSWORD")
