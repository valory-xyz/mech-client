# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### ✨ Added

#### NVM Subscription Module Refactoring
- **Layered Architecture Alignment**: Refactored NVM subscription module to follow v0.17.0 layered architecture
  - **Infrastructure Layer** (`infrastructure/nvm/`): Configuration, contract wrappers, and resources
    - `NVMConfig` dataclass with `from_chain()` loader
    - 11 refactored contract wrappers (simplified, no transaction building)
    - `NVMContractFactory` for creating contract instances
    - Chain-specific configuration files (gnosis.env, base.env, networks.json)
  - **Domain Layer** (`domain/subscription/`): Business logic components
    - `SubscriptionManager`: Orchestrates 3-transaction purchase workflow
    - `AgreementBuilder`: Builds agreement data structure
    - `FulfillmentBuilder`: Builds fulfillment parameters
    - `SubscriptionBalanceChecker`: Validates sufficient balance
  - **Service Layer** (`services/subscription_service.py`): Service orchestration
    - Coordinates dependencies and workflow execution
    - Uses `ExecutorFactory` for agent/client mode handling
- **Backward Compatibility**: Deprecated monolithic `nvm_subscription/__init__.py` module
  - Emits `DeprecationWarning` when used
  - Wraps new `SubscriptionService` internally
  - Will be removed in future release
- **Comprehensive Tests**: 14 unit tests for NVM subscription components
  - Infrastructure layer tests (config, contracts)
  - Domain layer tests (builders, manager, balance checker)
  - Service layer tests (subscription service)

#### Documentation Organization
- **docs/ Folder Structure**: Consolidated all documentation in `docs/` folder
  - Moved `ARCHITECTURE.md` → `docs/ARCHITECTURE.md`
  - Moved `TESTING.md` → `docs/TESTING.md`
  - Moved `TOKEN_APPROVAL_AGENT_MODE_ISSUE.md` → `docs/TOKEN_APPROVAL_AGENT_MODE_ISSUE.md`
  - Created `docs/COMMANDS.md` with command dependency diagrams
- **Optimized CLAUDE.md**: Reduced from 1,075 to 323 lines (70% reduction)
  - Extracted command diagrams to `docs/COMMANDS.md`
  - Removed duplicate architecture content
  - Focused on essential development patterns and gotchas
- **Updated Cross-References**: All documentation files reference each other correctly

### 🔧 Changed

- **NVM Subscription Purchase**: Now uses layered architecture with strategy patterns
  - Supports both agent mode (Safe multisig) and client mode (EOA)
  - Chain-specific payment handling (native xDAI for Gnosis, USDC for Base)
  - Improved error handling and validation

## [0.17.2] - 2025-02-06

### ✨ Added

- **Marketplace URL Display**: Setup command now displays marketplace URL for deployed services
  - Shows direct link to service on Olas Marketplace
  - Format: `https://marketplace.olas.network/{chain}/ai-agents/{token}`

### 🔧 Changed

- **ChainType Enum Handling**: Fixed Safe address retrieval to work with ChainType enum keys
  - Iterate over enum keys and match `chain_type.value` against string chain configs
  - Resolves issues with wallet.safes dictionary access

### 🗑️ Removed

- **IPFS to-png Command**: Removed `mechx ipfs to-png` command
  - Command was not widely used and added unnecessary complexity
  - Users can use external tools for image conversion

### 🐛 Fixed

- **Release Workflow**: Set `skip_existing: false` to fail explicitly on duplicate PyPI versions
  - Prevents silent success when version already exists on PyPI
  - Ensures deployment issues are visible

## [0.17.1] - 2025-02-06

### 🐛 Fixed

- **Setup Command**: Fixed agent mode setup and messaging
  - Improved error messages for setup failures
  - Better guidance for users when setup encounters issues
- **Agent Mode Messaging**: Fixed "Agent mode enabled" message display
  - Only shows for wallet commands (request, deposit, subscription)
  - Read-only commands (mech, tool) and utility commands (ipfs) work independently

## [0.17.0] - 2025-02-06

### 🏗️ Major Architectural Refactor

