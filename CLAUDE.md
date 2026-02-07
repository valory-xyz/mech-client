# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Mech Client is a Python CLI tool and library for interacting with AI Mechs (on-chain AI agents) via the Olas (Mech) Marketplace, enabling users to send AI task requests on-chain and receive results through on-chain delivery.

## Command Dependency Diagrams

This section provides visual diagrams showing external resource dependencies and environment variables for each CLI command. Use these during development to understand what each command needs to function.

**Total commands: 11** (10 with detailed diagrams - utility commands have minimal dependencies)

### Legend

```
[Command] → External Resource (Environment Variable if configurable)
├─ Resource Type: description
└─ Contract: contract name
```

### 1. setup

```
mechx setup
├─ HTTP RPC (MECHX_CHAIN_RPC)
│  └─ Blockchain queries for Safe setup
├─ Olas Operate Middleware
│  └─ Service configuration and deployment
└─ Local Files
   ├─ ~/.operate_mech_client/ (service configs)
   └─ .env (OPERATE_PASSWORD)

ENV VARS:
  MECHX_CHAIN_RPC (optional, uses default from mechs.json)
  OPERATE_PASSWORD (loaded from .env or prompted)
```

### 2. request

```
mechx request --priority-mech 0x... --tools tool1 --prompts "..."
├─ HTTP RPC (MECHX_CHAIN_RPC) ← PRIMARY DEPENDENCY
│  ├─ Send transaction (approve, request)
│  ├─ Wait for transaction receipt ← TIMES OUT HERE IF RPC SLOW
│  └─ Poll for Deliver events
├─ IPFS Gateway (https://gateway.autonolas.tech/ipfs/)
│  ├─ Upload: prompt + tool metadata
│  └─ Download: mech response data
├─ Smart Contracts (on-chain)
│  ├─ MechMarketplace: request(), requestBatch()
│  ├─ IMech: paymentType(), serviceId(), maxDeliveryRate()
│  ├─ BalanceTracker: mapRequesterBalances() (if prepaid)
│  ├─ ERC20 Token: approve(), balanceOf() (if token payment)
│  └─ ERC1155: balanceOf() (if NVM subscription)
└─ [If Agent Mode]
   ├─ Safe Multisig (via safe-eth-py)
   └─ Olas Operate Middleware (fetch safe address)

OPTIONAL:
├─ Offchain Mech HTTP (MECHX_MECH_OFFCHAIN_URL)
│  └─ If --use-offchain flag set

ENV VARS:
  MECHX_CHAIN_RPC (required for reliable operation) ← SET THIS
  MECHX_MECH_OFFCHAIN_URL (required if --use-offchain)

NOTES:
  - NO WebSocket (WSS) used for marketplace mechs
  - Delivery watched via HTTP RPC polling only
  - If HTTP RPC is slow/unavailable, command times out at "Waiting for transaction receipt..."
```

### 3. deposit native

```
mechx deposit native --chain-config gnosis --mech-type native --amount 0.01
├─ HTTP RPC (MECHX_CHAIN_RPC)
│  ├─ Check native balance
│  ├─ Send transfer transaction
│  └─ Wait for receipt
└─ Smart Contracts
   ├─ BalanceTrackerFixedPriceNative: deposit()
   └─ [If Agent Mode] Safe: execTransaction()

ENV VARS:
  MECHX_CHAIN_RPC (required)

NOTES:
  - Prepaid balance for marketplace requests
  - Supports both agent mode (Safe) and client mode (EOA)
```

### 4. deposit token

```
mechx deposit token --chain-config gnosis --token-type olas --amount 1000000000000000000
├─ HTTP RPC (MECHX_CHAIN_RPC)
│  ├─ Check ERC20 balance
│  ├─ Send approve() transaction
│  ├─ Send deposit() transaction
│  └─ Wait for receipts
└─ Smart Contracts
   ├─ ERC20 Token: approve(), balanceOf()
   ├─ BalanceTrackerFixedPriceToken: deposit()
   └─ [If Agent Mode] Safe: execTransaction()

ENV VARS:
  MECHX_CHAIN_RPC (required)

SUPPORTED TOKENS:
  - olas: OLAS token (chain-specific address)
  - usdc: USDC token (not available on gnosis)
```

### 5. subscription purchase

```
mechx subscription purchase --chain-config gnosis --mech-type native_nvm
├─ HTTP RPC (MECHX_CHAIN_RPC)
│  └─ Send NVM subscription transaction
├─ Nevermined Network
│  └─ Subscription plan management
└─ Smart Contracts
   ├─ NVM Subscription contracts
   └─ [If Agent Mode] Safe: execTransaction()

ENV VARS:
  MECHX_CHAIN_RPC (required)
  PLAN_DID (from mech_client/nvm_subscription/envs/{chain}.env)
  NETWORK_NAME (from envs)
  CHAIN_ID (from envs)
```

