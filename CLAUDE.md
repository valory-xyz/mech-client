# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Mech Client is a Python CLI tool and library for interacting with AI Mechs (on-chain AI agents) via the Olas (Mech) Marketplace, enabling users to send AI task requests on-chain and receive results through on-chain delivery.

**Key Architecture:** Layered architecture (CLI → Service → Domain → Infrastructure) following hexagonal design principles. See [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) for details.

**Testing:** Comprehensive unit test suite (689 tests, 100% coverage). See [docs/TESTING.md](./docs/TESTING.md) for testing guidelines.

**Commands:** 11 CLI commands with detailed dependency diagrams. See [docs/COMMANDS.md](./docs/COMMANDS.md) for command reference.

## Quick Start for Development

```bash
# Install dependencies
poetry install
poetry shell

# Run all linters (REQUIRED before committing)
tox -e black-check,isort-check,flake8,mypy,pylint,bandit,darglint,vulture && tox -e liccheck

# Run tests
poetry run pytest tests/unit/ -k "not trio"

# Test documentation locally
tox -e mkdocs-serve  # Starts dev server at http://127.0.0.1:8000/

# Build documentation
tox -e mkdocs-build  # Builds static site to site/ directory

# Build distribution
make dist
```

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

### Issue: Custom Subgraph URL (optional)

**Note:** Default subgraph URLs are provided in config. Override only if needed.

**Solution (Optional):**
```bash
# Override default subgraph URL if needed
export MECHX_SUBGRAPH_URL='https://your-custom-subgraph-url'

# Default URLs (already configured):
# Gnosis:   https://api.subgraph.autonolas.tech/api/proxy/marketplace-gnosis
# Base:     https://api.subgraph.autonolas.tech/api/proxy/marketplace-base
# Polygon:  https://api.subgraph.autonolas.tech/api/proxy/marketplace-polygon
# Optimism: https://api.subgraph.autonolas.tech/api/proxy/marketplace-optimism
```

### Issue: "Permission denied" when reading private key

**Affected Commands:** request, deposit native, deposit token, subscription purchase

**Solution:**
```bash
# Fix file permissions
chmod 600 ethereum_private_key.txt

# Or specify different key file
mechx request --key /path/to/key ...
```

### Issue: "Failed to decrypt private key" or "Incorrect password"

**Affected Commands:** request, deposit native, deposit token, subscription purchase (agent mode)

**Solution:**
- Verify your OPERATE_PASSWORD in .env file
- Ensure keyfile format is valid (JSON keystore format)
- Try re-creating the agent mode setup if keyfile is corrupted:
```bash
# Re-run setup
mechx setup --chain-config gnosis
```

### Issue: "Smart contract error" or "Insufficient balance"

**Affected Commands:** request, deposit native, deposit token, subscription purchase

**Solution:**
```bash
# Check your balance
cast balance <YOUR_ADDRESS> --rpc-url $MECHX_CHAIN_RPC

# For request command, ensure you have deposited balance or per-request payment
mechx deposit native 1000000000000000000 --chain-config gnosis
```

See [docs/COMMANDS.md](./docs/COMMANDS.md) for more common issues and their solutions.

## Key Patterns and Conventions

### 1. Centralized Environment Variable Configuration

**CRITICAL:** All environment variable loading must go through `EnvironmentConfig` - never use `os.getenv()` or `os.environ[]` directly outside of error handlers.

**Single Source of Truth:**
```python
from mech_client.infrastructure.config.environment import EnvironmentConfig

# Load environment config once
env_config = EnvironmentConfig.load()

# Access env vars through the config object
if env_config.mechx_chain_rpc:
    use_custom_rpc(env_config.mechx_chain_rpc)
```