Version 0.17.0 introduces a comprehensive architectural refactoring that separates concerns into distinct layers and introduces modern design patterns. This is a **breaking release** for library users but maintains CLI compatibility where possible.

### ✨ Added

#### Architecture & Design
- **Layered Architecture**: Introduced 4-layer architecture (CLI → Service → Domain → Infrastructure)
- **Service Layer**: New service classes for business logic orchestration
  - `MarketplaceService`: Marketplace request operations
  - `ToolService`: Tool discovery and management
  - `DepositService`: Balance deposit operations
  - `SetupService`: Agent mode setup
  - `SubscriptionService`: NVM subscription management
- **Strategy Pattern**: Flexible payment, execution, and delivery strategies
  - `PaymentStrategyFactory`: Creates payment strategies based on type
  - `ExecutorFactory`: Creates execution strategies (client/agent mode)
  - `DeliveryWatcherFactory`: Creates delivery watchers (onchain/offchain)
- **Domain Layer**: Core business logic and models
  - Payment strategies (Native, Token, NVM)
  - Execution strategies (Client, Agent)
  - Delivery watchers (Onchain, Offchain)
  - Tool models (`ToolInfo`, `ToolSchema`)
- **Infrastructure Layer**: External system adapters
  - Blockchain client (`BlockchainClient`)
  - IPFS client (`IPFSClient`)
  - Subgraph client (`SubgraphClient`)
  - Safe client (`SafeClient`)
  - Configuration loader (`get_mech_config`)

#### CLI Improvements
- **Nested Command Groups**: Reorganized CLI with intuitive command hierarchy
  - `mechx deposit native|token` (was `mechx deposit-native/deposit-token`)
  - `mechx tool list|describe|schema` (was `mechx tools-for-marketplace-mech`, etc.)
  - `mechx mech list` (was `mechx fetch-mm-mechs-info`)
  - `mechx ipfs upload|upload-prompt|to-png` (was separate commands)
  - `mechx subscription purchase` (was `mechx purchase-nvm-subscription`)
  - `mechx setup` (was `mechx setup-agent-mode`)
  - `mechx request` (was `mechx interact`)
- **Improved Help Text**: Better documentation and examples in CLI help messages
- **Consistent Error Handling**: Comprehensive error handling with actionable solutions

#### Testing & Quality
- **Comprehensive Test Suite**: 164 tests with ~40% coverage
  - Unit tests for all service layer components
  - Unit tests for payment strategies
  - Unit tests for execution strategies
  - Unit tests for delivery watchers
  - Unit tests for validators and utilities
- **CI/CD Improvements**: GitHub Actions workflow with Python 3.10 & 3.11 matrix
- **Perfect Linter Scores**: Pylint 10.00/10, all linters passing
- **Type Safety**: Comprehensive type hints throughout codebase

#### Documentation
- **docs/ARCHITECTURE.md**: Comprehensive architecture guide with diagrams
- **docs/TESTING.md**: Testing guide for contributors
- **MIGRATION.md**: Detailed migration guide from pre-v0.17.0
- **Updated CLAUDE.md**: Development guidelines for Claude Code
- **Updated README.md**: New examples and command structure

#### Public API
- **Exposed Public API**: Library users can now easily import services
  ```python
  from mech_client import (
      MarketplaceService,
      ToolService,
      DepositService,
      PaymentType,
      get_mech_config,
      # ... and more
  )
  ```
- **Custom Exceptions**: Specific exception types for better error handling
  - `MechClientError`: Base exception
  - `RpcError`, `SubgraphError`, `ContractError`
  - `ValidationError`, `ConfigurationError`, `TransactionError`
  - `IPFSError`, `ToolError`, `AgentModeError`, `PaymentError`
  - `DeliveryTimeoutError`

### 🔧 Changed

#### Breaking Changes - CLI

**Command Name Changes** (old → new):
- `setup-agent-mode` → `setup`
- `interact` → `request`
- `fetch-mm-mechs-info` → `mech list`
- `deposit-native` → `deposit native`
- `deposit-token` → `deposit token`
- `purchase-nvm-subscription` → `subscription purchase`
- `tools-for-marketplace-mech` → `tool list`
- `tool-description-for-marketplace-mech` → `tool describe`
- `tool-io-schema-for-marketplace-mech` → `tool schema`
- `prompt-to-ipfs` → `ipfs upload-prompt`
- `push-to-ipfs` → `ipfs upload`
- `to-png` → `ipfs to-png`

