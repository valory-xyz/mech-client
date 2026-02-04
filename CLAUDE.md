# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Mech Client is a Python CLI tool and library for interacting with AI Mechs (on-chain AI agents) via the Olas protocol. It supports both legacy mechs and the newer Mech Marketplace, enabling users to send AI task requests on-chain and receive results through various delivery methods (ACN, WebSocket, on-chain).

## Development Commands

### Installation and Setup

```bash
# Install dependencies and enter virtual environment
poetry install
poetry shell
```

### Code Quality and Linting

```bash
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

### Testing

The project uses Locust for stress testing the mech marketplace:

```bash
# Run Locust with web UI
locust -f tests/locustfile.py

# Run Locust headless (CLI mode)
locust -f tests/locustfile.py --headless -u 1 -r 1 -t 25m

# Run with CSV export for results
locust -f tests/locustfile.py --headless --only-summary --csv results
```

Note: A `ethereum_private_key.txt` file is required in `tests/` for stress testing.

### Build and Release

```bash
# Build distribution packages (includes ejecting packages)
make dist
```

For releases, manually:
1. Bump version in `pyproject.toml`, `mech_client/__init__.py`, and `SECURITY.md`
2. Run `poetry lock`
3. Run `rm -rf dist`
4. Run `autonomy packages sync --update-packages`
5. Run `make eject-packages`
6. Create release PR and tag

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

1. **Agent Mode (Recommended for all chains)**: Registers on-chain interactions as an agent in the Olas protocol, using Safe multisig for transactions. Configured via `setup-agent-mode` command and uses the `olas-operate-middleware` package.

2. **Client Mode**: Simple EOA-based interactions without agent registration. Enabled with `--client-mode` flag.

### Core Modules

#### CLI Layer (`cli.py`)
Main Click-based CLI interface that routes commands to appropriate modules. Handles:
- Command parsing and validation
- Agent mode vs client mode switching
- Environment setup and configuration loading
- Integration with `olas-operate-middleware` for agent operations

#### Interaction Layers

**Legacy Mechs (`interact.py`)**
- Direct interaction with individual mech agents via agent registry
- Uses `ConfirmationType` enum (off-chain, on-chain, wait-for-both) for delivery method selection
- Configuration via `MechConfig` dataclass loaded from `configs/mechs.json`
- Single request/response model per agent

**Mech Marketplace (`marketplace_interact.py`)**
- Interaction via the Mech Marketplace contract
- Supports multiple payment types (`PaymentType` enum): NATIVE, TOKEN, USDC_TOKEN, NATIVE_NVM, TOKEN_NVM_USDC
- Batch request support (multiple prompts/tools)
- Prepaid and per-request payment models
- Offchain mech support via HTTP endpoints
- Configuration via `MechMarketplaceRequestConfig`

#### Delivery Mechanisms (`delivery.py`, `wss.py`, `acn.py`)

**On-chain delivery (`delivery.py`)**
- Polls blockchain for `Deliver` events from marketplace or mech contracts
- Extracts IPFS hash from event data
- Primary method: `watch_for_marketplace_data()` and `watch_for_mech_data_url()`

**WebSocket delivery (`wss.py`)**
- Connects to chain WSS endpoints for real-time event streaming
- Watches for `Request` events to get request IDs and `Deliver` events for results
- Uses websocket-client library

**ACN delivery (`acn.py`)**
- Agent Communication Network (libp2p-based) for off-chain delivery
- Loads ACN protocols and p2p_libp2p_client connection from `mech_client/helpers/`
- Used primarily for legacy mechs

#### Safe Integration (`safe.py`)
- Gnosis Safe transaction building and execution for agent mode
- Functions: `send_safe_tx()` and `get_safe_nonce()`
- Uses `safe-eth-py` library

#### Tool Management

**Legacy (`mech_tool_management.py`)**
- Fetches tools from agent metadata via complementary metadata hash contract
- Functions: `get_tools_for_agents()`, `get_tool_description()`, `get_tool_io_schema()`

**Marketplace (`mech_marketplace_tool_management.py`)**
- Fetches tools from marketplace mech metadata
- Uses `ToolInfo` and `ToolsForMarketplaceMech` dataclasses
- Same function signatures as legacy but with "marketplace" in name

#### Blockchain Interaction

**Subgraph queries (`subgraph.py`, `mech_marketplace_subgraph.py`)**
- GraphQL queries for agent/mech metadata
- Legacy: queries agent registry
- Marketplace: queries marketplace contract data

**IPFS (`prompt_to_ipfs.py`, `push_to_ipfs.py`, `fetch_ipfs_hash.py`)**
- IPFS gateway at `https://gateway.autonolas.tech/ipfs/`
- Prompts and metadata stored on IPFS before on-chain requests
- Results delivered as IPFS hashes

