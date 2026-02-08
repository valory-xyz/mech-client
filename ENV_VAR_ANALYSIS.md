# Environment Variable Usage Analysis

## Overview
This document catalogs all environment variable usage in mech-client to identify inconsistencies and design a unified approach.

## Environment Variables Used

### MECHX_* Variables (User Configuration)
1. **MECHX_CHAIN_RPC** - Chain RPC endpoint (most critical)
2. **MECHX_SUBGRAPH_URL** - Subgraph URL for mech list command
3. **MECHX_MECH_OFFCHAIN_URL** - Offchain mech endpoint
4. **MECHX_LEDGER_CHAIN_ID** - Override chain ID
5. **MECHX_LEDGER_POA_CHAIN** - Enable POA chain mode
6. **MECHX_LEDGER_DEFAULT_GAS_PRICE_STRATEGY** - Gas price strategy
7. **MECHX_LEDGER_IS_GAS_ESTIMATION_ENABLED** - Enable gas estimation
8. **MECHX_SERVICE_REGISTRY_CONTRACT** - Service registry contract address
9. **MECHX_WSS_ENDPOINT** - WebSocket endpoint
10. **MECHX_GAS_LIMIT** - Gas limit override
11. **MECHX_TRANSACTION_URL** - Transaction explorer URL

### OPERATE_* Variables (Internal Agent Mode)
1. **OPERATE_PASSWORD** - Password for agent mode keyfile decryption

---

## Inconsistencies Found

### 1. **Pattern Inconsistency: os.getenv() vs os.environ[]**

#### Files using `os.getenv()` (preferred - safe, returns None if not set):
- `mech_client/services/setup_service.py:136` - MECHX_CHAIN_RPC
- `mech_client/infrastructure/operate/manager.py:75` - OPERATE_PASSWORD
- `mech_client/infrastructure/operate/key_manager.py:75` - OPERATE_PASSWORD
- `mech_client/utils/errors/handlers.py` - Multiple instances for MECHX_CHAIN_RPC, MECHX_SUBGRAPH_URL
- `mech_client/cli/commands/request_cmd.py:151` - MECHX_MECH_OFFCHAIN_URL
- `mech_client/cli/commands/mech_cmd.py:64` - MECHX_SUBGRAPH_URL
- `mech_client/infrastructure/config/chain_config.py` - All MECHX_* variables

#### Files using `os.environ[]` (risky - raises KeyError if not set):
- `mech_client/infrastructure/nvm/config.py:62` - MECHX_CHAIN_RPC
  ```python
  if "MECHX_CHAIN_RPC" in os.environ:
      self.web3_provider_uri = os.environ["MECHX_CHAIN_RPC"]
  ```

#### Files using `os.environ` for SETTING (not reading):
- `mech_client/infrastructure/operate/manager.py:77,87,89,90,91` - Setting OPERATE_PASSWORD and ATTENDED

**Issue:** Should consistently use `os.getenv()` for reading env vars.

---

### 2. **Default Value Inconsistency**

#### No default (returns None):
- `mech_client/cli/commands/request_cmd.py:151`
  ```python
  mech_offchain_url = os.getenv("MECHX_MECH_OFFCHAIN_URL")
  ```

- `mech_client/cli/commands/mech_cmd.py:64`
  ```python
  subgraph_url = os.getenv("MECHX_SUBGRAPH_URL")
  ```

- `mech_client/utils/errors/handlers.py:109,154`
  ```python
  rpc_url = os.getenv("MECHX_CHAIN_RPC")  # No default
  ```

#### Default to "default":
- `mech_client/utils/errors/handlers.py:67,98,104,143,149`
  ```python
  rpc_url = os.getenv("MECHX_CHAIN_RPC", "default")
  ```

#### Default to "not set":
- `mech_client/utils/errors/handlers.py:70,199,207`
  ```python
  subgraph_url = os.getenv("MECHX_SUBGRAPH_URL", "not set")
  ```

**Issue:** Inconsistent defaults make error messages confusing. Sometimes we show "default", sometimes "not set", sometimes None.

---

### 3. **Loading Location Inconsistency**

#### Loaded in `__post_init__()` (dataclass pattern - good):
- `mech_client/infrastructure/config/chain_config.py:69-89` - LedgerConfig.__post_init__()
  - Loads: MECHX_CHAIN_RPC, MECHX_LEDGER_CHAIN_ID, MECHX_LEDGER_POA_CHAIN, etc.

- `mech_client/infrastructure/nvm/config.py:58-62` - NVMConfig.__post_init__()
  - Loads: MECHX_CHAIN_RPC

#### Loaded in `__post_init__()` (MechConfig pattern - good):
- `mech_client/infrastructure/config/chain_config.py:155-187` - MechConfig.__post_init__()
  - Loads: MECHX_SERVICE_REGISTRY_CONTRACT, MECHX_CHAIN_RPC, MECHX_WSS_ENDPOINT, MECHX_GAS_LIMIT, MECHX_TRANSACTION_URL, MECHX_SUBGRAPH_URL

