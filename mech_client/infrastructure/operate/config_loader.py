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

"""Configuration loading utilities for agent mode."""

from typing import Any, Optional

from mech_client.infrastructure.operate.manager import OperateManager


def load_rpc_from_operate(chain_config: str) -> Optional[str]:
    """Load RPC URL from stored operate configuration.

    Reads the RPC URL that was persisted during `mechx setup` for the specified chain.
    This allows commands to reuse the RPC configuration without requiring
    MECHX_CHAIN_RPC to be set as an environment variable.

    :param chain_config: Chain name (gnosis, base, polygon, optimism)
    :return: RPC URL from operate config, or None if not found
    """
    try:
        manager = OperateManager()

        # Check if operate is initialized
        if not manager.is_initialized():
            return None

        # Find and load service for this chain
        service_obj = _find_service_for_chain(manager.operate, chain_config)
        if not service_obj:
            return None

        # Extract RPC from service configuration
        return _extract_rpc_from_service(service_obj, chain_config)

    except Exception:  # pylint: disable=broad-except
        # If there's any error reading from operate config, return None
        # and fall back to other configuration sources
        return None


def _find_service_for_chain(operate: Any, chain_config: str) -> Optional[Any]:
    """Find service object for the specified chain.

    :param operate: OperateApp instance
    :param chain_config: Chain configuration name
    :return: Service object or None
    """
    service_manager = operate.service_manager()
    for service in service_manager.json:
        if service["home_chain"] == chain_config:
            service_config_id = service["service_config_id"]
            return service_manager.load(service_config_id)
    return None


def _extract_rpc_from_service(service_obj: Any, chain_config: str) -> Optional[str]:
    """Extract RPC URL from service configuration.

    :param service_obj: Service object
    :param chain_config: Chain configuration name
    :return: RPC URL or None
    """
    if chain_config not in service_obj.chain_configs:
        return None

    chain_data = service_obj.chain_configs[chain_config]
    if not hasattr(chain_data, "ledger_config") or not chain_data.ledger_config:
        return None

    ledger_config = chain_data.ledger_config
    if hasattr(ledger_config, "rpc") and ledger_config.rpc:
        return ledger_config.rpc

    return None
