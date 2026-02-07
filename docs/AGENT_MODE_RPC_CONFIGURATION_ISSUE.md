# Agent Mode RPC Configuration Issue

**Status:** 🐛 Open Issue
**Severity:** Medium
**Affects:** Agent mode (all wallet commands: request, deposit, subscription)
**Workaround:** Set `MECHX_CHAIN_RPC` environment variable

## Summary

When running commands in agent mode (after `mechx setup`), the RPC configuration stored during setup is **not used**. Instead, commands fall back to the default RPC from `mechs.json` or require `MECHX_CHAIN_RPC` to be set as an environment variable.

This means users must set `MECHX_CHAIN_RPC` **both during setup AND when running commands**, defeating the purpose of persisting the configuration.

## Symptoms

1. User runs `mechx setup --chain-config gnosis` with `MECHX_CHAIN_RPC` set
2. Setup succeeds and stores RPC configuration to `~/.operate_mech_client/`
3. User unsets `MECHX_CHAIN_RPC` or opens a new terminal
4. User runs `mechx request ...` in agent mode
5. **Command uses default RPC from mechs.json, not the stored RPC**
6. If default RPC is slow/unavailable, command times out

## Root Cause Analysis

### During Setup (Works Correctly ✅)

**File:** `mech_client/services/setup_service.py`

```python
def configure_local_config(self, template, operate):
    # Loads RPC from MECHX_CHAIN_RPC or mechs.json
    for chain in template["configurations"]:
        mech_config = get_mech_config(chain)
        rpc_url = mech_config.rpc_url

        env_rpc_override = os.getenv("MECHX_CHAIN_RPC")
        if env_rpc_override is not None:
            rpc_url = env_rpc_override

        config.rpc[chain] = rpc_url  # ✅ Stores to operate config

    config.store()  # ✅ Persists to disk
```

**Stored locations:**
- `~/.operate_mech_client/{service_name}-quickstart-config.json`
- `~/.operate_mech_client/services/{service_hash}/deployment/service.yaml`

### During Commands (Bug ❌)

**Files:** `mech_client/cli/commands/request_cmd.py`, `deposit_cmd.py`, `subscription_cmd.py`

```python
# Load config from mechs.json only
mech_config = get_mech_config(validated_chain)  # ❌ Ignores stored operate config

# Create ledger API with mechs.json defaults
ledger_api = EthereumApi(**asdict(mech_config.ledger_config))
```

**File:** `mech_client/infrastructure/config/chain_config.py`

```python
@dataclass
class LedgerConfig:
    address: str  # Default from mechs.json

    def __post_init__(self):
        # Only overrides from environment variable
        address = os.getenv("MECHX_CHAIN_RPC")  # ❌ Never reads from operate config
        if address:
            self.address = address
```

### Configuration Loading Priority (Current)

1. ❌ **Never** reads from stored operate configuration
2. ✅ Loads default from `mechs.json`
3. ✅ Overrides with `MECHX_CHAIN_RPC` environment variable if set

### Configuration Loading Priority (Expected)

**Agent Mode:**
1. ✅ Read from stored operate configuration (persisted during setup)
2. ✅ Override with `MECHX_CHAIN_RPC` environment variable if set
3. ✅ Fall back to `mechs.json` default if not found

**Client Mode:**
1. ✅ Load default from `mechs.json`
2. ✅ Override with `MECHX_CHAIN_RPC` environment variable if set

## Current Workaround

Users must set `MECHX_CHAIN_RPC` as a persistent environment variable:

```bash
# Add to ~/.bashrc or ~/.zshrc
export MECHX_CHAIN_RPC='https://your-reliable-rpc-provider'

# Then run commands
mechx setup --chain-config gnosis
mechx request --priority-mech 0x... --tools tool1 --prompts "..." --chain-config gnosis
```

This defeats the purpose of `mechx setup` storing the configuration.

## Proposed Solution

### Option 1: Load RPC from Operate Config in Agent Mode

Modify CLI commands to read RPC from stored operate configuration when in agent mode.

**Changes needed:**