### Configuration

**Chain configs (`configs/mechs.json`)**
- Per-chain configuration for gnosis, arbitrum, polygon, base, celo, optimism
- Contains: RPC URLs, contract addresses, gas limits, ledger config
- Overridable via environment variables (`MECHX_*`)

**Service templates (`config/mech_client_*.json`)**
- Open Autonomy service configurations for agent mode
- Defines service components, dependencies, and deployment settings

**Environment variables**
Key variables:
- `MECHX_CHAIN_RPC`: Override RPC endpoint
- `MECHX_WSS_ENDPOINT`: Override WebSocket endpoint
- `MECHX_GAS_LIMIT`: Override gas limit
- `MECHX_MECH_OFFCHAIN_URL`: Offchain mech endpoint for offchain requests
- `MECHX_LEDGER_*`: Ledger configuration overrides

### Open Autonomy Integration

The project includes Open AEA packages in `packages/valory/`:
- `agents/mech_client`: AEA agent package
- `services/mech_client`: Service package

These are "ejected" into `mech_client/helpers/` during build via `make eject-packages`:
- `p2p_libp2p_client`: libp2p connection
- `acn`: ACN protocol
- `acn_data_share`: ACN data sharing protocol

### Smart Contract ABIs

All contract ABIs are in `mech_client/abis/`:
- `AgentMech.json`, `AgentRegistry.json`: Legacy mech contracts
- `MechMarketplace.json`: Marketplace contract
- `IMech.json`, `IToken.json`, `IERC1155.json`: Interfaces
- `BalanceTracker*.json`: Payment tracking contracts
- Various NVM (Nevermined) subscription contracts

## Key Patterns and Conventions

1. **Dataclasses for configuration**: Use `@dataclass` with `__post_init__` for environment variable overrides (see `LedgerConfig`, `MechConfig`)

2. **Contract interaction**: Always use `get_contract()` helper which loads ABI from JSON and creates Web3 contract instance

3. **IPFS URLs**: Use `IPFS_URL_TEMPLATE` format with CIDv1 (f01701220 prefix + hash)

4. **Error handling**: Retry logic with `MAX_RETRIES` and `WAIT_SLEEP` constants for network operations

5. **Async delivery**: Use `asyncio` for concurrent waiting on multiple delivery channels

6. **Private keys**: Store in `ethereum_private_key.txt` by default (NEVER commit to git)

7. **Type hints**: All functions should have type hints; mypy runs with `--disallow-untyped-defs`

8. **Linting exceptions**:
   - Ignore `mech_client/helpers/*` (ejected packages)
   - Ignore `*_pb2.py` (generated protobuf files)
   - Line length: 88 characters (Black style)

## Important Notes

- Python version: >=3.10, <3.12
- Main dependencies: `olas-operate-middleware`, `safe-eth-py`, `gql`, `click`
- Agent mode currently only supports Gnosis and Base networks
- Batch requests only supported for marketplace mechs, not legacy mechs
- Always use custom RPC providers for reliability (public RPCs may be rate-limited)