#### Loaded at runtime in CLI commands (bad - should be in config):
- `mech_client/cli/commands/request_cmd.py:151` - MECHX_MECH_OFFCHAIN_URL
- `mech_client/cli/commands/mech_cmd.py:64` - MECHX_SUBGRAPH_URL

#### Loaded at runtime in error handlers (unavoidable - for diagnostic messages):
- `mech_client/utils/errors/handlers.py` - Multiple instances

#### Loaded at runtime in services (inconsistent):
- `mech_client/services/setup_service.py:136` - MECHX_CHAIN_RPC

**Issue:** Some env vars are loaded in config classes (good), others are loaded ad-hoc in CLI commands (bad).

---

### 4. **Validation Inconsistency**

#### Explicit validation with error message:
- `mech_client/cli/commands/mech_cmd.py:64-73`
  ```python
  subgraph_url = os.getenv("MECHX_SUBGRAPH_URL")
  if not subgraph_url:
      raise click.ClickException(
          "Environment variable MECHX_SUBGRAPH_URL is required..."
      )
  ```

- `mech_client/cli/commands/request_cmd.py:151-157`
  ```python
  mech_offchain_url = os.getenv("MECHX_MECH_OFFCHAIN_URL")
  if not mech_offchain_url:
      raise click.ClickException(
          "MECHX_MECH_OFFCHAIN_URL is required..."
      )
  ```

#### Implicit validation (will fail later with unclear error):
- `mech_client/infrastructure/config/chain_config.py:69-71`
  ```python
  address = os.getenv("MECHX_CHAIN_RPC")
  if address:
      self.address = address  # If not set, uses default from mechs.json
  ```

**Issue:** Some env vars have explicit validation with helpful messages, others fail silently or with unclear errors.

---

### 5. **Documentation Inconsistency**

#### Well-documented:
- `mech_client/infrastructure/config/chain_config.py:50-54`
  ```python
  """Load RPC configuration with precedence:

  1. MECHX_CHAIN_RPC environment variable (highest priority)
  2. Operate config (agent mode only)
  3. mechs.json default (lowest priority)
  """
  ```

#### Poorly documented:
- Most other env var usage has minimal or no documentation

**Issue:** Users don't know which env vars exist, what they do, or what precedence they have.

---

## Recommendations for Discussion

### Option 1: Centralized Config Loading
- Create a single `EnvironmentConfig` class that loads ALL env vars in `__post_init__()`
- All other code reads from this config object, never directly from `os.getenv()`
- Pros: Single source of truth, easy to document, easy to test
- Cons: Need to pass config object everywhere

### Option 2: Dataclass Pattern (Current Best Practice)
- Continue using `__post_init__()` in dataclasses
- Move CLI command env var loading into config classes
- Standardize: always use `os.getenv()`, never `os.environ[]`
- Standardize: consistent default values (None vs "not set" vs "default")
- Pros: Follows existing pattern, minimal refactoring
- Cons: Env vars scattered across multiple config classes

### Option 3: Environment Variable Registry
- Create a registry of all valid env vars with metadata (name, type, default, description, validation)
- Use a helper function that reads from registry: `get_env("MECHX_CHAIN_RPC")`
- Pros: Self-documenting, type-safe, centralized validation
- Cons: Most invasive refactoring

---

## Files Affected (Summary)

### Configuration Files (should own env var loading):
1. `mech_client/infrastructure/config/chain_config.py` - ✅ Good (uses __post_init__)
2. `mech_client/infrastructure/nvm/config.py` - ⚠️ Uses os.environ[] instead of os.getenv()

### CLI Commands (should NOT load env vars directly):
1. `mech_client/cli/commands/request_cmd.py` - ❌ Loads MECHX_MECH_OFFCHAIN_URL
2. `mech_client/cli/commands/mech_cmd.py` - ❌ Loads MECHX_SUBGRAPH_URL

### Service Layer (should use config objects):
1. `mech_client/services/setup_service.py` - ❌ Loads MECHX_CHAIN_RPC directly

### Infrastructure (internal, acceptable):
1. `mech_client/infrastructure/operate/manager.py` - ✅ OK (sets OPERATE_PASSWORD for olas-operate-middleware)
2. `mech_client/infrastructure/operate/key_manager.py` - ✅ OK (reads OPERATE_PASSWORD)

### Error Handlers (unavoidable, acceptable):
1. `mech_client/utils/errors/handlers.py` - ✅ OK (diagnostic messages only)

---

## Next Steps

1. **Decide on approach:** Option 1, 2, or 3?
2. **Standardize patterns:**
   - `os.getenv()` vs `os.environ[]`
   - Default values (None vs "not set" vs "default")
   - Validation strategy
3. **Refactor CLI commands:** Move env var loading to config classes
4. **Document all env vars:** Create user-facing documentation
5. **Add validation:** Ensure helpful error messages for missing required env vars