### 6. mech list

```
mechx mech list --chain-config gnosis
├─ Subgraph GraphQL API (MECHX_SUBGRAPH_URL) ← REQUIRED, NO DEFAULT
│  └─ Query: MechsOrderedByServiceDeliveries
│     ├─ Returns: service IDs, addresses, delivery counts
│     └─ Filters: totalDeliveries > 0
└─ [Output references]
   └─ IPFS Gateway links (metadata URLs)

ENV VARS:
  MECHX_SUBGRAPH_URL (REQUIRED - must be set manually)

NOTES:
  - Read-only command, no transactions
  - Does NOT use HTTP RPC
  - Subgraph URL must match chain-config
  - Currently all chains have empty subgraph_url in mechs.json
```

### 7. tool list

```
mechx tool list --agent-id <service_id> --chain-config gnosis
├─ HTTP RPC (MECHX_CHAIN_RPC)
│  └─ Query: ComplementaryMetadataHash contract
└─ External HTTP
   └─ Fetch metadata from tokenURI(service_id)

ENV VARS:
  MECHX_CHAIN_RPC (required)

NOTES:
  - For marketplace mechs only
  - Uses service_id (passed as --agent-id parameter)
```

### 8. tool describe

```
mechx tool describe <tool_id> --chain-config gnosis
├─ HTTP RPC (MECHX_CHAIN_RPC)
│  └─ Query: ComplementaryMetadataHash.tokenURI(service_id)
└─ External HTTP
   └─ Fetch and parse tool metadata

ENV VARS:
  MECHX_CHAIN_RPC (required)

NOTES:
  - tool_id format: "service_id-tool_name"
  - Example: "1-openai-gpt-3.5-turbo"
```

### 9. tool schema

```
mechx tool schema <tool_id> --chain-config gnosis
├─ HTTP RPC (MECHX_CHAIN_RPC)
│  └─ Query: ComplementaryMetadataHash.tokenURI(service_id)
└─ External HTTP
   └─ Fetch and parse tool metadata

ENV VARS:
  MECHX_CHAIN_RPC (required)

NOTES:
  - tool_id format: "service_id-tool_name"
  - Returns input/output schema for the tool
```

### 10. ipfs upload-prompt & ipfs upload

```
mechx ipfs upload-prompt "prompt" "tool"
mechx ipfs upload /path/to/file
└─ IPFS Gateway (https://gateway.autonolas.tech/ipfs/)
   └─ Upload file/metadata

ENV VARS:
  None (uses hardcoded IPFS gateway)

NOTES:
  - Utility commands, no blockchain interaction
  - No RPC or WSS needed
```

## Quick Reference: Environment Variables by Command

| Command | MECHX_CHAIN_RPC | MECHX_SUBGRAPH_URL | MECHX_MECH_OFFCHAIN_URL | OPERATE_PASSWORD |
|---------|----------------|--------------------|-----------------------|------------------|
| setup | ○ | | | ✓ |
| request | ✓ | | ○ | |
| deposit native | ✓ | | | |
| deposit token | ✓ | | | |
| subscription purchase | ✓ | | | |
| mech list | | ✓ | | |
| tool list | ✓ | | | |
| tool describe | ✓ | | | |
| tool schema | ✓ | | | |
| ipfs upload-prompt | | | | |
| ipfs upload | | | | |

**Legend:**
- ✓ = Required for command to work
- ○ = Optional (uses default from mechs.json if not set)
- Empty = Not used

## Common Issues & Solutions

### Issue: "Timeout while waiting for transaction receipt"

**Affected Commands:** request, deposit native, deposit token, subscription purchase

**Cause:** HTTP RPC endpoint is slow, rate-limiting, or unavailable

**Solution:**
```bash
# Set a reliable RPC provider
export MECHX_CHAIN_RPC='https://your-reliable-rpc-provider'

# Examples:
export MECHX_CHAIN_RPC='https://gnosis-mainnet.public.blastapi.io'  # Gnosis
export MECHX_CHAIN_RPC='https://polygon-rpc.com'  # Polygon
export MECHX_CHAIN_RPC='https://mainnet.base.org'  # Base
```

**Why this happens:**
- The `wait_for_receipt()` function polls HTTP RPC to get transaction receipt
- If RPC is slow/down, it times out after 5 minutes (300 seconds)

### Issue: "Subgraph URL not set" (mech list)

**Cause:** MECHX_SUBGRAPH_URL environment variable not set (no default in config)

