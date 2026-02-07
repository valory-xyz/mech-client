"""Mech client.

Public API for using mech-client as a library.

Example usage:
    >>> from mech_client import MarketplaceService, PaymentType, get_mech_config
    >>> from aea_ledger_ethereum import EthereumApi, EthereumCrypto
    >>>
    >>> config = get_mech_config("gnosis")
    >>> crypto = EthereumCrypto("ethereum_private_key.txt")
    >>> ledger_api = EthereumApi(**config.ledger_config.__dict__)
    >>>
    >>> service = MarketplaceService(
    ...     chain_config="gnosis",
    ...     ledger_api=ledger_api,
    ...     payer_address=crypto.address,
    ...     mode="client",
    ... )
    >>>
    >>> result = service.send_request(
    ...     priority_mech="0x...",
    ...     tools=["openai-gpt-4"],
    ...     prompts=["What is 2+2?"],
    ...     payment_type=PaymentType.NATIVE,
    ... )
"""

__version__ = "0.17.2"

# Domain models
from mech_client.domain.tools.models import (
    ToolInfo,
    ToolSchema,
    ToolsForMarketplaceMech,
)

# Configuration
from mech_client.infrastructure.config.loader import get_mech_config
from mech_client.infrastructure.config.payment_config import PaymentType
from mech_client.services.deposit_service import DepositService

# Services - Main entry points for library users
from mech_client.services.marketplace_service import MarketplaceService
from mech_client.services.setup_service import SetupService
from mech_client.services.subscription_service import SubscriptionService
from mech_client.services.tool_service import ToolService

# Exceptions
from mech_client.utils.errors.exceptions import (
    AgentModeError,
    ConfigurationError,
    ContractError,
    DeliveryTimeoutError,
    IPFSError,
    MechClientError,
    PaymentError,
    RpcError,
    SubgraphError,
    ToolError,
    TransactionError,
    ValidationError,
)


__all__ = [
    # Version
    "__version__",
    # Services
    "MarketplaceService",
    "ToolService",
    "DepositService",
    "SetupService",
    "SubscriptionService",
    # Configuration
    "get_mech_config",
    "PaymentType",
    # Domain models
    "ToolInfo",
    "ToolsForMarketplaceMech",
    "ToolSchema",
    # Exceptions
    "MechClientError",
    "RpcError",
    "SubgraphError",
    "ContractError",
    "ValidationError",
    "ConfigurationError",
    "TransactionError",
    "IPFSError",
    "ToolError",
    "AgentModeError",
    "PaymentError",
    "DeliveryTimeoutError",
]
