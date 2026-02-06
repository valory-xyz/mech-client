# Mech Client Refactoring Plan

## Executive Summary

This document outlines a comprehensive refactoring of the mech-client codebase to adopt a modern, layered architecture. The goal is to improve maintainability, testability, and extensibility while preserving all existing functionality.

## Current State Analysis

### Issues Identified
1. **Large monolithic files**: `cli.py` (1,508 LOC), `marketplace_interact.py` (1,213 LOC)
2. **Tight coupling**: Payment logic, transaction execution, and CLI all intertwined
3. **Code duplication**: Agent/client mode branching in 7+ functions, error handling repeated 10+ times
4. **Scattered concerns**: Payment logic split across 3+ files, contract addresses duplicated
5. **Limited testability**: Business logic mixed with CLI and output formatting

### Metrics
- **Total LOC**: ~4,400 (production code)
- **Code Duplication**: Estimated 30-40% can be eliminated
- **Large Functions**: 3 functions >200 LOC, 10+ functions >100 LOC
- **Cyclomatic Complexity**: High in `marketplace_interact()` and `request()`

## Target Architecture

### Layered Architecture Pattern

```
┌──────────────────────────────────────────────────────────┐
│                     CLI Layer                             │
│  (cli/, commands/ - thin routing, validation only)       │
└──────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────┐
│                  Service Layer                            │
│  (services/ - business logic orchestration)              │
│  • marketplace_service.py                                │
│  • tool_service.py                                       │
│  • deposit_service.py                                    │
│  • subscription_service.py                               │
└──────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────┐
│                  Domain Layer                             │
│  (domain/ - core business entities)                      │
│  • payment/ (strategies: native, token, nvm)            │
│  • execution/ (strategies: client_mode, agent_mode)      │
│  • tools/ (tool management, validation)                  │
│  • delivery/ (on-chain, off-chain delivery)             │
└──────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────┐
│               Infrastructure Layer                        │
│  (infrastructure/ - external integrations)               │
│  • blockchain/ (contracts, web3, safe)                   │
│  • ipfs/ (upload, download, conversion)                  │
│  • subgraph/ (GraphQL queries)                           │
│  • config/ (chain configs, ABIs)                         │
└──────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────┐
│                  Shared Utilities                         │
│  (utils/ - cross-cutting concerns)                       │
│  • errors/ (exception handling)                          │
│  • validators/ (input validation)                        │
│  • logger/ (structured logging)                          │
└──────────────────────────────────────────────────────────┘
```

### Proposed Directory Structure

