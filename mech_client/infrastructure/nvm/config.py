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

"""NVM subscription configuration."""

import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class NVMConfig:  # pylint: disable=too-many-instance-attributes
    """Configuration for NVM subscription operations."""

    # Chain-specific settings
    chain_config: str
    chain_id: int
    network_name: str  # Used for chain identification

    # NVM plan settings
    plan_did: str
    subscription_credits: str
    plan_fee_nvm: str
    plan_price_mechs: str

    # Contract addresses
    subscription_nft_address: str
    olas_marketplace_address: str
    receiver_plan: str  # Used in agreement receivers list
    token_address: str

    # Network configuration from networks.json
    web3_provider_uri: str  # Can be overridden by MECHX_CHAIN_RPC
    marketplace_uri: str  # NVM marketplace API endpoint
    nevermined_node_uri: str  # NVM node endpoint
    nevermined_node_address: str  # NVM node address
    subscription_id: str
    etherscan_url: str  # Block explorer URL
    native_token: str  # Native token name (xDAI, ETH, etc.)

    def __post_init__(self) -> None:
        """Override configuration with environment variables."""
        # Allow MECHX_CHAIN_RPC to override web3_provider_uri
        if "MECHX_CHAIN_RPC" in os.environ:
            self.web3_provider_uri = os.environ["MECHX_CHAIN_RPC"]

    @classmethod
    def from_chain(cls, chain_config: str) -> "NVMConfig":
        """
        Load NVM configuration for a specific chain.

        :param chain_config: Chain identifier (gnosis, base)
        :return: NVMConfig instance
        :raises ValueError: If chain is not supported
        """
        # Validate chain support
        supported_chains = {"gnosis", "base"}
        if chain_config not in supported_chains:
            raise ValueError(
                f"NVM subscriptions not supported for chain {chain_config!r}. "
                f"Supported chains: {', '.join(sorted(supported_chains))}"
            )

        # Load chain-specific .env file
        base_path = Path(__file__).parent / "resources" / "envs"
        env_file = base_path / f"{chain_config}.env"

        if not env_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {env_file}")

        load_dotenv(env_file)

        # Load networks.json
        networks_file = Path(__file__).parent / "resources" / "networks.json"
        if not networks_file.exists():
            raise FileNotFoundError(
                f"Networks configuration file not found: {networks_file}"
            )

        with open(networks_file, "r", encoding="utf-8") as f:
            networks = json.load(f)

        # Get network config (uppercase for networks.json keys)
        network_key = os.environ["NETWORK_NAME"]
        if network_key not in networks:
            raise ValueError(f"Network {network_key!r} not found in networks.json")

        network_config = networks[network_key]
        nvm_config = network_config["nvm"]

        # Build config from environment and networks.json
        return cls(
            chain_config=chain_config,
            chain_id=int(os.environ["CHAIN_ID"]),
            network_name=network_key,
            plan_did=os.environ["PLAN_DID"],
            subscription_credits=os.environ["SUBSCRIPTION_CREDITS"],
            plan_fee_nvm=os.environ["PLAN_FEE_NVM"],
            plan_price_mechs=os.environ["PLAN_PRICE_MECHS"],
            subscription_nft_address=os.environ["SUBSCRIPTION_NFT_ADDRESS"],
            olas_marketplace_address=os.environ["OLAS_MARKETPLACE_ADDRESS"],
            receiver_plan=os.environ["RECEIVER_PLAN"],
            token_address=os.environ["TOKEN_ADDRESS"],
            web3_provider_uri=nvm_config["web3ProviderUri"],
            marketplace_uri=nvm_config["marketplaceUri"],
            nevermined_node_uri=nvm_config["neverminedNodeUri"],
            nevermined_node_address=nvm_config["neverminedNodeAddress"],
            subscription_id=str(nvm_config["subscription_id"]),
            etherscan_url=network_config["etherscanUrl"],
            native_token=network_config["nativeToken"],
        )

    def requires_token_approval(self) -> bool:
        """
        Check if token approval is required for this chain.

        :return: True if token approval needed (Base), False otherwise (Gnosis)
        """
        # Gnosis uses native xDAI (token_address is zero address)
        # Base uses USDC (token_address is ERC20 contract)
        return (
            self.token_address != "0x0000000000000000000000000000000000000000"  # nosec
        )

    def get_transaction_value(self) -> int:
        """
        Get the transaction value (msg.value) for the subscription purchase.

        :return: Transaction value in wei (native token amount for Gnosis, 0 for Base)
        """
        if self.requires_token_approval():
            # Base: paying with USDC token, no native token value
            return 0
        # Gnosis: paying with native xDAI
        return int(self.plan_fee_nvm) + int(self.plan_price_mechs)

    def get_total_payment_amount(self) -> int:
        """
        Get the total payment amount (for balance checks and approvals).

        :return: Total payment amount in smallest token unit
        """
        return int(self.plan_fee_nvm) + int(self.plan_price_mechs)
