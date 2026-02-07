# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Mech Client is a Python CLI tool and library for interacting with AI Mechs (on-chain AI agents) via the Olas (Mech) Marketplace, enabling users to send AI task requests on-chain and receive results through on-chain delivery.

**Key Architecture:** Layered architecture (CLI → Service → Domain → Infrastructure) following hexagonal design principles. See [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) for details.

**Testing:** Comprehensive unit test suite (277 tests across all layers). See [docs/TESTING.md](./docs/TESTING.md) for testing guidelines.

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

### 1. Dataclasses for Configuration

Use `@dataclass` with `__post_init__` for environment variable overrides:

```python
@dataclass
class MechConfig:
    chain_rpc: str = "https://default-rpc.com"

    def __post_init__(self) -> None:
        # Override from environment variable
        self.chain_rpc = os.getenv("MECHX_CHAIN_RPC", self.chain_rpc)
```

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

All configuration values can be overridden via `MECHX_*` environment variables:

1. Load defaults from `mech_client/configs/mechs.json`
2. Override in `MechConfig.__post_init__()` if environment variable is set

Key variables:
- `MECHX_CHAIN_RPC`: Override RPC endpoint (most important)
- `MECHX_SUBGRAPH_URL`: Override subgraph URL (required for `mech list`)
- `MECHX_MECH_OFFCHAIN_URL`: Offchain mech endpoint (required for `--use-offchain`)

### 10. User Experience Guidelines

- Error messages should reference environment variables (e.g., `MECHX_CHAIN_RPC`)
- Never suggest users "see mechs.json" or other internal package files
- Provide actionable solutions that end users can execute
- Never show raw Python tracebacks for network failures

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

## Post-v0.17.0 Refactor Bug Fixes

Critical bugs fixed in v0.17.1:

1. **Blocking Event Loop** (`domain/delivery/onchain_watcher.py`): Used `time.sleep()` instead of `await asyncio.sleep()` ✅ Fixed
2. **Misleading Balance Error** (`services/marketplace_service.py`): Showed bool instead of amount ✅ Fixed
3. **Polling Cycle Sleep** (`domain/delivery/onchain_watcher.py`): Sleep inside loop instead of outside ✅ Fixed
4. **IPFS Pinning** (`infrastructure/ipfs/metadata.py`): Unnecessary pinning for offchain requests ✅ Fixed

Known issues:
5. **Token Approval Agent Mode** (`domain/payment/token.py`): Only implements client mode path 📋 Documented in `docs/TOKEN_APPROVAL_AGENT_MODE_ISSUE.md`
6. **Agent Mode RPC Configuration** (`infrastructure/config/chain_config.py`): Commands don't read RPC from stored operate config 📋 Documented in `docs/AGENT_MODE_RPC_CONFIGURATION_ISSUE.md`

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
- **[docs/TOKEN_APPROVAL_AGENT_MODE_ISSUE.md](./docs/TOKEN_APPROVAL_AGENT_MODE_ISSUE.md)**: Known issue - token approval in agent mode
- **[docs/AGENT_MODE_RPC_CONFIGURATION_ISSUE.md](./docs/AGENT_MODE_RPC_CONFIGURATION_ISSUE.md)**: Known issue - RPC config not loaded from operate
- **[README.md](./README.md)**: User documentation and examples