```
mech_client/
├── __init__.py
├── __main__.py                     # Entry point (mechx command)
│
├── cli/                            # CLI Layer (commands + routing)
│   ├── __init__.py
│   ├── main.py                     # Main CLI group, version, client/agent mode
│   ├── commands/
│   │   ├── __init__.py
│   │   ├── setup.py                # mechx setup
│   │   ├── request.py              # mechx request
│   │   ├── mech.py                 # mechx mech [list]
│   │   ├── tool.py                 # mechx tool [list|describe|schema]
│   │   ├── deposit.py              # mechx deposit [native|token]
│   │   ├── subscription.py         # mechx subscription [purchase]
│   │   └── ipfs.py                 # mechx ipfs [upload|upload-prompt|to-png]
│   └── validators.py               # CLI input validators
│
├── services/                       # Service Layer (business orchestration)
│   ├── __init__.py
│   ├── marketplace_service.py      # Orchestrate marketplace requests
│   ├── tool_service.py             # Tool discovery & validation
│   ├── deposit_service.py          # Deposit operations
│   ├── subscription_service.py     # NVM subscription management
│   └── setup_service.py            # Agent mode setup orchestration
│
├── domain/                         # Domain Layer (business logic)
│   ├── __init__.py
│   │
│   ├── payment/                    # Payment strategies
│   │   ├── __init__.py
│   │   ├── base.py                 # PaymentStrategy interface
│   │   ├── native.py               # NativePaymentStrategy
│   │   ├── token.py                # TokenPaymentStrategy
│   │   ├── nvm.py                  # NVMPaymentStrategy
│   │   └── factory.py              # PaymentStrategyFactory
│   │
│   ├── execution/                  # Transaction execution strategies
│   │   ├── __init__.py
│   │   ├── base.py                 # TransactionExecutor interface
│   │   ├── client_executor.py      # EOA-based execution
│   │   ├── agent_executor.py       # Safe-based execution
│   │   └── factory.py              # ExecutorFactory
│   │
│   ├── tools/                      # Tool management
│   │   ├── __init__.py
│   │   ├── manager.py              # ToolManager (discovery, caching)
│   │   ├── models.py               # ToolInfo, ToolSchema dataclasses
│   │   ├── validator.py            # Tool validation logic
│   │   └── formatter.py            # Schema formatting for CLI
│   │
│   ├── delivery/                   # Delivery mechanisms
│   │   ├── __init__.py
│   │   ├── base.py                 # DeliveryWatcher interface
│   │   ├── onchain_watcher.py      # On-chain delivery (marketplace)
│   │   ├── offchain_watcher.py     # Off-chain delivery (HTTP)
│   │   └── factory.py              # DeliveryWatcherFactory
│   │
│   └── models.py                   # Shared domain models (RequestConfig, etc.)
│
├── infrastructure/                 # Infrastructure Layer (external deps)
│   ├── __init__.py
│   │
│   ├── blockchain/                 # Blockchain interactions
│   │   ├── __init__.py
│   │   ├── contracts/
│   │   │   ├── __init__.py
│   │   │   ├── base.py             # BaseContract wrapper
│   │   │   ├── marketplace.py      # MechMarketplace wrapper
│   │   │   ├── balance_tracker.py  # BalanceTracker wrappers
│   │   │   ├── token.py            # ERC20 token wrapper
│   │   │   └── registry.py         # ContractRegistry (address lookup)
│   │   ├── safe_client.py          # Safe multisig client
│   │   ├── web3_client.py          # Web3 connection management
│   │   ├── receipt_waiter.py       # Transaction receipt polling
│   │   └── abi_loader.py           # ABI loading utilities
│   │
│   ├── ipfs/                       # IPFS gateway client
│   │   ├── __init__.py
│   │   ├── client.py               # IPFSClient (upload/download)
│   │   ├── metadata.py             # Metadata formatting
│   │   └── converters.py           # Format converters (PNG, etc.)
│   │
│   ├── subgraph/                   # Subgraph queries
│   │   ├── __init__.py
│   │   ├── client.py               # GraphQL client
│   │   └── queries.py              # Query definitions
│   │
│   ├── operate/                    # Operate middleware integration
│   │   ├── __init__.py
│   │   ├── manager.py              # Operate setup & config
│   │   └── key_manager.py          # Key extraction helpers
│   │
│   └── config/                     # Configuration management
│       ├── __init__.py
│       ├── chain_config.py         # Chain configuration (MechConfig)
│       ├── contract_addresses.py   # Contract address registry
│       ├── payment_config.py       # Payment type definitions
│       └── loader.py               # Config file loader (mechs.json)
│
├── utils/                          # Shared Utilities
│   ├── __init__.py
│   ├── errors/                     # Error handling
│   │   ├── __init__.py
│   │   ├── exceptions.py           # Custom exceptions
│   │   ├── handlers.py             # Error handlers & decorators
│   │   └── messages.py             # User-friendly error messages
│   ├── validators.py               # Business validators
│   ├── logger.py                   # Logging configuration
│   └── constants.py                # Shared constants
│
├── nvm_subscription/               # NVM module (keep as-is, integrate later)
│   └── ...                         # (existing structure)
│
├── abis/                           # Contract ABIs (keep as-is)
├── configs/                        # Config files (keep as-is)
│   └── mechs.json
└── config/                         # Service templates (keep as-is)
    └── *.json
```

### Total Files Impact
- **Before**: 18 Python files at root level
- **After**: ~45 Python files organized into 25 modules
- **Line reduction**: Expect 20-30% reduction through eliminating duplication

## Implementation Strategy

### Phase 1: Infrastructure Layer (Week 1)
**Goal**: Extract all external dependencies into clean interfaces

1. **Create `infrastructure/config/`**
   - Move `interact.py` → `chain_config.py` (MechConfig, LedgerConfig)
   - Move `contract_addresses.py` → `contract_addresses.py` (preserve mappings)
   - Create `loader.py` for mechs.json loading
   - Create `payment_config.py` for PaymentType enum