**Solution:**
```bash
# Gnosis
export MECHX_SUBGRAPH_URL='https://api.subgraph.autonolas.tech/api/proxy/marketplace-gnosis'

# Base
export MECHX_SUBGRAPH_URL='https://api.subgraph.autonolas.tech/api/proxy/marketplace-base'

# Polygon
export MECHX_SUBGRAPH_URL='https://api.subgraph.autonolas.tech/api/proxy/marketplace-polygon'

# Optimism
export MECHX_SUBGRAPH_URL='https://api.subgraph.autonolas.tech/api/proxy/marketplace-optimism'
```

### Issue: "Invalid chain configuration" or "Chain not found"

**Affected Commands:** All commands with --chain-config option

**Cause:** Typo in chain name or unsupported chain

**Solution:**
```bash
# Supported chains: gnosis, base, polygon, optimism
# Use exact chain names:
mechx request --chain-config gnosis ...
```

### Issue: "Permission denied" when reading private key

**Affected Commands:** request, deposit native, deposit token, subscription purchase

**Cause:** Private key file has incorrect permissions or is in a protected directory

**Solution:**
```bash
# Fix file permissions
chmod 600 ethereum_private_key.txt

# Or specify different key file
mechx request --key /path/to/key ...
```

### Issue: "Failed to decrypt private key" or "Incorrect password"

**Affected Commands:** request, deposit native, deposit token, subscription purchase (agent mode)

**Cause:** Wrong password for encrypted keyfile, corrupted keyfile, or invalid keyfile format

**Solution:**
- Verify your OPERATE_PASSWORD in .env file
- Ensure keyfile format is valid (JSON keystore format)
- Try re-creating the agent mode setup if keyfile is corrupted:
```bash
# Re-run setup
mechx setup --chain-config gnosis
```

### Issue: "Invalid tool ID format"

**Affected Commands:** tool describe, tool schema

**Cause:** Incorrect tool ID format provided

**Solution:**
```bash
# Use format "service_id-tool_name"
mechx tool describe 1-openai-gpt-3.5-turbo --chain-config gnosis
```

### Issue: "Chain does not support marketplace deposits" or "NVM subscriptions not available"

**Affected Commands:** deposit native, deposit token, subscription purchase

**Cause:** Chain doesn't have marketplace contract or NVM support deployed

**Solution:**
```bash
# Marketplace deposits supported on: gnosis, base, polygon, optimism
# NVM subscriptions supported on: gnosis, base
# Use a supported chain
```

### Issue: "Smart contract error" or "Insufficient balance"

**Affected Commands:** request, deposit native, deposit token, subscription purchase

**Cause:** ContractLogicError - typically insufficient balance, failed approval, invalid parameters, or contract paused

**Solution:**
```bash
# Check your balance
cast balance <YOUR_ADDRESS> --rpc-url $MECHX_CHAIN_RPC

# For token deposits, ensure you have enough tokens
# Verify you have enough native tokens for gas
# Check if you need to approve tokens first (done automatically but may fail)

# For request command, ensure you have deposited balance or per-request payment
mechx deposit native 1000000000000000000 --chain-config gnosis
```

### Issue: "Transaction validation error" (ValidationError)

**Affected Commands:** request, deposit native, deposit token, subscription purchase

**Cause:** Transaction failed validation before being sent - gas estimation failure, nonce issues, or invalid parameters

**Solution:**
```bash
# Check amount/address format is correct
# Ensure sufficient balance for amount + gas
# Try increasing gas limit
export MECHX_GAS_LIMIT=500000

# Check for nonce issues (pending transactions)
# Clear any stuck transactions in your wallet
```

### Issue: "Tool not found" or "Missing description/schema"

**Affected Commands:** tool describe, tool schema

**Cause:** Tool doesn't exist, tool ID is wrong, or metadata is incomplete

**Solution:**
```bash
# List available tools first
mechx tool list --agent-id 1 --chain-config gnosis

# Then use exact tool ID from the list
mechx tool describe <tool_id_from_list> --chain-config gnosis
```

### Issue: "Missing required environment variable" (NVM subscription)

**Affected Commands:** subscription purchase

**Cause:** Chain-specific .env file missing or incomplete (PLAN_DID, NETWORK_NAME, CHAIN_ID)

**Solution:**
Ensure the chain-specific .env file exists in `mech_client/nvm_subscription/envs/<chain>.env` and contains all required variables: PLAN_DID, NETWORK_NAME, CHAIN_ID. Contact the development team if these files are missing.

## Development Commands

### Installation and Setup

```bash
# Install dependencies and enter virtual environment
poetry install
poetry shell
```

### Code Quality and Linting

**IMPORTANT: Before committing, run ALL linters to ensure code quality:**

