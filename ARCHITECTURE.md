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
- **Utility commands** (no mode): `ipfs upload/upload-prompt/to-png`
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
        ledger_api=ledger_api,
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

        # 5. Execute transaction
        executor = ExecutorFactory.create(
            self.mode, self.ledger_api, self.safe_address
        )
        tx_hash = executor.execute(tx_params)

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
    def execute(self, tx_params: Dict[str, Any]) -> str:
        """Execute transaction. Returns tx_hash."""
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
class MarketplaceService:
    def __init__(
        self,
        ledger_api: EthereumApi,
        ipfs_client: IPFSClient,
        marketplace_contract: Web3Contract,
        # ... other dependencies
    ):
        self.ledger_api = ledger_api
        self.ipfs_client = ipfs_client
        self.marketplace_contract = marketplace_contract
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
| `ReceiptWaiter` | Infrastructure | Transaction receipt polling |

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

- Use environment variables for deployment settings
- Keep defaults in `configs/mechs.json`
- Use `__post_init__` for env var overrides
- Document all configuration options

### 5. Dependencies

- Inject dependencies via constructors
- Use interfaces (ABC) for external dependencies
- Keep infrastructure at edges
- Avoid global state

## Migration Guide

See [MIGRATION.md](./MIGRATION.md) for guidance on migrating from pre-v0.17.0 code to the new architecture.

## Further Reading

- [TESTING.md](./TESTING.md) - Comprehensive testing guide
- [CLAUDE.md](./CLAUDE.md) - Development guidelines for Claude Code
- [README.md](./README.md) - User documentation and examples
- [PHASE6_SUMMARY.md](./PHASE6_SUMMARY.md) - Refactoring progress and statistics
