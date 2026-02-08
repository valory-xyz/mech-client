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

"""Configuration loading utilities."""

import json
from typing import Optional

from mech_client.infrastructure.config.chain_config import LedgerConfig, MechConfig
from mech_client.infrastructure.config.constants import MECH_CONFIGS


def get_mech_config(
    chain_config: Optional[str] = None, agent_mode: bool = False
) -> MechConfig:
    """Load mech configuration for a specific chain.

    Loads configuration from mechs.json and applies environment variable
    overrides via dataclass __post_init__ methods.

    :param chain_config: Chain name (gnosis, base, polygon, optimism).
                        If None, uses first chain in config.
    :param agent_mode: Whether running in agent mode (uses stored operate config)
    :return: MechConfig instance with loaded configuration
    :raises FileNotFoundError: If mechs.json is not found
    :raises json.JSONDecodeError: If mechs.json is malformed
    :raises KeyError: If chain_config is not found in mechs.json
    """
    with open(MECH_CONFIGS, "r", encoding="UTF-8") as file:
        data = json.load(file)

        if chain_config is None:
            chain_config = next(iter(data))

        entry = data[chain_config].copy()
        ledger_config_data = entry.pop("ledger_config")
        # Remove nvm_subscription if present (used by NVMConfig, not MechConfig)
        entry.pop("nvm_subscription", None)

        # Create LedgerConfig with agent_mode and chain_config context
        ledger_config = LedgerConfig(
            **ledger_config_data, agent_mode=agent_mode, chain_config=chain_config
        )

        mech_config = MechConfig(
            **entry,
            ledger_config=ledger_config,
            agent_mode=agent_mode,
            chain_config=chain_config,
        )
        return mech_config