```bash
# Run all critical linters (REQUIRED before committing)
# Note: Run liccheck separately to avoid race conditions
tox -e black-check,isort-check,flake8,mypy,pylint,bandit,darglint,vulture && tox -e liccheck

# Or run individually:

# Format code with black
tox -e black

# Check code formatting
tox -e black-check

# Sort imports with isort
tox -e isort

# Check import sorting
tox -e isort-check

# Run flake8 linter
tox -e flake8

# Run type checking with mypy
tox -e mypy

# Run pylint
tox -e pylint

# Check docstrings with darglint
tox -e darglint

# Security checks with bandit
tox -e bandit

# Check for unused code with vulture
tox -e vulture

# Dependency security audit
tox -e safety

# License compliance check
tox -e liccheck
```

**Note:** All linters must pass in CI. See "Key Patterns and Conventions" section #8 for linting approach, including when pylint disable comments are acceptable (must be 10.00/10 for CI).

**Pre-commit checklist:**
- [ ] Run `tox -e black-check,isort-check,flake8,mypy,pylint,bandit,darglint,vulture && tox -e liccheck`
- [ ] All linters pass (no failures)
- [ ] Pylint score is 10.00/10

### Testing

**Note:** This project currently has no unit tests. The `stress_tests/` folder contains only load/performance testing.

#### Stress Testing

The project uses Locust for stress testing the mech marketplace:

```bash
# Run Locust with web UI
locust -f stress_tests/locustfile.py

# Run Locust headless (CLI mode)
locust -f stress_tests/locustfile.py --headless -u 1 -r 1 -t 25m

# Run with CSV export for results
locust -f stress_tests/locustfile.py --headless --only-summary --csv results
```

Note: A `ethereum_private_key.txt` file is required in `stress_tests/` for stress testing.

### Build and Release

```bash
# Build distribution packages
make dist
```

The `make dist` target runs `poetry build` to build sdist and wheel distribution packages.

For releases, manually:
1. Bump version in `pyproject.toml`, `mech_client/__init__.py`, and `SECURITY.md`
2. Run `poetry lock` (updates lock file if dependencies changed)
3. Run `poetry run autonomy packages sync --update-packages` (syncs Open Autonomy packages)
4. Run `make dist` (builds distribution packages)
5. Create release PR and tag

### CLI Tool

The main CLI entry point is `mechx`:

```bash
# Show version
mechx --version

# Show help
mechx --help

# Use client mode (EOA-based) instead of agent mode
mechx --client-mode <command>
```

## Architecture

### Two Operating Modes

The mech-client supports two operating modes for wallet-based commands. Read-only and utility commands work independently of these modes.

#### 1. Agent Mode (Recommended for all chains)

Registers on-chain interactions as an agent in the Olas protocol, using Safe multisig for transactions. Configured via `setup` command and uses the `olas-operate-middleware` package.

**Setup:**
```bash
mechx setup --chain-config gnosis
```

**Usage:** Default for wallet commands (no flag needed)
```bash
mechx request --prompts "..." --tools tool1 --chain-config gnosis
# → Uses agent mode automatically
```

**Requirements:**
- Must run `mechx setup` first
- Creates `~/.operate_mech_client/` directory
- Uses Safe multisig for enhanced security

#### 2. Client Mode

Simple EOA-based interactions without agent registration. Enabled with `--client-mode` flag.

**Usage:**
```bash
mechx --client-mode request --prompts "..." --tools tool1 --chain-config gnosis --key ./key.txt
```

**Requirements:**
- Requires `--key` parameter pointing to private key file
- No setup needed
- Direct EOA transactions (no Safe)

#### Operating Mode by Command Type

| Command Type | Agent Mode | Client Mode | No Mode Required |
|--------------|------------|-------------|------------------|
| **Wallet Commands** | | | |
| `request` | ✅ Default | ✅ With --client-mode | ❌ |
| `deposit native` | ✅ Default | ✅ With --client-mode | ❌ |
| `deposit token` | ✅ Default | ✅ With --client-mode | ❌ |
| `subscription purchase` | ✅ Default | ✅ With --client-mode | ❌ |
| **Read-Only Commands** | | | |
| `mech list` | N/A | N/A | ✅ Works independently |
| `tool list` | N/A | N/A | ✅ Works independently |
| `tool describe` | N/A | N/A | ✅ Works independently |
| `tool schema` | N/A | N/A | ✅ Works independently |
| **Utility Commands** | | | |
| `ipfs upload` | N/A | N/A | ✅ Works independently |
| `ipfs upload-prompt` | N/A | N/A | ✅ Works independently |
| **Setup Command** | | | |
| `setup` | Creates setup | N/A | ✅ Works independently |

