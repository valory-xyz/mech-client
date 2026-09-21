# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.23.3] - 2026-09-21

### ✨ Added

- `mechx request` states the Valory Mech Terms before anything is signed, when the Mech is operated by Valory. Identification is a DNS lookup of the Mech's own name under `mech.valory.xyz`, so the answer does not depend on the Mech being up. It fails closed: a name that does not resolve, a timed-out lookup, or a zone that answers every name all mean the Mech is not identified as Valory operated.
- `mechx mech list` gains an Operator column, marking the Mechs the same check confirms. A Mech that is not confirmed is left blank rather than labelled, since an independent Mech and a lookup that could not complete are indistinguishable to the check.
- `identify()` in `mech_client.domain.identification` returns `VALORY`, `NOT_VALORY` or `UNKNOWN`, so a caller can tell a Mech Valory does not operate from a check that could not complete. `is_valory_operated()` is unchanged.
- `ToolManager.terms_report(mech_address, metadata)` returns, for an already fetched metadata document, `valory_operated`, the Valory terms statement as `terms` for a Valory Mech, an `identification_note` when the check could not tell, and the operator's published link as `terms_url`. The chain comes from the manager, and the rule that only a Valory Mech gets the statement lives here, so integrations do not reimplement it.

### 🔧 Changed

- For a Mech operated by someone else, or one the check could not identify, `mechx request` shows the terms link the operator published in `termsUrl`, as published, instead of stating that sending the request means agreeing to it. Those terms are that operator's to state. The link is also still shown in the Terms column of `mechx mech list`.
- `ToolManager.extract_terms_url()` only returns an `https` link with a host, no whitespace or control characters, and at most 2048 characters. Anything else in an operator's `termsUrl` is dropped, including in the Terms column of `mechx mech list`.
- A lookup that fails or times out now logs a warning; only a name that does not exist stays at debug level. Lookups share one pool capped at 8 threads, and a lookup still queued when its caller gives up is cancelled.

## [0.23.2] - 2026-09-16

### ✨ Added

- `mechx mech list` shows a Terms column, read from the `termsUrl` field of each mech's published metadata.
- `mechx request` logs the mech operator's terms link before anything is signed, on both the on-chain and the off-chain path, or states that the mech publishes none.
- `ToolManager.extract_terms_url()` reads the link from a fetched metadata document, for library users.
- `send_request` reads the mech's metadata once per request; the tool check, the terms notice and the off-chain URL lookup all use that one document.

### 🐛 Fixed

- The off-chain path logged that the prompt would be uploaded to a gateway. It never leaves the requester on that path; only its content CID is signed. The log now says so.

## [0.23.1] - 2026-09-16

### ✨ Added

- **Agent mode on Robinhood Chain (4663)**: `mechx setup --chain-config robinhood` creates the service and its Safe, funded with USDG (the chain's USDC payment type) for requests and ETH for the agent's gas.

### 🔧 Changed

- `olas-operate-middleware>=0.15.39`, the first release whose quickstart tables know Robinhood. 0.15.38 carried the chain in its ledger profiles only, so `mechx setup --chain-config robinhood` exited with a `KeyError` before printing an address.

## [0.23.0] - 2026-09-16

### ✨ Added

- **`mech list` on Robinhood** via the marketplace squid. Every chain in `mechs.json` now names its `subgraph_dialect` (`"graph"` or `"squid"`), and `mech list` sends the matching sort syntax.

### 🔧 Changed

- `olas-operate-middleware>=0.15.38` and `open-aea-helpers==0.21.29` (open-autonomy 0.21.29). These carry Robinhood in the middleware's ledger profiles, though not in its quickstart tables, so `mechx setup` still doesn't support the chain. open-autonomy 0.21.27 made the Solana plugin an optional extra ([valory-xyz/open-autonomy#2541](https://github.com/valory-xyz/open-autonomy/pull/2541)), so it and its transitive dependencies are no longer installed.
- `SubgraphClient` now requires a `dialect` argument (`"graph"` or `"squid"`) and rejects an unknown one when built. A `mechs.json` entry with a missing or unknown `subgraph_dialect` fails when the config loads. `query_mechs` rejects an `order_by` that isn't a field name and an `order_direction` other than `asc`/`desc`.
- `MechConfig` requires `subgraph_dialect`, placed before `priority_mech_address`, so positional construction shifts. `query_mm_mechs_info` returns an empty list instead of `None` when a chain has no delivering mechs, and raises `SubgraphError` instead of `KeyError` or `TypeError` on a record it can't read.

## [0.22.1] - 2026-09-14

### ✨ Added

- **Robinhood Chain (4663)** in client mode: marketplace requests (on-chain and offchain), native and USDC-type deposits (USDG on Robinhood), and `tool` commands. Agent mode (`setup`) and `mech list` are not available on Robinhood yet: the operate middleware does not support the chain, and there is no marketplace subgraph.

## [0.22.0] - 2026-08-12

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

- **Delivery results are now the delivered content, in one shape** (breaking, [#250](https://github.com/valory-xyz/mech-client/issues/250))
  - `send_request` now returns a single `deliveries[request_id]` key holding a
    `DeliveryResult`, replacing `delivery_results`. Previously the on-chain flow returned
    a URL string and the off-chain flow returned the mech's raw envelope, so a caller
    could not write one handler.
  - The on-chain URL addressed the delivery *directory*, which serves an HTML listing;
    the result file inside is named after the request ID in decimal. Both watchers now
    build that full path and read the file themselves.
  - `DeliveryResult.data` is the parsed result file, `None` if the gateway could not be
    read. `DeliveryResult.url` is the result-file URL to retry with, `None` for off-chain
    mechs that answer inline. Pairing content with its location in one object keeps the
    two from drifting apart per request.
  - `mechx request` prints the mech's answer (decoding the JSON-encoded `result` field
    when the payload has one, otherwise the payload itself) followed by the result-file
    URL.
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
- **docs/COMMANDS.md**: Command reference with dependency diagrams
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

**Migration**: See [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) for architecture details and code examples.

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
- **Documentation files**: 5 (docs/ARCHITECTURE.md, docs/TESTING.md, docs/COMMANDS.md, CLAUDE.md, README.md)

### 🔗 Documentation

For detailed information about the architecture and development:
- **[docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md)** - Architecture overview and patterns
- **[docs/TESTING.md](./docs/TESTING.md)** - Testing guide for contributors
- **[docs/COMMANDS.md](./docs/COMMANDS.md)** - Command reference and dependencies

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