1. **Create utility function** to load RPC from operate config:
   ```python
   # mech_client/infrastructure/operate/config_loader.py (new file)
   def load_rpc_from_operate(chain_config: str) -> Optional[str]:
       """Load RPC URL from stored operate configuration.

       :param chain_config: Chain name (gnosis, base, etc.)
       :return: RPC URL from operate config, or None if not found
       """
       manager = OperateManager()
       operate = manager.operate

       # Find service for this chain
       service_manager = operate.service_manager()
       for service in service_manager.json:
           if service["home_chain"] == chain_config:
               service_config_id = service["service_config_id"]
               service = service_manager.load(service_config_id)

               # Read RPC from service configuration
               if chain_config in service.chain_configs:
                   chain_data = service.chain_configs[chain_config]
                   if hasattr(chain_data, 'rpc') and chain_data.rpc:
                       return chain_data.rpc

       return None
   ```

2. **Modify `LedgerConfig.__post_init__`** to try operate config first:
   ```python
   def __post_init__(self) -> None:
       """Post initialization to override with environment variables."""
       # In agent mode, try to load from stored operate config
       if is_agent_mode():  # Need to pass this context
           operate_rpc = load_rpc_from_operate(self.chain_config)
           if operate_rpc:
               self.address = operate_rpc

       # Environment variable overrides everything
       env_rpc = os.getenv("MECHX_CHAIN_RPC")
       if env_rpc:
           self.address = env_rpc
   ```

3. **Pass agent mode context** to config loading:
   ```python
   # In CLI commands
   mech_config = get_mech_config(
       validated_chain,
       agent_mode=agent_mode
   )
   ```

**Files to modify:**
- `mech_client/infrastructure/config/chain_config.py`
- `mech_client/infrastructure/config/loader.py`
- `mech_client/infrastructure/operate/config_loader.py` (new file)
- `mech_client/cli/commands/request_cmd.py`
- `mech_client/cli/commands/deposit_cmd.py`
- `mech_client/cli/commands/subscription_cmd.py`

### Option 2: Always Require MECHX_CHAIN_RPC Environment Variable

Simplify by making `MECHX_CHAIN_RPC` required for all operations:
- Remove RPC storage during setup
- Document that users must set `MECHX_CHAIN_RPC` persistently
- Validate that `MECHX_CHAIN_RPC` is set before running commands

**Pros:** Simpler, explicit configuration
**Cons:** Less user-friendly, setup becomes less useful

### Option 3: Store RPC in a Simpler Location

Create a mech-client-specific config file that's easier to read:
- Store RPC mapping in `~/.mechx_config.json`
- Format: `{"gnosis": "https://...", "base": "https://..."}`
- Read this file in addition to operate config

**Pros:** Simpler implementation, doesn't rely on operate internals
**Cons:** Duplicates configuration, can get out of sync

## Recommendation

**Option 1** is the correct solution as it:
- Honors the configuration stored during setup
- Maintains backward compatibility
- Allows environment variable override for flexibility
- Provides the best user experience

## Testing Plan

Once fixed, test:

1. **Agent mode with stored RPC:**
   ```bash
   export MECHX_CHAIN_RPC='https://custom-rpc.example.com'
   mechx setup --chain-config gnosis
   unset MECHX_CHAIN_RPC
   mechx request --priority-mech 0x... --tools tool1 --prompts "test" --chain-config gnosis
   # Should use stored RPC, not default from mechs.json
   ```

2. **Agent mode with env var override:**
   ```bash
   export MECHX_CHAIN_RPC='https://setup-rpc.example.com'
   mechx setup --chain-config gnosis
   export MECHX_CHAIN_RPC='https://different-rpc.example.com'
   mechx request --priority-mech 0x... --tools tool1 --prompts "test" --chain-config gnosis
   # Should use different-rpc (env var override), not setup-rpc
   ```

3. **Client mode unchanged:**
   ```bash
   mechx --client-mode request --key key.txt --priority-mech 0x... --tools tool1 --prompts "test" --chain-config gnosis
   # Should use mechs.json default or MECHX_CHAIN_RPC
   ```

## Related Issues

- See [TOKEN_APPROVAL_AGENT_MODE_ISSUE.md](./TOKEN_APPROVAL_AGENT_MODE_ISSUE.md) for another agent mode issue

## References

- Setup service: `mech_client/services/setup_service.py:104-166`
- Config loading: `mech_client/infrastructure/config/chain_config.py:38-68`
- Command usage: `mech_client/cli/commands/request_cmd.py:180-185`