**Key Points:**
- Operating modes only apply to wallet commands (request, deposit, subscription)
- Read-only commands (mech, tool) work without any mode setup
- Utility commands (ipfs) work without any mode setup
- The "Agent mode enabled" message only appears for wallet commands when not using --client-mode
- Setup command works independently to create agent mode configuration

### Core Modules

#### CLI Layer (`cli.py`)
Main Click-based CLI interface that routes commands to appropriate modules. Handles:
- Command parsing and validation
- Agent mode vs client mode switching
- Environment setup and configuration loading
- Integration with `olas-operate-middleware` for agent operations

**Validation helpers:**
- `validate_chain_config()`: Validates chain exists in mechs.json config (used in ALL commands)
- `validate_ethereum_address()`: Validates address format and non-zero check

**Error handling pattern:** All CLI commands include:
- HTTP RPC error handling (HTTPError, ConnectionError, Timeout) with `MECHX_CHAIN_RPC` context
- Web3 contract errors (ContractLogicError, ValidationError) with actionable solutions
- Private key errors (PermissionError, ValueError for decryption) with helpful guidance
- Metadata errors (KeyError, JSONDecodeError, IOError) with data source context
- Chain/marketplace/NVM support validation before execution

#### Interaction Layers

**Marketplace Service (`services/marketplace_service.py`)**
- Service layer for marketplace request operations
- Supports multiple payment types (`PaymentType` enum): NATIVE, TOKEN, USDC_TOKEN, NATIVE_NVM, TOKEN_NVM_USDC
- Batch request support (multiple prompts/tools)
- Prepaid and per-request payment models
- Offchain mech support via HTTP endpoints
- Uses payment strategies and execution strategies
- Main method: `send_request()`

**Deposit Service (`services/deposit_service.py`)**
- Service layer for prepaid balance deposit functionality
- Methods: `deposit_native()`, `deposit_token()` for balance deposits
- Supports both agent mode (Safe) and client mode (EOA)
- Handles token approval and balance checking via payment strategies
- Uses execution strategies for transaction submission

**Contract Addresses (`infrastructure/config/contract_addresses.py`)**
- Centralized contract address mappings for all supported chains
- Contains: balance tracker contracts (native, OLAS, USDC), token addresses (OLAS, USDC)
- Single source of truth for all chain-specific contract addresses

**NVM Subscription (`nvm_subscription/`)**
- Nevermined (NVM) subscription management for subscription-based payments
- Main module: `NVMSubscriptionManager` in `manager.py`
- Contract wrappers in `contracts/`: agreement_manager, did_registry, escrow_payment, lock_payment, nft, nft_sales, subscription_provider, token, transfer_nft
- Chain-specific configuration in `envs/`: gnosis.env, base.env
- Network configuration in `resources/networks.json`
- Entry point: `nvm_subscribe_main()` in `__init__.py`

#### Delivery Mechanisms

**Delivery Watchers (`domain/delivery/`)**
- Strategy pattern for delivery watching
- `OnchainDeliveryWatcher`: Polls blockchain for `Deliver` events
- `OffchainDeliveryWatcher`: Watches offchain mech endpoints
- `DeliveryWatcherFactory`: Creates appropriate watcher based on mode
- Async/await pattern for concurrent delivery watching

#### Safe Integration

**Safe Client (`infrastructure/blockchain/safe_client.py`)**
- Gnosis Safe transaction building and execution for agent mode
- Functions: `build_safe_tx()`, `send_safe_tx()`, `get_safe_nonce()`
- Uses `safe-eth-py` library

**Agent Executor (`domain/execution/agent_executor.py`)**
- Execution strategy for agent mode (Safe multisig)
- Integrates with Olas Operate middleware
- Handles Safe transaction building and submission

#### Tool Management

**Tool Service (`services/tool_service.py`)**
- Service layer for tool discovery and management
- Methods: `list_tools()`, `get_description()`, `get_tools_info()`, `format_input_schema()`, `format_output_schema()`
- Uses `ToolInfo`, `ToolsForMarketplaceMech`, `ToolSchema` dataclasses

**Tool Manager (`domain/tools/manager.py`)**
- Domain logic for fetching and parsing tool metadata
- Queries ComplementaryMetadataHash contract for tool information
- Parses tool schemas and descriptions from metadata

#### Blockchain Interaction

**Subgraph Client (`infrastructure/subgraph/`)**
- `SubgraphClient`: GraphQL client for subgraph queries
- `queries.py`: Predefined queries for marketplace mech metadata
- Queries marketplace contract data and standard Olas service registry
- Function: `query_mm_mechs_info()` for mech list command

**IPFS Client (`infrastructure/ipfs/`)**
- `IPFSClient`: Client for IPFS gateway operations
- `metadata.py`: Functions for uploading prompt metadata
- IPFS gateway at `https://gateway.autonolas.tech/ipfs/`
- Prompts and metadata stored on IPFS before on-chain requests
- Results delivered as IPFS hashes