**Available Environment Variables (see `EnvironmentConfig` for full list):**
- `MECHX_CHAIN_RPC` - Chain RPC endpoint (most critical)
- `MECHX_SUBGRAPH_URL` - Subgraph GraphQL endpoint (optional, defaults provided)
- `MECHX_MECH_OFFCHAIN_URL` - Offchain mech endpoint
- `MECHX_GAS_LIMIT` - Gas limit override
- `MECHX_TRANSACTION_URL` - Block explorer URL template
- `MECHX_LEDGER_CHAIN_ID` - Override chain ID
- `MECHX_LEDGER_POA_CHAIN` - Enable POA chain mode
- `MECHX_LEDGER_DEFAULT_GAS_PRICE_STRATEGY` - Gas price strategy
- `MECHX_LEDGER_IS_GAS_ESTIMATION_ENABLED` - Enable gas estimation
- `OPERATE_PASSWORD` - Password for agent mode keyfile decryption

**Dataclasses for Configuration:**

Use `@dataclass` with `__post_init__` that loads from `EnvironmentConfig`:

```python
from mech_client.infrastructure.config.environment import EnvironmentConfig

@dataclass
class MechConfig:
    rpc_url: str  # Default from mechs.json

    def __post_init__(self) -> None:
        # Load environment configuration (centralized)
        env_config = EnvironmentConfig.load()

        # Override from environment if set
        if env_config.mechx_chain_rpc:
            self.rpc_url = env_config.mechx_chain_rpc
```

**Benefits:**
- Single source of truth for all environment variables
- Improved testability (easy to mock)
- Self-documenting via type hints and docstrings
- Type-safe environment variable access
- Eliminates inconsistent patterns

### 2. Error Handling Pattern

All CLI commands follow this error handling pattern:

- **RPC/Network errors**: Catch `requests.exceptions.HTTPError`, `ConnectionError`, `Timeout`. Raise `ClickException` with:
  - Current RPC URL (from `MECHX_CHAIN_RPC` env var)
  - Clear description of the error
  - Actionable solutions
  - Use `from e` to preserve exception chain

- **Web3/Contract errors**: Catch `ContractLogicError` and `ValidationError`. Provide context about contract state and requirements.

- **Private key errors**:
  - `PermissionError`: File permission issues - suggest `chmod 600`
  - `FileNotFoundError`: Missing private key file
  - `ValueError` with "password"/"decrypt"/"mac": Decryption failures

- **Validation helpers**: Use `validate_chain_config()` and `validate_ethereum_address()` in all commands

### 3. Linting and Code Quality

**CRITICAL:** All linters must pass with pylint score 10.00/10 for CI to pass.

```bash
# Run all linters (REQUIRED before committing)
tox -e black-check,isort-check,flake8,mypy,pylint,bandit,darglint,vulture && tox -e liccheck
```

**Pylint disable comments** acceptable only with justification:
- `too-many-statements`: Complex CLI command functions
- `too-many-locals`: Service methods orchestrating multiple strategies
- `import-outside-toplevel`: Avoiding circular imports
- `protected-access`: Accessing internal APIs for diagnostics
- Always add inline comment explaining why

**Globally disabled pylint checks** (in tox.ini):
- `C0103`: Invalid name (allows single-char variables)
- `R0801`: Similar lines (common in CLI commands)
- `R0912`: Too many branches (CLI command complexity)
- See tox.ini for full list

### 4. Operating Modes Pattern

The CLI supports two operating modes for wallet commands:

**Agent Mode (Default):**
- Uses Safe multisig for transactions
- Requires `mechx setup --chain-config <chain>` first
- Creates `~/.operate_mech_client/` directory

**Client Mode:**
- Uses EOA (Externally Owned Account) directly
- Enabled with `--client-mode` flag
- Requires `--key` parameter

**Mode Detection:**
```python
WALLET_COMMANDS = {"request", "deposit", "subscription"}

if is_wallet_command and not is_setup_called and not client_mode:
    click.echo("Agent mode enabled")
    # Check operate path exists
```

**Note:** Read-only commands (mech, tool) and utility commands (ipfs) work without mode setup.

### 5. Setup Service Monkey-Patching Pattern (CRITICAL)

The `olas-operate-middleware` expects chain-specific env vars (e.g., `GNOSIS_LEDGER_RPC`), but mech-client uses `MECHX_CHAIN_RPC`. Monkey-patch required:

```python
def setup(self):
    import sys

    # Create wrapper without self parameter
    def _configure_wrapper(template, operate_instance):
        return self.configure_local_config(template, operate_instance)

    # Monkey-patch the function
    sys.modules["operate.quickstart.run_service"].configure_local_config = _configure_wrapper

    # Now call run_service - it will use our custom config
    run_service(operate=operate, config_path=template_path, ...)
```

**Gotcha:** Without this monkey-patch, setup fails with "GNOSIS_LEDGER_RPC env var required in unattended mode"

### 6. Operate Library Gotchas

**ChainType Enum Keys:** The library uses `ChainType` enum objects (not strings) as dictionary keys:

```python
master_safe = "N/A"
for chain_type, safe_address in master_wallet.safes.items():
    if hasattr(chain_type, "value") and chain_type.value == self.chain_config:
        master_safe = str(safe_address)
        break
```

**Service Token ID:** Access via `service.chain_configs[chain_config].chain_data.token`. Token is `-1` if not deployed yet.

### 7. Type Hints

All functions must have type hints. Mypy runs with `--disallow-untyped-defs`.

### 8. Async Patterns

- Use `asyncio` for concurrent delivery watching
- Use `await asyncio.sleep()`, **never** `time.sleep()` in async functions
- Place `await asyncio.sleep()` OUTSIDE loops iterating over request IDs

### 9. Configuration Override Pattern

All configuration values can be overridden via `MECHX_*` environment variables using `EnvironmentConfig`:

**Priority order:**
1. Environment variable (via `EnvironmentConfig`) - highest priority
2. Stored operate config (agent mode only, for RPC)
3. Default from `mech_client/configs/mechs.json` - lowest priority

**Implementation:**
```python
from mech_client.infrastructure.config.environment import EnvironmentConfig

def __post_init__(self) -> None:
    # Load environment configuration (centralized)
    env_config = EnvironmentConfig.load()

    # Override if env var is set
    if env_config.mechx_chain_rpc:
        self.rpc_url = env_config.mechx_chain_rpc
```

**Key variables:**
- `MECHX_CHAIN_RPC`: Override RPC endpoint (most important)
- `MECHX_SUBGRAPH_URL`: Override subgraph URL (optional, defaults provided)
- `MECHX_MECH_OFFCHAIN_URL`: Offchain mech endpoint (required for `--use-offchain`)

See `EnvironmentConfig` class in `infrastructure/config/environment.py` for complete list.

### 10. User Experience Guidelines

- Error messages should reference environment variables (e.g., `MECHX_CHAIN_RPC`)
- Never suggest users "see mechs.json" or other internal package files
- Provide actionable solutions that end users can execute
- Never show raw Python tracebacks for network failures

### 11. Code Reuse Patterns

**CLI Command Helper:**
```python
from mech_client.cli.common import setup_wallet_command

# Use in all wallet commands (request, deposit, subscription)
wallet_ctx = setup_wallet_command(ctx, chain_config, key)
# Returns: crypto, agent_mode, safe_address, ethereum_client
```

**Error Handling Decorator:**
```python
from mech_client.utils.errors.handlers import handle_cli_errors

@click.command()
@handle_cli_errors  # Catches and formats common errors
def my_command():
    pass
```

**Base Service Class:**
```python
from mech_client.services.base_service import BaseTransactionService

class MyService(BaseTransactionService):
    def __init__(self, chain_config, agent_mode, crypto, safe_address=None, ethereum_client=None):
        super().__init__(chain_config, agent_mode, crypto, safe_address, ethereum_client)
        # self.ledger_api, self.executor, self.mech_config already initialized
```

**NVM Contract Wrappers:**
```python
class MyContract(NVMContractWrapper):
    CONTRACT_NAME = "MyContract"  # No need for __init__
```

**Chain ID Constants:**
```python
from mech_client.infrastructure.config.constants import CHAIN_ID_GNOSIS, CHAIN_ID_TO_NAME
```

