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

        # Load mechs.json
        mechs_file = Path(__file__).parent.parent.parent / "configs" / "mechs.json"
        if not mechs_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {mechs_file}")

        with open(mechs_file, "r", encoding="utf-8") as f:
            mechs_config = json.load(f)

        if chain_config not in mechs_config:
            raise ValueError(f"Chain {chain_config!r} not found in mechs.json")

        chain_data = mechs_config[chain_config]

        # Check if NVM subscription config exists
        if "nvm_subscription" not in chain_data:
            raise ValueError(
                f"NVM subscription configuration not found for chain {chain_config!r}"
            )

        nvm_sub_config = chain_data["nvm_subscription"]

        # Load networks.json
        networks_file = Path(__file__).parent / "resources" / "networks.json"
        if not networks_file.exists():
            raise FileNotFoundError(
                f"Networks configuration file not found: {networks_file}"
            )

        with open(networks_file, "r", encoding="utf-8") as f:
            networks = json.load(f)

        # Map chain_config to network key (uppercase for networks.json)
        network_key_map = {"gnosis": "GNOSIS", "base": "BASE"}
        network_key = network_key_map[chain_config]

        if network_key not in networks:
            raise ValueError(f"Network {network_key!r} not found in networks.json")

        network_config = networks[network_key]
        nvm_config = network_config["nvm"]

        # Build config from mechs.json and networks.json
        return cls(
            chain_config=chain_config,
            chain_id=chain_data["ledger_config"]["chain_id"],
            network_name=network_key,
            plan_did=nvm_sub_config["plan_did"],
            subscription_credits=nvm_sub_config["subscription_credits"],
            plan_fee_nvm=nvm_sub_config["plan_fee_nvm"],
            plan_price_mechs=nvm_sub_config["plan_price_mechs"],
            subscription_nft_address=nvm_sub_config["subscription_nft_address"],
            olas_marketplace_address=chain_data["mech_marketplace_contract"],
            receiver_plan=nvm_sub_config["receiver_plan"],
            token_address=nvm_sub_config["token_address"],
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