### Configuration

**Chain configs (`mech_client/configs/mechs.json`)**
- Per-chain configuration for gnosis, arbitrum, polygon, base, celo, optimism
- Contains: RPC URLs, contract addresses, gas limits, ledger config
- Overridable via environment variables (`MECHX_*`)

**Service templates (`mech_client/config/mech_client_*.json`)**
- Open Autonomy service configurations for agent mode
- Defines service components, dependencies, and deployment settings
- Located within the package for proper distribution

**Environment variables**
All configuration values can be overridden via `MECHX_*` environment variables. The pattern is:
1. Load defaults from `mech_client/configs/mechs.json`
2. Override in `MechConfig.__post_init__()` if environment variable is set

Key variables:
- `MECHX_CHAIN_RPC`: Override RPC endpoint (standardized name, used throughout for both agent mode and blockchain interactions)
- `MECHX_GAS_LIMIT`: Override gas limit
- `MECHX_SERVICE_REGISTRY_CONTRACT`: Override standard Olas service registry contract address (for marketplace mechs)
- `MECHX_TRANSACTION_URL`: Override transaction URL template
- `MECHX_SUBGRAPH_URL`: Override subgraph URL
- `MECHX_MECH_OFFCHAIN_URL`: Offchain mech HTTP endpoint (required for `--use-offchain`, no default)
- `MECHX_LEDGER_CHAIN_ID`: Override chain ID
- `MECHX_LEDGER_POA_CHAIN`: Override POA chain flag
- `MECHX_LEDGER_DEFAULT_GAS_PRICE_STRATEGY`: Override gas price strategy
- `MECHX_LEDGER_IS_GAS_ESTIMATION_ENABLED`: Override gas estimation setting

### Open Autonomy Integration

The project includes Open AEA packages in `packages/valory/` that are used for agent mode operations:
- `agents/mech_client`: AEA agent package
- `services/mech_client`: Service package
- `connections/p2p_libp2p_client`: libp2p connection
- `protocols/acn`: ACN protocol
- `protocols/acn_data_share`: ACN data sharing protocol

### Smart Contract ABIs

All contract ABIs are in `mech_client/abis/`:
- `MechMarketplace.json`: Marketplace contract
- `IMech.json`, `IToken.json`, `IERC1155.json`: Interfaces
- `BalanceTracker*.json`: Payment tracking contracts
- Various NVM (Nevermined) subscription contracts

## Key Patterns and Conventions

1. **Dataclasses for configuration**: Use `@dataclass` with `__post_init__` for environment variable overrides (see `LedgerConfig`, `MechConfig`)

2. **Contract interaction**: Always use `get_contract()` helper which loads ABI from JSON and creates Web3 contract instance

3. **IPFS URLs**: Use `IPFS_URL_TEMPLATE` format with CIDv1 (f01701220 prefix + hash)

4. **Error handling**:
   - **RPC/Network errors in CLI commands**: Catch `requests.exceptions.HTTPError`, `requests.exceptions.ConnectionError`, and `requests.exceptions.Timeout` at the CLI command level. Raise `ClickException` with helpful error messages that include:
     - The current RPC URL (from `MECHX_CHAIN_RPC` env var)
     - Clear description of the error
     - Actionable solutions (check endpoint availability, set different RPC, check network)
     - Use `from e` to preserve the exception chain
   - **Subgraph errors**: Same pattern as RPC errors but reference `MECHX_SUBGRAPH_URL` instead
   - **Web3/Contract errors**: Catch `ContractLogicError` and `ValidationError` from `web3.exceptions`. Provide context about:
     - Contract state and requirements (balance, allowances)
     - Parameter validation
     - Possible causes (insufficient funds, invalid parameters, contract paused)
   - **Private key errors**:
     - `PermissionError`: File permission issues - suggest `chmod 600`
     - `FileNotFoundError`: Missing private key file - suggest valid path
     - `ValueError` with "password"/"decrypt"/"mac" keywords: Decryption failures (wrong password, corrupted keyfile, invalid format)
   - **Metadata/Tool errors**:
     - `KeyError`: Missing tool, schema fields, or environment variables - suggest checking tool lists or env vars
     - `json.JSONDecodeError`: Malformed metadata from IPFS/contracts - indicate data source
     - `IOError`: IPFS gateway or network issues when fetching metadata
   - **Validation helpers**: Use `validate_chain_config()` and `validate_ethereum_address()` helper functions in all commands
   - **Transaction timeout**: `wait_for_receipt()` uses `TRANSACTION_RECEIPT_TIMEOUT = 300.0` seconds (5 minutes)
   - **Retry logic**: Use `MAX_RETRIES = 3` and `WAIT_SLEEP = 3.0` constants for network polling operations (delivery watching, event monitoring)
   - **User-facing errors**: Never show raw Python tracebacks for network failures; always provide context and solutions

