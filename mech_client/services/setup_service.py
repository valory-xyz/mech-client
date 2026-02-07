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

from pathlib import Path
from typing import Dict, Optional

from operate.cli import OperateApp
from operate.constants import NO_STAKING_PROGRAM_ID
from operate.operate_types import ServiceTemplate
from operate.quickstart.run_service import QuickstartConfig, run_service

from mech_client.infrastructure.config import get_mech_config
from mech_client.infrastructure.operate import OperateManager


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
        import sys  # pylint: disable=import-outside-toplevel

        # Ensure Operate is initialized
        operate = self.operate_manager.operate
        operate.setup()

        # Get and store password
        self.operate_manager.get_password()
        print("✓ Password configured")

        # Load service template
        print(f"Loading service template from {self.template_path}...")
        # This would normally load the template, but we'll use operate's run_service

        # Configure local config with RPC override
        print(f"Configuring service for {self.chain_config}...")

        # Monkey-patch configure_local_config to use our custom implementation
        # This is necessary to override the RPC configuration from MECHX_CHAIN_RPC
        # Create a wrapper function without self parameter for monkey-patching
        def _configure_wrapper(
            template: ServiceTemplate, operate_instance: OperateApp
        ) -> QuickstartConfig:
            return self.configure_local_config(template, operate_instance)

        sys.modules[
            "operate.quickstart.run_service"
        ].configure_local_config = _configure_wrapper  # type: ignore

        # Run service setup
        try:
            run_service(
                operate=operate,
                config_path=self.template_path,
                build_only=True,
                use_binary=True,
                skip_dependency_check=False,
            )
            print(f"✓ Service configured for {self.chain_config}")
        except Exception as e:
            print(f"✗ Service setup failed: {e}")
            raise

    def configure_local_config(  # pylint: disable=no-self-use
        self, template: ServiceTemplate, operate: OperateApp
    ) -> QuickstartConfig:
        """
        Configure local quickstart configuration.

        Sets RPC endpoints and chain configs from environment variables
        and mechs.json configuration.

        :param template: Service template
        :param operate: OperateApp instance
        :return: Configured QuickstartConfig
        """
        from operate.quickstart.run_service import (  # pylint: disable=import-outside-toplevel
            load_local_config,
        )

        config = load_local_config(operate=operate, service_name=template["name"])

        if config.rpc is None:
            config.rpc = {}

        # Configure RPC for each chain in template
        for chain in template["configurations"]:
            import os  # pylint: disable=import-outside-toplevel

            # Use environment variable if set, otherwise fall back to default
            env_rpc = os.getenv("MECHX_CHAIN_RPC")
            if env_rpc is None:
                mech_config = get_mech_config(chain)
                env_rpc = mech_config.rpc_url
            config.rpc[chain] = env_rpc

        config.principal_chain = template["home_chain"]

        # Set chain configs in service template
        for chain in template["configurations"]:
            template["configurations"][chain] |= {
                "staking_program_id": NO_STAKING_PROGRAM_ID,
                "rpc": config.rpc[chain],
                "cost_of_bond": 1,
            }

        if config.user_provided_args is None:
            config.user_provided_args = {}

        config.store()
        return config

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
            master_safe = master_wallet.safes.get(self.chain_config, "N/A")
            if master_safe != "N/A":
                master_safe = str(master_safe)

            # Load service
            service_manager = operate.service_manager()
            service_config_id = None
            for service in service_manager.json:
                if service["home_chain"] == self.chain_config:
                    service_config_id = service["service_config_id"]
                    break

            if not service_config_id:
                print(f"⚠ Could not find service for {self.chain_config}")
                return None

            service = service_manager.load(service_config_id)
            agent_eoa = service.agent_addresses[0] if service.agent_addresses else "N/A"
            agent_safe = (
                service.chain_configs[self.chain_config].chain_data.multisig
                if self.chain_config in service.chain_configs
                else "N/A"
            )

            wallet_info = {
                "master_eoa": master_wallet.address,
                "master_safe": master_safe,
                "agent_eoa": agent_eoa,
                "agent_safe": agent_safe,
            }

            # Print formatted output
            self._print_wallet_box(wallet_info)

            return wallet_info

        except Exception as e:  # pylint: disable=broad-except
            print(f"⚠ Could not display wallet info: {e}")
            return None

    def _print_wallet_box(self, wallet_info: Dict[str, str]) -> None:
        """
        Print wallet information in a formatted box.

        :param wallet_info: Dictionary with wallet addresses
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

        print("\n" + "\n".join(lines) + "\n")