## Common Refactoring Pitfalls

When refactoring CLI code, be aware of these gotchas (discovered during v0.17.0 refactor):

1. **Monkey-Patching Loss**: Ensure monkey-patching behavior is preserved when extracting logic. Setup command requires monkey-patching `configure_local_config`.

2. **Agent Mode Scope Creep**: Agent mode checks should only apply to wallet commands. Read-only and utility commands work independently.

3. **Context Flag Propagation**: Ensure Click context flags (like `client_mode`) are accessible via `ctx.obj.get()`.

4. **ChainType Enum Handling**: Operate library uses enum objects as dictionary keys, not strings.

5. **Test Coverage for Integration Points**: Monkey-patching, context passing, and mode detection need explicit test coverage.

6. **Token Approval Agent Mode**: ERC20 approvals must use executor pattern. In agent mode, approvals go through Safe multisig via `executor.execute_transaction()`, not directly from EOA.

7. **IPFS Pin Flag**: For offchain requests, use `upload(file_path, pin=False)` to only compute hash without uploading.

8. **Polling Cycle Sleep**: Place `await asyncio.sleep()` OUTSIDE the request ID loop.

9. **Blocking Async Event Loop**: Never use `time.sleep()` in async functions.

10. **Native vs Token Deposit Contracts**: `BalanceTrackerFixedPriceNative` has NO `deposit()` method - it uses `receive()` (triggered by plain native transfer) and `depositFor(address)`. Use `executor.execute_transfer()` for native deposits. `BalanceTrackerFixedPriceToken` DOES have `deposit(amount)` - use `executor.execute_transaction()` for token deposits.

## Release Workflow

Version bump checklist:
1. Update `pyproject.toml`, `mech_client/__init__.py`, and `SECURITY.md`
2. Run `poetry lock` (updates lock file if dependencies changed)
3. Run `poetry run autonomy packages sync --update-packages`
4. Run `make dist` (builds distribution packages)
5. Create release PR and tag

**PyPI Publish:** Always set `skip_existing: false` in GitHub Actions to fail explicitly on duplicate versions.

## Important Notes

- **Python version**: >=3.10, <3.12 (supports Python 3.10, 3.11)
- **Supported chains**: gnosis, base, polygon, optimism (Arbitrum and Celo not functional)
- **Main dependencies**: `olas-operate-middleware`, `safe-eth-py`, `gql`, `click`
- **Agent mode**: Supports all marketplace chains
- **Always use custom RPC providers** for reliability (public RPCs may be rate-limited)
- **Transaction timeout**: 5 minutes (300 seconds) for `wait_for_receipt()`

## Documentation Structure

- **[CLAUDE.md](./CLAUDE.md)** (this file): Development guidelines and patterns
- **[docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md)**: System architecture, layers, and design principles
- **[docs/TESTING.md](./docs/TESTING.md)**: Testing guidelines, running tests, writing tests
- **[docs/COMMANDS.md](./docs/COMMANDS.md)**: Command reference with dependency diagrams
- **[docs/index.md](./docs/index.md)**: User guide for interacting with Mechs
- **[docs/manual-testing-guide.md](./docs/manual-testing-guide.md)**: Manual testing procedures (internal, not in public docs nav)
- **[README.md](./README.md)**: User documentation and examples
- **[mkdocs.yml](./mkdocs.yml)**: MkDocs configuration for documentation site

### Testing Documentation Locally

The documentation is built with MkDocs and published to https://stack.olas.network/mech-client/

**Test documentation locally:**
```bash
# Start development server with live reload
tox -e mkdocs-serve
# Visit http://127.0.0.1:8000/

# Build static site
tox -e mkdocs-build
# Output in site/ directory
```

**MkDocs Configuration:**
- Simplified configuration (32 lines) with only essential features
- Compatible with monorepo inclusion via `!include` directive
- Material theme with basic markdown extensions
- Only `docs/index.md` in public navigation (manual-testing-guide.md is internal)