2. **Create `infrastructure/blockchain/`**
   - Extract contract interaction from `interact.py` → `contracts/base.py`
   - Create wrappers: `marketplace.py`, `balance_tracker.py`, `token.py`
   - Move `safe.py` → `safe_client.py`
   - Move `wss.py` → `receipt_waiter.py`
   - Create `abi_loader.py` for ABI management
   - Create `web3_client.py` for Web3 initialization

3. **Create `infrastructure/ipfs/`**
   - Move `push_to_ipfs.py` → `client.py` (generic upload/download)
   - Move `prompt_to_ipfs.py` → `metadata.py` (prompt metadata)
   - Move `to_png.py` → `converters.py` (PNG conversion)
   - Move `fetch_ipfs_hash.py` → `client.py` (hash calculation)

4. **Create `infrastructure/subgraph/`**
   - Move `mech_marketplace_subgraph.py` → `client.py` + `queries.py`

### Phase 2: Domain Layer (Week 2)
**Goal**: Extract core business logic with clear abstractions

1. **Create `domain/payment/`**
   - Define `PaymentStrategy` interface (approve, deposit, check_balance)
   - Implement `NativePaymentStrategy`, `TokenPaymentStrategy`, `NVMPaymentStrategy`
   - Create `PaymentStrategyFactory` (select based on PaymentType)
   - Extract logic from `marketplace_interact.py` and `deposits.py`

2. **Create `domain/execution/`**
   - Define `TransactionExecutor` interface (execute_transaction, build_tx)
   - Implement `ClientExecutor` (EOA signing), `AgentExecutor` (Safe multisig)
   - Create `ExecutorFactory` (select based on agent_mode flag)

3. **Create `domain/tools/`**
   - Move `mech_marketplace_tool_management.py` → `manager.py` + `models.py`
   - Create `validator.py` for tool validation logic
   - Create `formatter.py` for CLI output formatting

4. **Create `domain/delivery/`**
   - Extract from `delivery.py` → `onchain_watcher.py`
   - Create `offchain_watcher.py` for HTTP mech delivery
   - Define `DeliveryWatcher` interface

### Phase 3: Service Layer (Week 3)
**Goal**: Orchestrate domain operations, replace monolithic functions

1. **Create `services/marketplace_service.py`**
   - Replace `marketplace_interact()` function
   - Methods: `send_request()`, `send_batch_request()`, `verify_tools()`
   - Compose payment strategies, execution strategies, delivery watchers
   - Extract from `marketplace_interact.py` (reduce from 1,213 → ~400 LOC)

2. **Create `services/tool_service.py`**
   - Replace tool management functions
   - Methods: `list_tools()`, `get_description()`, `get_schema()`

3. **Create `services/deposit_service.py`**
   - Replace `deposit_native_main()`, `deposit_token_main()`
   - Methods: `deposit_native()`, `deposit_token()`, `check_balance()`
   - Extract from `deposits.py` (reduce from 501 → ~150 LOC)

4. **Create `services/subscription_service.py`**
   - Wrap `nvm_subscribe_main()`
   - Future: integrate NVM module into domain layer

5. **Create `services/setup_service.py`**
   - Extract setup logic from `cli.py`
   - Wrap Operate middleware calls

### Phase 4: CLI Layer (Week 4)
**Goal**: Thin CLI commands, move all logic to services

1. **Create `cli/main.py`**
   - Move main CLI group from `cli.py`
   - Keep: `@click.group`, version, client_mode flag, context setup

2. **Create `cli/commands/`**
   - Split `cli.py` into separate command files
   - Each command file: 50-100 LOC max
   - Commands call services directly (no business logic)
   - Error handling via decorators from `utils/errors/handlers.py`

3. **Create `cli/validators.py`**
   - Move `validate_chain_config()`, `validate_ethereum_address()`
   - Add other CLI-specific validators

### Phase 5: Shared Utilities (Week 5)
**Goal**: Cross-cutting concerns (errors, logging, validation)

1. **Create `utils/errors/`**
   - `exceptions.py`: Custom exceptions (RpcError, ContractError, etc.)
   - `handlers.py`: Error handler decorators for CLI commands
   - `messages.py`: User-friendly error message templates

2. **Create `utils/validators.py`**
   - Business-level validators (not CLI-specific)
   - Examples: validate_amount, validate_tool_id, validate_payment_type

