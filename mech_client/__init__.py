"""Mech client.

Public API for using mech-client as a library.

Example usage:
    >>> from mech_client import MarketplaceService, PaymentType
    >>> from aea_ledger_ethereum import EthereumCrypto
    >>>
    >>> crypto = EthereumCrypto("ethereum_private_key.txt")
    >>>
    >>> service = MarketplaceService(
    ...     chain_config="gnosis",
    ...     agent_mode=False,
    ...     crypto=crypto,
    ... )
    >>>
    >>> result = service.send_request(
    ...     priority_mech="0x...",
    ...     tools=["openai-gpt-4"],
    ...     prompts=["What is 2+2?"],
    ...     payment_type=PaymentType.NATIVE,
    ... )
"""

__version__ = "0.18.7"

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