**Migration**: Update your scripts and aliases to use the new command names. The CLI will not provide backward compatibility for old command names.

#### Breaking Changes - Programmatic API

**Module Relocations**:
- `mech_client.interact` → `mech_client.services.marketplace_service`
- `mech_client.mech_tool` → `mech_client.services.tool_service`
- `mech_client.subgraph` → `mech_client.infrastructure.subgraph`
- `mech_client.ipfs` → `mech_client.infrastructure.ipfs`
- `mech_client.safe_tx` → `mech_client.infrastructure.blockchain.safe_client`

**API Changes**:
- Functions replaced with service classes and methods
- Payment types now use `PaymentType` enum instead of strings
- Delivery watching now uses async/await
- Configuration access via `get_mech_config()` instead of direct dict access

**Migration**: See [MIGRATION.md](./MIGRATION.md) for detailed migration guide with code examples.

#### Improved

- **Error Messages**: More descriptive error messages with actionable solutions
- **Validation**: Centralized validation functions with consistent error handling
- **Configuration**: Environment variable overrides with `MECHX_*` prefix
- **Logging**: Structured logging with configurable log levels
- **Code Organization**: Clear separation of concerns across layers
- **Maintainability**: Reduced code duplication and improved modularity

### 🗑️ Removed

#### Deleted Files
- `mech_client/interact.py` (replaced by `services/marketplace_service.py`)
- `mech_client/mech_tool.py` (replaced by `services/tool_service.py`)
- `mech_client/mech_marketplace_tool_management.py` (functionality moved to domain layer)
- `mech_client/mech_marketplace_subgraph.py` (replaced by `infrastructure/subgraph`)
- `mech_client/prompt_to_ipfs.py` (replaced by `infrastructure/ipfs`)
- `mech_client/push_to_ipfs.py` (replaced by `infrastructure/ipfs`)
- `mech_client/to_png.py` (replaced by `infrastructure/ipfs`)
- `mech_client/fetch_ipfs_hash.py` (unused, removed)

**Total**: 6 files deleted, 626 lines removed, replaced with ~1000+ lines of better-organized code.

### 📊 Statistics

- **Lines of code**: Net +400 lines (removed 626, added ~1000)
- **Test coverage**: ~40% (164 tests)
- **Pylint score**: 10.00/10
- **Python versions**: 3.10, 3.11
- **Architecture layers**: 4 (CLI, Service, Domain, Infrastructure)
- **Services**: 5 (Marketplace, Tool, Deposit, Setup, Subscription)
- **Strategies**: 7 (3 payment + 2 execution + 2 delivery)
- **Factories**: 3 (Payment, Executor, DeliveryWatcher)
- **Custom exceptions**: 11 specific exception types
- **Documentation files**: 5 (docs/ARCHITECTURE.md, docs/TESTING.md, MIGRATION.md, CLAUDE.md, README.md)

### 🔗 Migration Guide

For detailed migration instructions, code examples, and best practices, see:
- **[MIGRATION.md](./MIGRATION.md)** - Complete migration guide from pre-v0.17.0
- **[docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md)** - Architecture overview and patterns
- **[docs/TESTING.md](./docs/TESTING.md)** - Testing guide for contributors

### ⚠️ Important Notes

1. **CLI Commands**: Update all scripts to use new nested command structure
2. **Programmatic API**: Library users must migrate to service-based API
3. **Python Version**: Requires Python >=3.10, <3.12
4. **CI/CD**: Tests exclude trio backend by default (164 asyncio tests)
5. **Linters**: All code must pass pylint 10.00/10 and other linters

### 🙏 Acknowledgments

This refactor was a collaborative effort to modernize the codebase and improve developer experience. Special thanks to all contributors and the Valory AG team.

---

## [0.16.x] and Earlier

For changes in versions prior to 0.17.0, please refer to the git history or contact the maintainers.

[0.17.0]: https://github.com/valory-xyz/mech-client/compare/v0.16.0...v0.17.0