3. **Create `utils/logger.py`**
   - Structured logging setup
   - Replace print statements with proper logging

4. **Create `utils/constants.py`**
   - Move scattered constants (IPFS_URL_TEMPLATE, MAX_RETRIES, etc.)

### Phase 6: Testing & Documentation (Week 6)
**Goal**: Ensure refactored code works, add tests

1. **Unit Tests**
   - Test each domain strategy independently
   - Test service orchestration logic
   - Test infrastructure clients (mocked)
   - Target: 70% coverage minimum

2. **Integration Tests**
   - Test CLI commands end-to-end (using test RPC)
   - Validate error handling paths

3. **Documentation Updates**
   - Update CLAUDE.md with new architecture
   - Update README.md with examples
   - Create ARCHITECTURE.md explaining layers

4. **Migration Guide**
   - Document internal API changes (for developers)
   - Note: No CLI breaking changes (backward compatible)

## Key Design Decisions

### 1. Strategy Pattern for Payment & Execution
**Rationale**: Eliminate agent/client mode branching and payment type conditionals.

**Before** (scattered in multiple files):
```python
def send_request(...):
    if agent_mode:
        if payment_type == PaymentType.NATIVE:
            # Native agent logic
        elif payment_type == PaymentType.TOKEN:
            # Token agent logic
    else:
        if payment_type == PaymentType.NATIVE:
            # Native client logic
        elif payment_type == PaymentType.TOKEN:
            # Token client logic
```

**After** (clean composition):
```python
def send_request(...):
    payment_strategy = PaymentStrategyFactory.create(payment_type)
    executor = ExecutorFactory.create(agent_mode)

    payment_strategy.prepare(amount, executor)
    tx_hash = executor.execute_transaction(contract, method, args)
    return wait_for_receipt(tx_hash)
```

### 2. Service Layer for Orchestration
**Rationale**: Keep CLI thin, move business logic to testable services.

**Before** (CLI contains business logic):
```python
@cli.command()
def request(...):
    # 180 lines of validation + execution + error handling
    marketplace_interact_(...)  # Another 366 lines
```

**After** (CLI delegates to service):
```python
@cli.command()
@handle_errors  # Decorator handles all errors
def request(...):
    validate_inputs(...)  # 10 lines
    service = MarketplaceService(chain_config, agent_mode)
    result = service.send_request(prompts, tools, priority_mech)
    click.echo(format_result(result))
```

### 3. Dependency Injection for Testability
**Rationale**: Make services testable without mocking global state.

**Example** (`MarketplaceService`):
```python
class MarketplaceService:
    def __init__(
        self,
        chain_config: str,
        agent_mode: bool,
        contract_registry: ContractRegistry,
        ipfs_client: IPFSClient,
        tool_manager: ToolManager,
    ):
        self.chain_config = chain_config
        self.agent_mode = agent_mode
        self.contract_registry = contract_registry
        self.ipfs_client = ipfs_client
        self.tool_manager = tool_manager

    def send_request(...) -> RequestResult:
        # Use injected dependencies
        ...
```

### 4. Contract Wrappers for Type Safety
**Rationale**: Eliminate ABI path duplication, improve type hints.

**Before** (scattered ABI loading):
```python
marketplace_contract = get_contract(
    "MechMarketplace.json",
    mech_config.mech_marketplace_contract,
    ledger_api,
)
```

**After** (typed wrapper):
```python
class MechMarketplaceContract(BaseContract):
    def __init__(self, address: str, web3_client: Web3Client):
        super().__init__(
            abi_path="MechMarketplace.json",
            address=address,
            web3_client=web3_client,
        )

    def request(
        self,
        mech_address: str,
        data_hash: str,
        payment_token: str,
        value: int,
    ) -> TxReceipt:
        # Type-safe method with validation
        ...
```

### 5. Configuration as Single Source of Truth
**Rationale**: Eliminate scattered constants, make chain support explicit.

**Create `ChainConfigManager`**:
```python
class ChainConfigManager:
    def __init__(self):
        self.chains = load_mechs_json()
        self.contract_registry = ContractRegistry()

    def get_chain(self, name: str) -> ChainConfig:
        # Load from mechs.json
        ...

    def get_contract_address(self, chain: str, contract_name: str) -> str:
        # Lookup from registry
        ...

    def supports_marketplace(self, chain: str) -> bool:
        # Check if marketplace deployed
        ...
```

