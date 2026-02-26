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

"""Setup service for agent mode configuration."""

import logging
import os
from pathlib import Path
from typing import Dict, Optional

from operate.quickstart.run_service import run_service

from mech_client.infrastructure.config import get_mech_config
from mech_client.infrastructure.config.environment import EnvironmentConfig
from mech_client.infrastructure.operate import OperateManager


logger = logging.getLogger(__name__)


class SetupService:
    """Service for agent mode setup and configuration.

    Orchestrates Operate middleware setup, service deployment,
    and wallet information display.
    """

    def __init__(self, chain_config: str, template_path: Path):
        """
        Initialize setup service.

        :param chain_config: Chain configuration name (gnosis, base, etc.)
        :param template_path: Path to service template JSON file
        """
        self.chain_config = chain_config
        self.template_path = template_path
        self.operate_manager = OperateManager()

    def setup(self) -> None:
        """
        Setup agent mode for the chain.

        Creates Operate environment, loads service template, configures
        RPC endpoints, and deploys the service.

        :raises Exception: If setup fails
        """
        # Ensure Operate is initialized
        operate = self.operate_manager.operate
        operate.setup()

        # Get and store password
        self.operate_manager.get_password()
        logger.info("Password configured")

        # Configure middleware environment for unattended setup
        logger.info(f"Configuring service for {self.chain_config}...")
        rpc_url = self._get_rpc_url()
        ledger_rpc_env_var = f"{self.chain_config.upper()}_LEDGER_RPC"
        os.environ["ATTENDED"] = "false"
        os.environ[ledger_rpc_env_var] = rpc_url
        # "no_staking"; use numeric choice "1" (No staking) for compatibility.
        os.environ["STAKING_PROGRAM"] = "1"
        logger.info(f"Set {ledger_rpc_env_var} for unattended quickstart")
        logger.info("Set STAKING_PROGRAM=1 (No staking)")

        # Run service setup
        try:
            run_service(
                operate=operate,
                config_path=self.template_path,
                build_only=True,
                use_binary=True,
                skip_dependency_check=False,
            )
            logger.info(f"Service configured for {self.chain_config}")
        except Exception as e:
            logger.error(f"Service setup failed: {e}")
            raise

    def _get_rpc_url(self) -> str:
        """
        Get RPC URL for the configured chain.

        Uses MECHX_CHAIN_RPC env var if set, otherwise falls back to mechs.json default.

        :return: RPC URL string
        """
        env_config = EnvironmentConfig.load()
        if env_config.mechx_chain_rpc is not None:
            logger.info(f"Using MECHX_CHAIN_RPC override for {self.chain_config}")
            return env_config.mechx_chain_rpc

        mech_config = get_mech_config(self.chain_config)
        logger.info(f"Using default RPC for {self.chain_config}")
        return mech_config.rpc_url

    def display_wallets(self) -> Optional[Dict[str, str]]:
        """
        Display wallet information after setup.

        Extracts and returns master wallet, Safe addresses, and agent addresses.

        :return: Dictionary with wallet information, or None if extraction fails
        """
        try:
            operate = self.operate_manager.operate

            # Load master wallet
            master_wallet = operate.wallet_manager.load("ethereum")

            # The safes dict uses ChainType enum keys, not strings
            # We need to find the safe by matching the enum's value
            master_safe = "N/A"
            for chain_type, safe_address in master_wallet.safes.items():
                # ChainType enum has a 'value' attribute that contains the string (e.g., 'gnosis')
                if (
                    hasattr(chain_type, "value")
                    and chain_type.value == self.chain_config
                ):
                    master_safe = str(safe_address)
                    break

            # Load service
            service_manager = operate.service_manager()
            service_config_id = None
            for service in service_manager.json:
                if service["home_chain"] == self.chain_config:
                    service_config_id = service["service_config_id"]
                    break

            if not service_config_id:
                logger.warning(f"Could not find service for {self.chain_config}")
                return None

            service = service_manager.load(service_config_id)
            agent_eoa = service.agent_addresses[0] if service.agent_addresses else "N/A"
            agent_safe = (
                service.chain_configs[self.chain_config].chain_data.multisig
                if self.chain_config in service.chain_configs
                else "N/A"
            )

            # Get service token ID for marketplace URL
            service_token = None
            if self.chain_config in service.chain_configs:
                token = service.chain_configs[self.chain_config].chain_data.token
                # Token is -1 if not yet deployed on-chain
                if token != -1:
                    service_token = token

            wallet_info = {
                "master_eoa": master_wallet.address,
                "master_safe": master_safe,
                "agent_eoa": agent_eoa,
                "agent_safe": agent_safe,
            }

            # Print formatted output
            self._print_wallet_box(wallet_info, service_token)

            return wallet_info

        except Exception as e:  # pylint: disable=broad-except
            logger.warning(f"Could not display wallet info: {e}")
            return None

    def _print_wallet_box(
        self, wallet_info: Dict[str, str], service_token: Optional[int] = None
    ) -> None:
        """
        Print wallet information in a formatted box.

        :param wallet_info: Dictionary with wallet addresses
        :param service_token: Optional service token ID for marketplace URL
        """
        title = f" Agent Mode Setup Complete ({self.chain_config.upper()}) "
        wallet_data = [
            ("Master EOA", wallet_info["master_eoa"]),
            ("Master Safe", wallet_info["master_safe"]),
            ("Agent EOA", wallet_info["agent_eoa"]),
            ("Agent Safe", wallet_info["agent_safe"]),
        ]

        # Calculate dimensions
        label_width = max(len(label) for label, _ in wallet_data)
        box_width = max(label_width + 46, len(title)) + 4

        # Build lines
        title_pad = (box_width - len(title) - 2) // 2
        lines = [
            f"╔{'═' * title_pad}{title}{'═' * (box_width - title_pad - len(title) - 2)}╗"
        ]
        lines.append(f"║{' ' * (box_width - 2)}║")

        for label, address in wallet_data:
            content = f"  {label:<{label_width}} : {address}"
            lines.append(f"║{content}{' ' * (box_width - len(content) - 2)}║")

        lines.append(f"║{' ' * (box_width - 2)}║")
        lines.append(f"╚{'═' * (box_width - 2)}╝")

        wallet_box = "\n".join(lines)
        logger.info(f"\n{wallet_box}")

        # Display marketplace URL if service is deployed
        if service_token is not None:
            marketplace_url = f"https://marketplace.olas.network/{self.chain_config}/ai-agents/{service_token}"
            logger.info(f"Marketplace: {marketplace_url}")
        else:
            logger.info("Marketplace: URL unknown")
