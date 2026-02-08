# Unused MechConfig Fields Analysis

## Summary
Out of 10 MechConfig fields, **2 are completely unused** in the codebase.

---

## ✅ USED Fields (8 fields)

### 1. `complementary_metadata_hash_address` ✅
**Used in:** `domain/tools/manager.py` (2 occurrences)
```python
# Line 69
if self.mech_config.complementary_metadata_hash_address == ADDRESS_ZERO:

# Line 77
self.mech_config.complementary_metadata_hash_address,
```
**Purpose:** Used by ToolManager to fetch tool metadata from contract

---

### 2. `rpc_url` ✅
**Used in:** Multiple files
- `services/setup_service.py`
- `utils/errors/handlers.py`
- `utils/errors/exceptions.py`
**Purpose:** HTTP RPC endpoint for blockchain communication

---

### 3. `gas_limit` ✅
**Used in:**
- `services/deposit_service.py`
- `services/marketplace_service.py`
**Purpose:** Default gas limit for transactions

---

### 4. `transaction_url` ✅
**Used in:** `services/deposit_service.py` (2 occurrences)
```python
# Line 115
tx_url = self.mech_config.transaction_url.format(transaction_digest=tx_hash)

# Line 195
tx_url = self.mech_config.transaction_url.format(transaction_digest=tx_hash)
```
**Purpose:** Block explorer URL template for transaction links

---

### 5. `subgraph_url` ✅
**Used in:** Multiple files
- `infrastructure/subgraph/client.py`
- `infrastructure/subgraph/queries.py`
- `utils/errors/handlers.py`
- `utils/errors/exceptions.py`
**Purpose:** Subgraph GraphQL endpoint for mech list command

---

### 6. `price` ✅
**Used in:** `services/marketplace_service.py`
**Purpose:** Default price for marketplace requests

---

### 7. `mech_marketplace_contract` ✅
**Used in:**
- `services/marketplace_service.py`
- `cli/commands/deposit_cmd.py`
**Purpose:** Marketplace contract address

---

### 8. `priority_mech_address` ✅
**Used in:** `services/marketplace_service.py` (multiple occurrences)
```python
# Line 129
priority_mech_address = priority_mech or self.mech_config.priority_mech_address

# Line 143, 194, 221, 235, 273, 412
# Various uses for priority mech functionality
```
**Purpose:** Optional priority mech address for requests

---

## ❌ UNUSED Fields (2 fields)

### 1. `service_registry_contract` ❌
**Env var:** `MECHX_SERVICE_REGISTRY_CONTRACT`
**Defined in:** `configs/mechs.json` (all chains)
**Loaded in:** `chain_config.py:155-157`
**Used in:** NOWHERE

**Evidence:**
```bash
$ grep -r "service_registry_contract" mech_client/ --include="*.py" | grep -v "chain_config.py" | grep -v "mechs.json"
# NO RESULTS (except config definition)
```

**Can be removed:** ✅ YES

---

### 2. `wss_endpoint` ❌
**Env var:** `MECHX_WSS_ENDPOINT`
**Defined in:** `configs/mechs.json` (all chains)
**Loaded in:** `chain_config.py:175-177`
**Used in:** NOWHERE

**Evidence:**
```bash
$ grep -r "\.wss_endpoint" mech_client/ --include="*.py" | grep -v "chain_config.py"
# NO RESULTS (except config definition)
```

**Can be removed:** ✅ YES

---

## Recommendations

### Immediate Actions
1. **Remove unused fields:**
   - Remove `service_registry_contract` from MechConfig
   - Remove `wss_endpoint` from MechConfig
   - Remove corresponding env var overrides in `__post_init__()`
   - Remove from `configs/mechs.json`

2. **Remove unused env vars:**
   - Remove `MECHX_SERVICE_REGISTRY_CONTRACT` override logic
   - Remove `MECHX_WSS_ENDPOINT` override logic

### Why These Exist
**Likely reasons for unused fields:**
- `service_registry_contract`: May have been planned for service registry integration but never implemented
- `wss_endpoint`: May have been planned for WebSocket support (real-time events) but never implemented

### Future Considerations
If WebSocket support is needed in the future:
- Re-add `wss_endpoint` when implementing WebSocket delivery watching
- For now, all delivery watching uses HTTP RPC polling

If service registry queries are needed:
- Re-add `service_registry_contract` when implementing service registry features
- Currently not needed for any functionality

---

## Files to Update

### 1. `mech_client/infrastructure/config/chain_config.py`
Remove from MechConfig dataclass:
- Line 133: `service_registry_contract: str`
- Line 136: `wss_endpoint: str`

Remove from `__post_init__()`:
- Lines 155-157: MECHX_SERVICE_REGISTRY_CONTRACT override
- Lines 175-177: MECHX_WSS_ENDPOINT override

### 2. `mech_client/configs/mechs.json`
Remove from all chain configs (gnosis, arbitrum, polygon, base, celo, optimism):
- `"service_registry_contract"` field
- `"wss_endpoint"` field

### 3. Documentation
Update ENV_VAR_ANALYSIS.md to remove references to:
- MECHX_SERVICE_REGISTRY_CONTRACT
- MECHX_WSS_ENDPOINT

---

## Impact Assessment

### Low Risk ✅
- No code references these fields (except config definition)
- No tests reference these fields
- No CLI commands use these fields
- Removal is safe and will not break any functionality

### Benefits
- Reduces config complexity
- Removes confusing unused env vars
- Clearer user documentation
- Smaller JSON config files
- Less maintenance burden
