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

To keep the private key out of the process entirely (e.g. key custody in a
separate signer service), implement the ``Signer`` protocol and pass it
instead of ``crypto``:

    >>> from mech_client import MarketplaceService, Signer
    >>>
    >>> my_signer: Signer = MySignerImplementation()
    >>> service = MarketplaceService(
    ...     chain_config="gnosis",
    ...     agent_mode=False,
    ...     signer=my_signer,
    ... )
"""

__version__ = "0.26.0"

# Chat contract
from mech_client.domain.delivery.chat import ChatReport, chat_report, is_chat_prompt

# Payment addresses
from mech_client.domain.payment.addresses import balance_tracker, payment_token

# Request id
from mech_client.domain.request_id import request_digest

# Signing
from mech_client.domain.signing import LocalSigner, Signer

# Domain models
from mech_client.domain.tools.manager import ToolManager, offchain_blocker
from mech_client.domain.tools.models import (
    MetadataRead,
    ToolInfo,
    ToolSchema,
    ToolsForMarketplaceMech,
)

# Configuration
from mech_client.infrastructure.config.loader import get_mech_config
from mech_client.infrastructure.config.payment_config import PaymentType

# Off-chain nonce allocation
from mech_client.nonces import (
    NonceAllocator,
    NonceRefused,
    Outcome,
    Reservation,
    outcome_of,
    send_with_nonce,
)
from mech_client.services.deposit_service import DepositService

# Services - Main entry points for library users
from mech_client.services.marketplace_service import (
    MarketplaceService,
    MechInfo,
    MechPriceExceeded,
    OffchainRequestRejected,
    OffchainRequestResult,
    OffchainTopUpFailed,
    PreSignHook,
    RequestIdMismatch,
)
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
    "payment_token",
    "balance_tracker",
    # Marketplace
    "MechInfo",
    "OffchainRequestResult",
    "request_digest",
    # Off-chain nonce allocation
    "NonceAllocator",
    "NonceRefused",
    "Outcome",
    "Reservation",
    "outcome_of",
    "send_with_nonce",
    "PreSignHook",
    # Tools and off-chain capability
    "ToolManager",
    "MetadataRead",
    "offchain_blocker",
    # Chat contract
    "ChatReport",
    "chat_report",
    "is_chat_prompt",
    # Signing
    "Signer",
    "LocalSigner",
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
    "OffchainRequestRejected",
    "OffchainTopUpFailed",
    "RequestIdMismatch",
    "MechPriceExceeded",
]