5. **Async delivery**: Use `asyncio` for concurrent waiting on multiple delivery channels

6. **Private keys**: Store in `ethereum_private_key.txt` by default (NEVER commit to git)

7. **Type hints**: All functions should have type hints; mypy runs with `--disallow-untyped-defs`

8. **Linting and code quality**:
   - **Target**: All linters must pass in CI (black-check, flake8, mypy, pylint)
   - **Pylint score**: Must be 10.00/10 for CI to pass
   - **Ignore paths**:
     - `*_pb2.py` (generated protobuf files)
     - `packages/valory/*` (Open Autonomy packages)
     - `mech_client/nvm_subscription/*` (NVM subscription module)
   - **Line length**: 88 characters (Black style)
   - **Pylint disable comments**: Acceptable for specific cases with justification:
     - `too-many-statements`: For complex CLI command functions with extensive validation and error handling
     - `too-many-locals`: For service methods orchestrating multiple domain strategies
     - `import-outside-toplevel`: When avoiding circular imports or conditional dependencies (e.g., `CHAIN_TO_ENVS` in `nvm_subscribe`)
     - `protected-access`: When accessing internal APIs for diagnostics (e.g., `ledger_api._api.provider` for error messages)
     - Always add inline comment explaining why the disable is necessary
   - **Globally disabled pylint checks** (in tox.ini):
     - `C0103`: Invalid name (allows single-char variables)
     - `R0801`: Similar lines (common in CLI commands)
     - `R0912`: Too many branches (CLI command complexity)
     - `C0301`: Line too long (handled by Black)
     - `W1203`: Lazy string formatting in logging
     - `C0302`: Too many lines in module
     - `R1735/R1729`: Use of dict/list instead of comprehension
     - `W0511`: TODOs/FIXMEs allowed
     - `E0611/E1101`: Import and attribute errors (false positives with dynamic imports)
   - **Safety check ignored vulnerabilities** (in tox.ini):
     - Build tool vulnerabilities (pip/setuptools in tox environment, not runtime dependencies):
       - `76752`: setuptools Path Traversal (CVE-2025-47273) - affects PackageIndex.download() in setuptools <78.1.1
       - `75180`: pip malicious wheel files (PVE-2025-75180) - affects pip <25.0, requires malicious wheel installation
       - `79883`: pip Arbitrary File Overwrite (CVE-2025-8869) - affects pip <25.2, symlink validation issue
     - These vulnerabilities affect package installation scenarios, not the CLI tool's runtime operation
     - Safe to ignore as they require malicious packages/wheels which the project doesn't interact with

9. **User experience**:
   - Error messages should reference environment variables (e.g., `MECHX_CHAIN_RPC`) rather than internal config files
   - Never suggest users "see mechs.json" or other internal package files that aren't accessible after installation
   - Provide actionable solutions that end users can actually execute

10. **Command validation patterns**:
    - **Chain config**: ALL commands validate chain with `validate_chain_config()` before execution
    - **Addresses**: Commands accepting addresses use `validate_ethereum_address(address, name)` to check format and non-zero
    - **Tool ID format**: Marketplace tools require "service_id-tool_name"
    - **Amount validation**: Deposit commands validate amount is positive integer (wei/smallest unit)
    - **Marketplace support**: Deposit commands check `mech_marketplace_contract != ADDRESS_ZERO`
    - **NVM support**: subscription purchase checks chain exists in `CHAIN_TO_ENVS`
    - **Service ID validation**: Tool commands validate ID is non-negative integer

11. **Operate Library Gotchas**:
    - **ChainType Enum Keys**: The `olas-operate-middleware` library uses `ChainType` enum objects (not strings) as dictionary keys in `wallet.safes`. When accessing safes, iterate and match `chain_type.value` against your string chain config:
      ```python
      master_safe = "N/A"
      for chain_type, safe_address in master_wallet.safes.items():
          if hasattr(chain_type, "value") and chain_type.value == self.chain_config:
              master_safe = str(safe_address)
              break
      ```
    - **Service Token ID**: Access via `service.chain_configs[chain_config].chain_data.token`. Token is `-1` if service not deployed on-chain yet. Use for constructing marketplace URLs: `https://marketplace.olas.network/{chain}/ai-agents/{token}`
    - **Test Mocking**: When mocking operate objects in tests, create ChainType-like mocks with a `value` attribute:
      ```python
      mock_chain_type = MagicMock()
      mock_chain_type.value = "gnosis"
      mock_wallet.safes = {mock_chain_type: "0x5678"}
      ```