## Benefits of Refactoring

### 1. Maintainability
- **Before**: Change payment logic → edit 3+ files
- **After**: Change payment logic → edit 1 strategy class

### 2. Testability
- **Before**: Testing requires mocking CLI context, RPC, contracts
- **After**: Unit test strategies independently with mocked dependencies

### 3. Extensibility
- **Before**: Add new chain → edit 5+ files with chain IDs
- **After**: Add new chain → add entry to mechs.json + contract addresses

### 4. Readability
- **Before**: `marketplace_interact()` is 366 LOC
- **After**: `MarketplaceService.send_request()` is ~50 LOC (delegates to strategies)

### 5. Error Handling
- **Before**: Duplicate try/except in 10+ CLI commands
- **After**: Single error handler decorator, consistent messages

## Risks & Mitigation

### Risk 1: Breaking Changes
**Mitigation**:
- Keep CLI commands backward compatible (no changes to command structure)
- Internal APIs can change freely (only affects implementation)
- Add deprecation warnings if needed

### Risk 2: Regression Bugs
**Mitigation**:
- Incremental refactoring (one layer at a time)
- Comprehensive testing after each phase
- Manual testing of all CLI commands

### Risk 3: NVM Subscription Module
**Mitigation**:
- Keep `nvm_subscription/` as-is initially
- Integrate gradually after core refactoring complete
- Currently marked as excluded from linting (minimal risk)

### Risk 4: Development Time
**Mitigation**:
- 6-week timeline with clear milestones
- Focus on high-impact areas first (payment, execution strategies)
- Can pause after Phase 3 if needed (domain + infrastructure done)

## Success Metrics

### Code Quality Metrics
- **Target**: Reduce average function LOC from 50 → 25
- **Target**: Reduce cyclomatic complexity by 40%
- **Target**: Eliminate 80% of code duplication
- **Target**: Achieve 70%+ test coverage

### Maintainability Metrics
- **Target**: Add new payment type in <50 LOC
- **Target**: Add new chain support in <20 LOC
- **Target**: Zero pylint warnings, 10.00/10 score maintained

### Performance Metrics
- **Constraint**: No performance degradation (CLI command latency ±5%)
- **Constraint**: Backward compatible (all existing commands work identically)

## Timeline

| **Phase** | **Duration** | **Deliverable** |
|-----------|--------------|-----------------|
| Phase 1: Infrastructure Layer | Week 1 | All external deps extracted, tested |
| Phase 2: Domain Layer | Week 2 | Payment & execution strategies implemented |
| Phase 3: Service Layer | Week 3 | Services replace monolithic functions |
| Phase 4: CLI Layer | Week 4 | CLI commands split, thin routing only |
| Phase 5: Shared Utilities | Week 5 | Error handling, logging, validation |
| Phase 6: Testing & Docs | Week 6 | Tests, docs, migration guide |

**Total Estimated Effort**: 6 weeks (240 hours)

## Next Steps

1. **Review & Approval**: Review this plan with team, adjust as needed
2. **Setup Branch**: Create `refactor/modern-architecture` branch
3. **Start Phase 1**: Begin with infrastructure layer (config, blockchain, IPFS)
4. **Incremental PRs**: Submit small PRs per module (easier review)
5. **Continuous Testing**: Run linters + manual tests after each module

## Questions for Discussion

1. Should we keep backward compatibility with internal APIs, or is this CLI-only?
   - **Recommendation**: CLI-only (internal APIs can change)

2. Should we integrate `nvm_subscription/` module into domain layer now or later?
   - **Recommendation**: Later (Phase 7), keep as-is for now

3. Do we want to add type stubs (`.pyi` files) for better IDE support?
   - **Recommendation**: Yes, but as separate improvement (not blocking)

4. Should we adopt dependency injection framework (e.g., `injector`) or manual DI?
   - **Recommendation**: Manual DI (simpler, no new dependency)

5. Target test coverage percentage?
   - **Recommendation**: 70% minimum, focus on domain + service layers

---

**Document Version**: 1.0
**Author**: Claude Code
**Date**: 2026-02-06
**Status**: Draft - Awaiting Review
