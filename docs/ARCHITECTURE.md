# Mech Client Architecture

This document provides a comprehensive overview of the mech-client architecture after the v0.17.0 refactoring.

## Table of Contents

- [Overview](#overview)
- [Architecture Principles](#architecture-principles)
- [Layer Descriptions](#layer-descriptions)
- [Data Flow](#data-flow)
- [Key Patterns](#key-patterns)
- [Component Reference](#component-reference)
- [Testing Strategy](#testing-strategy)

## Overview

The mech-client is a Python CLI tool and library for interacting with AI Mechs (on-chain AI agents) via the Olas (Mech) Marketplace. The architecture follows a layered, hexagonal-inspired design that separates business logic from infrastructure concerns.

```
┌─────────────────────────────────────────────────────────────────┐
│                          CLI Layer                               │
│                     (User Interface)                             │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Service Layer                              │
│                   (Orchestration Logic)                          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Domain Layer                              │
│              (Business Logic & Strategies)                       │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Infrastructure Layer                           │
│              (External System Adapters)                          │
└─────────────────────────────────────────────────────────────────┘
```

## Architecture Principles

### 1. Separation of Concerns

Each layer has a specific responsibility:
- **CLI**: User interaction and command routing
- **Service**: Business workflow orchestration
- **Domain**: Core business logic and rules
- **Infrastructure**: External system integration

### 2. Dependency Inversion

Dependencies flow inward toward the domain layer. Infrastructure depends on domain abstractions, not vice versa.

```python
# Domain defines the interface
class DeliveryWatcher(ABC):
    @abstractmethod
    async def watch(self, request_ids: List[str]) -> Dict[str, Any]:
        pass

# Infrastructure implements it
class OnchainDeliveryWatcher(DeliveryWatcher):
    async def watch(self, request_ids: List[str]) -> Dict[str, Any]:
        # Implementation using blockchain APIs
```

### 3. Strategy Pattern

Business decisions (payment, execution, delivery) use the Strategy pattern for flexibility:

```python
# Payment strategies
strategy = PaymentStrategyFactory.create(payment_type, ledger_api)
strategy.approve_if_needed(payer_address, amount, marketplace_address)

# Execution strategies
executor = ExecutorFactory.create(mode, ledger_api, safe_address)
tx_hash = executor.execute(tx_params)
```

### 4. Single Responsibility

Each module has one clear purpose:
- `payment/native.py`: Native token payments only
- `execution/client.py`: Client mode (EOA) execution only
- `delivery/onchain_watcher.py`: On-chain delivery watching only

### 5. Testability

All components are designed for easy testing:
- Constructor injection of dependencies
- Interface-based design
- Minimal global state
- Pure functions where possible

## Layer Descriptions

### CLI Layer (`cli/`)

**Purpose**: Handle user interaction, command parsing, and basic validation.

**Components**:
- `main.py`: Click-based command definitions and mode management
- `validators.py`: CLI-specific input validation
- `commands/`: Individual command implementations

**Responsibilities**:
- Parse command-line arguments
- Validate user inputs
- Route to appropriate service methods
- Display results to user
- Handle CLI-level errors
- Manage operating modes (agent mode vs client mode)

**Design Principles**:
- Thin layer - minimal logic
- Delegate to services for business operations
- Convert CLI arguments to service method parameters
- Handle presentation formatting

#### Operating Modes

The CLI supports two operating modes for wallet-based commands:

**1. Agent Mode (Default)**
- Uses Safe multisig for transactions
- Requires `mechx setup --chain-config <chain>` first
- Checks for `~/.operate_mech_client/` directory
- Shows "Agent mode enabled" message
- Applied to: `request`, `deposit`, `subscription` commands

**2. Client Mode**
- Uses EOA (Externally Owned Account) directly
- Enabled with `--client-mode` flag
- Requires `--key` parameter for private key
- No setup needed
- Applied to: `request`, `deposit`, `subscription` commands

**Mode Detection Logic** (`main.py`):
```python
WALLET_COMMANDS = {"request", "deposit", "subscription"}

if is_wallet_command and not is_setup_called and not client_mode:
    click.echo("Agent mode enabled")
    operate_path = Path.home() / OPERATE_FOLDER_NAME
    if not operate_path.exists():
        raise ClickException("Setup agent mode using 'mechx setup' command.")
```

**Command Categories**:
- **Wallet commands** (require mode): `request`, `deposit`, `subscription`
- **Read-only commands** (no mode): `mech list`, `tool list/describe/schema`
- **Utility commands** (no mode): `ipfs upload/upload-prompt`
- **Setup command** (creates agent mode setup)

**Example**:
```python
@main.command()
@click.option("--priority-mech", required=True, type=str)
@click.option("--tool", "tools", multiple=True, required=True)
@click.option("--prompt", "prompts", multiple=True, required=True)
@click.pass_context
def request(ctx: click.Context, priority_mech: str, tools: List[str], prompts: List[str]) -> None:
    """Send a request to the mech marketplace."""
    # Extract mode from context
    agent_mode = not ctx.obj.get("client_mode", False)

    # Validate inputs
    validate_ethereum_address(priority_mech, "Priority mech")

    # Create service
    service = MarketplaceService(
        chain_config=chain_config,
        agent_mode=agent_mode,
        crypto=crypto,
        agent_mode=agent_mode,
        # ... other dependencies
    )

    # Delegate to service
    result = service.send_request(
        priority_mech=priority_mech,
        tools=tools,
        prompts=prompts,
    )

    # Display result
    click.echo(f"Request sent: {result['tx_hash']}")
```

### Service Layer (`services/`)

**Purpose**: Orchestrate business workflows by coordinating domain objects.

**Components**:
- `marketplace_service.py`: Marketplace request orchestration
- `tool_service.py`: Tool metadata operations
- `deposit_service.py`: Deposit orchestration

**Responsibilities**:
- Coordinate multiple domain operations
- Manage transaction workflows
- Handle cross-cutting concerns (logging, error handling)
- Convert between domain and external representations

**Design Principles**:
- No direct infrastructure access
- Use domain strategies and managers
- Handle business workflow logic
- Keep services stateless where possible

**Base Service Pattern**:

Transaction services inherit from `BaseTransactionService` which provides common initialization:

```python
class BaseTransactionService:
    """Base class for services that execute blockchain transactions."""

    def __init__(
        self,
        chain_config: str,
        agent_mode: bool,
        crypto: EthereumCrypto,
        safe_address: Optional[str] = None,
        ethereum_client: Optional[EthereumClient] = None,
    ):
        # Initializes: mech_config, ledger_api, executor
        # Subclasses get these automatically

class MarketplaceService(BaseTransactionService):
    # Inherits ledger_api, executor, mech_config
    pass
```

**Example**:
```python
class MarketplaceService:
    def send_request(
        self,
        priority_mech: str,
        tools: List[str],
        prompts: List[str],
        payment_type: PaymentType,
    ) -> Dict[str, Any]:
        """Send request to marketplace."""
        # 1. Validate inputs
        self._validate_inputs(tools, prompts)

        # 2. Upload to IPFS
        ipfs_hash = self.ipfs_client.upload_prompt(prompts, tools)

        # 3. Get payment strategy
        strategy = PaymentStrategyFactory.create(
            payment_type, self.ledger_api
        )

        # 4. Approve if needed
        strategy.approve_if_needed(
            self.payer_address, self.price, self.marketplace_address
        )

        # 5. Execute transaction (executor from BaseTransactionService)
        tx_hash = self.executor.execute(tx_params)

        # 6. Watch for delivery
        watcher = OnchainDeliveryWatcher(
            self.marketplace_contract, self.ledger_api
        )
        results = await watcher.watch(request_ids)

        return {"tx_hash": tx_hash, "results": results}
```

### Domain Layer (`domain/`)

**Purpose**: Implement core business logic and business rules.

**Components**:

#### Payment Strategies (`domain/payment/`)
Handle different payment mechanisms:
- `native.py`: Native token payments
- `token.py`: ERC20 token payments (OLAS, USDC)
- `nvm.py`: NVM subscription payments
- `factory.py`: Payment strategy factory

**Key Abstractions**:
```python
class PaymentStrategy(ABC):
    @abstractmethod
    def check_balance(self, payer: str, amount: int) -> bool:
        """Check if payer has sufficient balance."""

    @abstractmethod
    def approve_if_needed(
        self, payer: str, amount: int, spender: str
    ) -> Optional[str]:
        """Approve tokens if needed. Returns tx_hash or None."""
```

#### Execution Strategies (`domain/execution/`)
Handle transaction execution modes:
- `client.py`: Client mode (EOA) execution
- `agent.py`: Agent mode (Safe multisig) execution
- `factory.py`: Execution strategy factory

**Key Abstractions**:
```python
class TransactionExecutor(ABC):
    @abstractmethod
    def execute_transaction(self, contract, method_name, method_args, tx_args) -> str:
        """Execute a contract method call. Returns tx_hash."""

    @abstractmethod
    def execute_transfer(self, to_address, amount, gas) -> str:
        """Execute a plain native token transfer. Returns tx_hash."""
```

#### Delivery Watchers (`domain/delivery/`)
Handle response delivery mechanisms:
- `onchain_watcher.py`: On-chain event watching
- `base.py`: Delivery watcher interface

**Key Abstractions**:
```python
class DeliveryWatcher(ABC):
    @abstractmethod
    async def watch(self, request_ids: List[str]) -> Dict[str, Any]:
        """Watch for delivery. Returns results by request_id."""
```

#### Tool Managers (`domain/tools/`)
Handle tool metadata and discovery:
- `marketplace_manager.py`: Marketplace tool operations
- `metadata.py`: Tool metadata structures

**Design Principles**:
- Pure business logic
- No infrastructure dependencies
- Use abstractions (ABC) for external concerns
- Immutable data structures where possible

### Infrastructure Layer (`infrastructure/`)

**Purpose**: Provide adapters to external systems.

**Components**:

#### Blockchain (`infrastructure/blockchain/`)
- `abi_loader.py`: Load contract ABIs
- `contracts/`: Contract interaction helpers
- `receipt_waiter.py`: Transaction receipt polling
- `safe_client.py`: Gnosis Safe integration

#### IPFS (`infrastructure/ipfs/`)
- `client.py`: IPFS gateway client
- `converters.py`: Hash format conversions
- `metadata.py`: Metadata upload/download

#### Subgraph (`infrastructure/subgraph/`)
- `client.py`: GraphQL client
- `queries.py`: Predefined queries

#### Configuration (`infrastructure/config/`)
- `chain_config.py`: Chain configuration dataclasses
- `loader.py`: Configuration loading
- `contract_addresses.py`: Contract address mappings
- `constants.py`: Infrastructure constants

#### Operate (`infrastructure/operate/`)
- `manager.py`: Olas Operate integration
- `key_manager.py`: Key management for agent mode

**Design Principles**:
- Implement domain interfaces
- Handle all external I/O
- Convert external data to domain models
- Encapsulate third-party libraries

**Example**:
```python
class IPFSClient:
    """Client for IPFS operations."""

    def upload(self, file_path: str) -> Tuple[str, str]:
        """Upload file to IPFS. Returns (v1_hash, v1_hex)."""
        result = self.ipfs_tool.client.add(
            file_path, pin=True, recursive=True
        )
        v0_hash = result["Hash"]
        v1_hash = to_v1(v0_hash)
        v1_hex = ipfs_hash_to_hex(v1_hash)
        return v1_hash, v1_hex
```

### Utils Layer (`utils/`)

**Purpose**: Provide shared utilities across all layers.

**Components**:
- `validators.py`: Business input validation
- `errors/`: Custom exception hierarchy
- `logger.py`: Structured logging
- `constants.py`: Shared constants

**Design Principles**:
- No dependencies on other layers
- Pure functions
- Reusable across contexts
- Well-tested

## Data Flow

### Request Flow Example

```
┌──────┐
│ User │ mechx request --priority-mech 0x... --tool gpt-4 --prompt "..."
└──┬───┘
   │
   ▼
┌─────────────────────────────────────────────────────────────┐
│ CLI Layer (commands/request.py)                             │
│ - Parse arguments                                            │
│ - Validate ethereum address                                  │
│ - Load configuration                                         │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ Service Layer (marketplace_service.py)                      │
│ - Validate prompt/tool counts match                          │
│ - Coordinate workflow                                        │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
    ┌─────────┐   ┌──────────┐   ┌──────────┐
    │ Payment │   │Execution │   │ Delivery │
    │Strategy │   │ Strategy │   │ Watcher  │
    └────┬────┘   └────┬─────┘   └────┬─────┘
         │             │              │
         │             │              │
         ▼             ▼              ▼
┌─────────────────────────────────────────────────────────────┐
│ Infrastructure Layer                                        │
│ - IPFS upload (ipfs/client.py)                             │
│ - Token approval (blockchain/contracts/)                    │
│ - Transaction execution (blockchain/safe_client.py)         │
│ - Event watching (blockchain/receipt_waiter.py)             │
│ - IPFS download (ipfs/client.py)                           │
└─────────────────────────────────────────────────────────────┘
```

### Deposit Flow Example

```
User → CLI → DepositService → PaymentStrategy → Infrastructure
                     │              │                  │
                     │              │                  ├─ Check balance
                     │              │                  ├─ Approve token
                     │              │                  └─ Send deposit tx
                     │              │
                     │              └─ Uses: NativePaymentStrategy
                     │                        or TokenPaymentStrategy
                     │
                     └─ Orchestrates: validate → check → approve → execute
```

## Key Patterns

### 1. Factory Pattern

Used for creating strategies based on runtime configuration:

```python
class PaymentStrategyFactory:
    @staticmethod
    def create(
        payment_type: PaymentType,
        ledger_api: EthereumApi,
    ) -> PaymentStrategy:
        """Create payment strategy based on type."""
        if payment_type == PaymentType.NATIVE:
            return NativePaymentStrategy(ledger_api)
        elif payment_type == PaymentType.TOKEN:
            return TokenPaymentStrategy(ledger_api, token_address)
        elif payment_type == PaymentType.NATIVE_NVM:
            return NVMPaymentStrategy(ledger_api, nvm_config)
        else:
            raise ValueError(f"Unknown payment type: {payment_type}")
```

### 2. Strategy Pattern

Encapsulates algorithms (payment, execution) as interchangeable objects:

```python
# Define strategy interface
class PaymentStrategy(ABC):
    @abstractmethod
    def approve_if_needed(
        self, payer: str, amount: int, spender: str
    ) -> Optional[str]:
        pass

# Use strategy
strategy = PaymentStrategyFactory.create(payment_type, ledger_api)
tx_hash = strategy.approve_if_needed(payer, amount, marketplace)
```

### 3. Dependency Injection

Constructor injection for testability:

```python
class MarketplaceService(BaseTransactionService):
    def __init__(
        self,
        chain_config: str,
        agent_mode: bool,
        crypto: EthereumCrypto,
        safe_address: Optional[str] = None,
        ethereum_client: Optional[EthereumClient] = None,
    ):
        # BaseTransactionService initializes: ledger_api, executor, mech_config
        super().__init__(chain_config, agent_mode, crypto, safe_address, ethereum_client)
        # Service-specific initialization
        self.ipfs_client = IPFSClient()
```

### 4. Repository Pattern

Infrastructure components act as repositories for external data:

```python
class SubgraphClient:
    """Repository for subgraph data."""

    def query_mechs(
        self, order_by: str = "totalDeliveries"
    ) -> Dict[str, Any]:
        """Query mechs from subgraph."""
        query = self._build_query(order_by)
        return self.client.execute(query)
```

### 5. Async/Await

Used for I/O-bound operations (delivery watching):

```python
class OnchainDeliveryWatcher(DeliveryWatcher):
    async def watch(self, request_ids: List[str]) -> Dict[str, Any]:
        """Watch for on-chain delivery."""
        while True:
            # Poll blockchain
            for request_id in request_ids:
                result = self._check_delivery(request_id)
                if result:
                    results[request_id] = result

            if len(results) == len(request_ids):
                return results

            await asyncio.sleep(WAIT_SLEEP)
```

## Component Reference

### Service Components

| Component | Layer | Purpose |
|-----------|-------|---------|
| `BaseTransactionService` | Service | Base class for transaction services |
| `MarketplaceService` | Service | Marketplace request orchestration |
| `DepositService` | Service | Deposit orchestration |
| `SubscriptionService` | Service | NVM subscription management |
| `ToolService` | Service | Tool metadata operations |
| `SetupService` | Service | Agent mode setup |

### Payment Components

| Component | Layer | Purpose |
|-----------|-------|---------|
| `PaymentStrategy` | Domain | Abstract payment interface |
| `NativePaymentStrategy` | Domain | Native token payments |
| `TokenPaymentStrategy` | Domain | ERC20 token payments |
| `NVMPaymentStrategy` | Domain | NVM subscription payments |
| `PaymentStrategyFactory` | Domain | Strategy creation |

### Execution Components

| Component | Layer | Purpose |
|-----------|-------|---------|
| `TransactionExecutor` | Domain | Abstract execution interface |
| `ClientExecutor` | Domain | EOA-based execution |
| `AgentExecutor` | Domain | Safe-based execution |
| `ExecutorFactory` | Domain | Executor creation |
| `SafeClient` | Infrastructure | Gnosis Safe integration |

### Delivery Components

| Component | Layer | Purpose |
|-----------|-------|---------|
| `DeliveryWatcher` | Domain | Abstract delivery interface |
| `OnchainDeliveryWatcher` | Domain | On-chain event watching |
| `wait_for_receipt` | Infrastructure | Transaction receipt polling |

### Tool Components

| Component | Layer | Purpose |
|-----------|-------|---------|
| `ToolManager` | Domain | Tool operations interface |
| `MarketplaceToolManager` | Domain | Marketplace tool ops |
| `ToolInfo` | Domain | Tool metadata structure |
| `ToolService` | Service | Tool service orchestration |

### Configuration Components

| Component | Layer | Purpose |
|-----------|-------|---------|
| `MechConfig` | Infrastructure | Chain configuration |
| `LedgerConfig` | Infrastructure | Ledger settings |
| `get_mech_config()` | Infrastructure | Config loader |
| `CONTRACT_ADDRESSES` | Infrastructure | Address mappings |

### Subscription Components

| Component | Layer | Purpose |
|-----------|-------|---------|
| `NVMConfig` | Infrastructure | NVM subscription configuration |
| `NVMContractWrapper` | Infrastructure | Base class for NVM contracts |
| `NVMContractFactory` | Infrastructure | Factory for creating NVM contracts |
| `SubscriptionManager` | Domain | Orchestrates subscription purchase workflow |
| `AgreementBuilder` | Domain | Builds agreement data structure |
| `FulfillmentBuilder` | Domain | Builds fulfillment parameters |
| `SubscriptionBalanceChecker` | Domain | Validates sufficient balance |
| `SubscriptionService` | Service | Service orchestration for subscriptions |
| `NVMPaymentStrategy` | Domain | Payment strategy for checking subscription status |

## NVM Subscription Architecture

The NVM (Nevermined) subscription module enables subscription-based payments for marketplace mechs. This section describes the refactored architecture introduced in v0.17.0+.

### Overview

NVM subscriptions provide an alternative payment model where users purchase a subscription plan to access mechs without per-request payments. The subscription purchase involves a 3-transaction workflow:

1. **Balance Check**: Verify sufficient funds (native tokens for Gnosis, USDC for Base)
2. **Token Approval** (Base only): Approve USDC for lock payment contract
3. **Create Agreement**: On-chain agreement creation with payment
4. **Fulfill Agreement**: Complete subscription activation

### Architecture Layers

#### Infrastructure Layer (`infrastructure/nvm/`)

Provides NVM-specific infrastructure adapters:

**Configuration** (`config.py`):
```python
@dataclass
class NVMConfig:
    """Configuration for NVM subscription operations."""

    chain_config: str
    chain_id: int
    network_name: str
    plan_did: str
    subscription_credits: str
    plan_fee_nvm: str
    plan_price_mechs: str
    subscription_nft_address: str
    token_address: str
    web3_provider_uri: str  # Overridable by MECHX_CHAIN_RPC
    # ... other configuration fields

    @classmethod
    def from_chain(cls, chain_config: str) -> "NVMConfig":
        """Load configuration from envs/{chain}.env and networks.json."""
        # Validates chain support (gnosis, base only)
        # Loads chain-specific settings
        # Supports MECHX_CHAIN_RPC override in __post_init__

    def requires_token_approval(self) -> bool:
        """Check if token approval needed (Base = True, Gnosis = False)."""
        return self.token_address != "0x0000..."

    def get_transaction_value(self) -> int:
        """Get native token value for transaction (Gnosis only)."""
        if self.requires_token_approval():
            return 0  # Base: paying with USDC, no native value
        return int(self.plan_fee_nvm) + int(self.plan_price_mechs)
```

**Contract Wrappers** (`contracts/`):
- `base.py`: `NVMContractWrapper` - simplified base class (no transaction building)
- `factory.py`: `NVMContractFactory` - creates all NVM contract instances
- 11 contract wrappers: `agreement_manager.py`, `did_registry.py`, `escrow_payment.py`, `lock_payment.py`, `nft.py`, `nft_sales.py`, `nevermined_config.py`, `subscription_provider.py`, `token.py`, `transfer_nft.py`

Key design: Contract wrappers provide **read-only methods** and contract instances. Transaction building is handled by the executor pattern.

**Resources** (`resources/`):
- `envs/gnosis.env`, `envs/base.env`: Chain-specific configuration
- `networks.json`: Network RPC endpoints and NVM node addresses

#### Domain Layer (`domain/subscription/`)

Implements subscription purchase business logic:

**Subscription Manager** (`manager.py`):
```python
class SubscriptionManager:
    """Orchestrates the subscription purchase workflow."""

    def purchase_subscription(self, plan_did: str) -> Dict[str, Any]:
        """
        Execute 3-transaction workflow:
        1. Check balance
        2. [Base only] Approve USDC token
        3. Create agreement
        4. Fulfill agreement
        """
        # Step 1: Check balance
        self.balance_checker.check()

        # Step 2: Build agreement data
        agreement = self.agreement_builder.build(plan_did)

        # Step 3: Token approval (Base only)
        if self.config.requires_token_approval():
            self._approve_token()

        # Step 4: Create agreement on-chain
        agreement_tx_hash = self._create_agreement(agreement)

        # Step 5: Fulfill agreement
        fulfillment_tx_hash = self._fulfill_agreement(agreement)

        return {
            "status": "success",
            "agreement_id": agreement.agreement_id.hex(),
            "agreement_tx_hash": agreement_tx_hash,
            "fulfillment_tx_hash": fulfillment_tx_hash,
        }
```

**Agreement Builder** (`agreement.py`):
```python
class AgreementBuilder:
    """Builds agreement data structure with condition IDs."""

    def build(self, plan_did: str) -> AgreementData:
        """
        Build agreement data:
        - Generate agreement ID seed and ID
        - Fetch DDO from DID Registry
        - Calculate condition hashes (lock, transfer, escrow)
        - Build receiver list
        """
        agreement_id_seed = os.urandom(32)
        agreement_id = self.agreement_manager.agreement_id(
            agreement_id_seed, self.sender
        )

        # Fetch DDO metadata
        ddo = self.did_registry.get_ddo(plan_did)

        # Calculate condition IDs
        lock_id = self.lock_payment.generate_id(agreement_id, ...)
        transfer_id = self.transfer_nft.generate_id(agreement_id, ...)
        escrow_id = self.escrow_payment.generate_id(agreement_id, ...)

        return AgreementData(
            agreement_id=agreement_id,
            did=plan_did,
            ddo=ddo,
            lock_id=lock_id,
            # ... other fields
        )
```

**Fulfillment Builder** (`fulfillment.py`):
```python
class FulfillmentBuilder:
    """Builds fulfillment parameter tuples."""

    def build(self, agreement: AgreementData) -> FulfillmentData:
        """Build fulfill_for_delegate_params and fulfill_params tuples."""
        fulfill_for_delegate_params = (
            agreement.ddo["owner"],  # nftHolder
            self.sender,  # nftReceiver
            int(self.config.subscription_credits),  # nftAmount
            "0x" + agreement.lock_id.hex(),  # lockPaymentCondition
            # ... other params
        )

        fulfill_params = (amounts, receivers, returnAddress, ...)

        return FulfillmentData(
            fulfill_for_delegate_params=fulfill_for_delegate_params,
            fulfill_params=fulfill_params,
        )
```

**Balance Checker** (`balance_checker.py`):
```python
class SubscriptionBalanceChecker:
    """Validates sufficient balance before purchase."""

    def check(self) -> None:
        """
        Check balance and raise ValueError if insufficient.
        - Gnosis: Check native xDAI balance
        - Base: Check USDC token balance
        """
        if self.config.requires_token_approval():
            # Base: Check USDC balance
            balance = self.token_contract.get_balance(self.sender)
        else:
            # Gnosis: Check native balance
            balance = self.w3.eth.get_balance(self.sender)

        required = self.config.get_total_payment_amount()
        if balance < required:
            raise ValueError(f"Insufficient balance: {balance} < {required}")
```

#### Service Layer (`services/subscription_service.py`)

Orchestrates subscription purchase using layered architecture:

```python
class SubscriptionService:
    """Service for managing NVM subscriptions."""

    def purchase_subscription(
        self, plan_did: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Purchase NVM subscription workflow:
        1. Create executor (agent mode or client mode)
        2. Create all NVM contract instances
        3. Create domain builders and managers
        4. Delegate to SubscriptionManager
        """
        # Use plan DID from config if not provided
        if not plan_did:
            plan_did = self.config.plan_did

        # Create executor for transaction handling
        executor = ExecutorFactory.create(
            ledger_api=self.ledger_api,
            agent_mode=self.agent_mode,
            crypto=self.crypto,
            ethereum_client=self.ethereum_client,
            safe_address=self.safe_address,
        )

        # Create required NVM contracts for this chain
        contracts = {
            # ... (create wrappers via NVMContractFactory.create)
        }

        # Create domain components
        agreement_builder = AgreementBuilder(...)
        fulfillment_builder = FulfillmentBuilder(...)
        balance_checker = SubscriptionBalanceChecker(...)

        # Create subscription manager
        manager = SubscriptionManager(
            w3=self.w3,
            ledger_api=self.ledger_api,
            config=self.config,
            sender=self.sender,
            executor=executor,
            agreement_builder=agreement_builder,
            fulfillment_builder=fulfillment_builder,
            balance_checker=balance_checker,
            nft_sales=contracts["nft_sales"],
            subscription_provider=contracts["subscription_provider"],
            subscription_nft=contracts["nft"],
            token_contract=contracts.get("token"),
        )

        # Execute purchase workflow
        return manager.purchase_subscription(plan_did)
```

#### CLI Layer (`cli/commands/subscription_cmd.py`)

Provides user interface for subscription purchase:

```python
@subscription.command(name="purchase")
@click.pass_context
def subscription_purchase(
    ctx: click.Context,
    chain_config: str,
    key: Optional[str] = None,
) -> None:
    """Purchase Nevermined subscription."""
    # Validate chain
    validated_chain = validate_chain_config(chain_config)

    # Validate NVM support (gnosis, base only)
    if validated_chain not in {"gnosis", "base"}:
        raise ClickException("NVM subscriptions only supported on gnosis, base")

    # Load configuration
    mech_config = get_mech_config(validated_chain)

    # Create crypto and ledger API
    crypto = EthereumCrypto(private_key_path=key_path, password=key_password)
    ledger_api = EthereumApi(**asdict(mech_config.ledger_config))

    # Create service
    service = SubscriptionService(
        chain_config=validated_chain,
        crypto=crypto,
        agent_mode=agent_mode,
        ledger_api=ledger_api,
        agent_mode=agent_mode,
        ethereum_client=ethereum_client,
        safe_address=safe_address,
    )

    # Execute purchase
    result = service.purchase_subscription()

    # Display results
    click.echo(f"✅ Subscription purchased successfully!")
    click.echo(f"Agreement ID: {result['agreement_id']}")
    click.echo(f"Agreement TX: {result['agreement_tx_hash']}")
    click.echo(f"Fulfillment TX: {result['fulfillment_tx_hash']}")
```

### Subscription Purchase vs Subscription Checking

The NVM module has two separate concerns handled by different components:

#### 1. Subscription Purchase (`domain/subscription/`, `services/subscription_service.py`)

**Purpose**: Purchase new NVM subscriptions

**Use case**: User runs `mechx subscription purchase` command

**Workflow**:
1. Check balance (native for Gnosis, USDC for Base)
2. Approve USDC token (Base only)
3. Create agreement on-chain (payment transaction)
4. Fulfill agreement (activate subscription)

**Architecture**: Uses layered refactored architecture (infrastructure → domain → service → CLI)

#### 2. Subscription Checking (`domain/payment/nvm.py`)

**Purpose**: Check if user HAS valid subscription when making marketplace requests

**Use case**: `MarketplaceService` validates subscription before sending request

**Implementation**:
```python
class NVMPaymentStrategy(PaymentStrategy):
    """Payment strategy for NVM subscription-based payments."""

    def check_balance(self, payer_address: str, amount: int) -> bool:
        """Check if payer has valid NVM subscription."""
        # Query subscription NFT balance
        nft_balance = subscription_nft.functions.balanceOf(
            payer_address, subscription_id
        ).call()

        # Query prepaid balance in balance tracker
        prepaid_balance = balance_tracker.functions.mapRequesterBalances(
            payer_address
        ).call()

        return (nft_balance + prepaid_balance) > 0
```

**Architecture**: Payment strategy pattern (part of v0.17.0 refactor)

These are **separate concerns** and both components should exist:
- **Subscription purchase**: Buys the subscription (3-transaction workflow)
- **Subscription checking**: Validates subscription status for marketplace requests

### Data Flow: Subscription Purchase

```
User → CLI → SubscriptionService → SubscriptionManager
                                          │
                        ┌─────────────────┼─────────────────┐
                        │                 │                 │
                        ▼                 ▼                 ▼
              AgreementBuilder   FulfillmentBuilder   BalanceChecker
                        │                 │                 │
                        └─────────────────┼─────────────────┘
                                          │
                                          ▼
                              Infrastructure Layer
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    │                     │                     │
                    ▼                     ▼                     ▼
            NVMContractFactory    NVMConfig          Executor
                    │                     │                     │
            (11 contracts)      (chain settings)    (agent/client)
```

### Chain Support

NVM subscriptions are supported on:
- **Gnosis** (chain_id: 100): Native xDAI payments
- **Base** (chain_id: 8453): USDC token payments

Configuration stored in:
- `infrastructure/nvm/resources/envs/gnosis.env`
- `infrastructure/nvm/resources/envs/base.env`
- `infrastructure/nvm/resources/networks.json`

### Backward Compatibility

The deprecated monolithic module (`nvm_subscription/__init__.py`) remains for backward compatibility:
- Emits `DeprecationWarning` when called
- Wraps new `SubscriptionService`
- Will be removed in future release

New code should use `SubscriptionService` directly.

## Testing Strategy

### Unit Tests

Each layer has comprehensive unit tests:

```
tests/unit/
├── utils/           # 75 tests - validators, errors
├── domain/          # 36 tests - strategies, watchers
├── services/        # 11 tests - service orchestration
└── infrastructure/  # 42 tests - adapters, clients
```

### Testing Patterns

**1. Mock External Dependencies**
```python
def test_native_payment_strategy():
    mock_ledger_api = MagicMock()
    mock_ledger_api.get_balance.return_value = 10**18

    strategy = NativePaymentStrategy(mock_ledger_api)
    assert strategy.check_balance(address, amount) is True
```

**2. Test Strategy Interfaces**
```python
def test_payment_strategy_interface():
    strategy = PaymentStrategyFactory.create(
        PaymentType.NATIVE, mock_ledger_api
    )
    # Strategy should implement the interface
    assert isinstance(strategy, PaymentStrategy)
    assert hasattr(strategy, 'approve_if_needed')
```

**3. Test Error Handling**
```python
def test_invalid_payment_type():
    with pytest.raises(ValidationError, match="Invalid payment type"):
        validate_payment_type("invalid")
```

**4. Test Async Components**
```python
@pytest.mark.anyio
async def test_delivery_watcher():
    watcher = OnchainDeliveryWatcher(mock_contract, mock_api)
    result = await watcher.watch([request_id])
    assert request_id in result
```

### Test Coverage

- **Utils**: 100% coverage (validators, errors, constants)
- **Domain**: High coverage (strategies, watchers, managers)
- **Services**: Core flows covered (request, deposit, tool ops)
- **Infrastructure**: Adapter logic covered (clients, loaders)

### Running Tests

```bash
# Run all unit tests (exclude trio backend)
poetry run pytest tests/unit/ -k "not trio"

# Run specific layer
poetry run pytest tests/unit/domain/

# Run with coverage
poetry run pytest tests/unit/ --cov=mech_client --cov-report=html

# Run linters
tox -e black-check,isort-check,flake8,mypy,pylint
```

## Best Practices

### 1. Adding New Features

When adding a new feature:
1. Start with domain layer (business logic)
2. Create abstractions for external dependencies
3. Implement infrastructure adapters
4. Add service orchestration
5. Expose via CLI
6. Write tests at each layer

### 2. Modifying Existing Code

When modifying code:
1. Check which layer the change belongs to
2. Maintain layer boundaries
3. Update tests first (TDD)
4. Ensure linters pass
5. Update documentation if interfaces change

### 3. Error Handling

- Use custom exceptions from `utils/errors/`
- Provide context in error messages
- Handle errors at appropriate layer
- Don't swallow exceptions silently

### 4. Configuration

- **Use `EnvironmentConfig` for all environment variables** (never `os.getenv()` or `os.environ[]`)
- Keep defaults in `configs/mechs.json`
- Use `__post_init__` to load from `EnvironmentConfig` and apply overrides
- Document all configuration options in `EnvironmentConfig` class

### 5. Dependencies

- Inject dependencies via constructors
- Use interfaces (ABC) for external dependencies
- Keep infrastructure at edges
- Avoid global state

## Further Reading

- [../CLAUDE.md](../CLAUDE.md) - Development guidelines and patterns for Claude Code
- [TESTING.md](./TESTING.md) - Comprehensive testing guide
- [COMMANDS.md](./COMMANDS.md) - Command reference with dependency diagrams
- [../README.md](../README.md) - User documentation and examples