12. **Release Workflow Patterns**:
    - **PyPI Publish**: Always set `skip_existing: false` in GitHub Actions `pypa/gh-action-pypi-publish` to fail explicitly on duplicate versions. Using `skip_existing: true` causes silent success when version already exists, hiding deployment issues.
    - **Version Bump Checklist**: Update `pyproject.toml`, `mech_client/__init__.py`, and `SECURITY.md`, then run `poetry lock`

## Validation Helpers

The CLI module (`cli.py`) includes centralized validation functions used across all commands:

### validate_chain_config(chain_config: Optional[str]) -> str

Validates that the chain configuration exists in `mechs.json`.

**Usage:**
```python
validated_chain = validate_chain_config(chain_config)
```

**Raises:**
- `ClickException` if chain_config is None
- `ClickException` if chain_config not found in mechs.json
- `ClickException` if mechs.json is missing or corrupted

**Location:** `mech_client/cli.py:96`

**Pattern:** All commands use this validator to ensure valid chain before proceeding.

### validate_ethereum_address(address: str, name: str = "Address") -> str

Validates Ethereum address format using `eth_utils.is_address()` and checks for zero address.

**Usage:**
```python
validated_address = validate_ethereum_address(priority_mech, "Priority mech address")
validated_safe = validate_ethereum_address(safe, "Safe address")
```

**Raises:**
- `ClickException` if address is None, empty, or zero address (`ADDRESS_ZERO`)
- `ClickException` if address format is invalid (not checksummed 0x... format)

**Location:** `mech_client/cli.py:128`

**Pattern:** All commands that accept addresses (request, deposit commands) use this validator.

## Chain Support Matrix

**Supported chains:** `gnosis`, `base`, `polygon`, `optimism`

All commands require `--chain-config` with one of these four chain names. Arbitrum and Celo exist in the configuration but have no marketplace support and are currently non-functional.

| Chain | Chain ID | Marketplace | Agent Mode | Native Payment | NVM Subscriptions | OLAS Token | USDC Token | Subgraph |
|-------|----------|-------------|------------|----------------|-------------------|------------|------------|----------|
| Gnosis | 100 | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| Base | 8453 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| Polygon | 137 | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ |
| Optimism | 10 | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ |
| Arbitrum | 42161 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Celo | 42220 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

**Feature Definitions:**
- **Marketplace**: Chain has `mech_marketplace_contract` deployed (non-zero address in `mechs.json`)
- **Agent Mode**: Supports `setup` command and Safe-based agent operations (all marketplace chains: Gnosis, Base, Polygon, Optimism)
- **Native Payment**: Supports `deposit native` command for prepaid native token deposits (Gnosis, Base, Polygon, Optimism)
- **NVM Subscriptions**: Supports `subscription purchase` command for Nevermined subscription-based payments (Gnosis, Base)
- **OLAS/USDC Token**: Payment token addresses configured in `infrastructure/config/contract_addresses.py`
- **Subgraph**: Built-in subgraph URL in `mechs.json` (currently all chains have empty `subgraph_url`; must be set via `MECHX_SUBGRAPH_URL` for `mech list`)

**Command Requirements:**
- `mech list`: Requires marketplace + `MECHX_SUBGRAPH_URL` environment variable
- `request`: Requires marketplace contract and standard Olas service registry
- `deposit native`: Requires marketplace + native payment support (Gnosis, Base, Polygon, Optimism)
- `deposit token`: Requires marketplace + token addresses in config (Gnosis, Base, Polygon, Optimism)
- `subscription purchase`: Requires marketplace + NVM subscription support (Gnosis, Base)
- `setup`: All marketplace chains (Gnosis, Base, Polygon, Optimism)

## Important Notes

- Python version: >=3.10, <3.12 (supports Python 3.10, 3.11)
- Main dependencies: `olas-operate-middleware`, `safe-eth-py`, `gql`, `click`
- Agent mode supports all marketplace chains (Gnosis, Base, Polygon, Optimism)
- Batch requests supported for marketplace mechs
- Always use custom RPC providers for reliability (public RPCs may be rate-limited)
- All chains currently have empty `subgraph_url` in config; set `MECHX_SUBGRAPH_URL` manually for subgraph-dependent commands
- **All CLI commands include comprehensive error handling** with actionable solutions referencing environment variables
- **Validation helpers** (`validate_chain_config`, `validate_ethereum_address`) used consistently across all commands
- **Private key handling** includes permission checks, decryption error handling, and clear error messages
- **Transaction timeout** is 5 minutes (300 seconds) for `wait_for_receipt()` - set reliable `MECHX_CHAIN_RPC` to avoid timeouts
