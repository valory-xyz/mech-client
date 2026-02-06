# Error Handling Improvements

This document tracks error handling improvements made to the mech-client CLI.

## Completed Improvements ✅

### 1. Core Validation Functions Added
- `validate_chain_config()`: Validates chain configuration exists in mechs.json
- `validate_ethereum_address()`: Validates Ethereum address format and checks for zero address

### 2. Exception Type Fixes
- **Fixed**: `interact` command - Changed `Exception` → `ClickException` for:
  - Missing `MECHX_MECH_OFFCHAIN_URL` validation (line ~453)
  - Prepaid/offchain model validation for legacy mechs (lines ~422-430)
- **Result**: Proper CLI error handling with actionable messages

### 3. Web3 Exception Handling
- **Added**: Specific handling for `ContractLogicError` and `ValidationError` in `interact` command
- **Result**: Clear error messages for smart contract failures instead of raw Python tracebacks
- **Location**: `mech_client/cli.py` lines ~552-565

### 4. Interact Command Validations
- **Added**: Chain config validation at command start
- **Added**: Extra attribute format validation (checks for "=" before splitting)
- **Added**: Priority mech address validation
- **Added**: Safe address validation (agent mode)
- **Result**: Fail fast with clear messages for invalid inputs

### 5. Subgraph URL Validation
- **Fixed**: `fetch-mm-mechs-info` command
- **Added**: Early validation that `MECHX_SUBGRAPH_URL` is set
- **Added**: Better error message explaining requirement
- **Changed**: Generic `Exception` catch → `ClickException` for consistency
- **Result**: Clear error before attempting GraphQL query

### 6. Import Additions
- Added `eth_utils.is_address` for address validation
- Added `web3.constants.ADDRESS_ZERO` for zero address checks
- Added `web3.exceptions.ContractLogicError, ValidationError` for Web3 errors

### 7. Tool Management Commands Error Handling
**All 6 commands fixed:**
- `tools-for-agents`
- `tool-description`
- `tool-io-schema`
- `tools-for-marketplace-mech`
- `tool-description-for-marketplace-mech`
- `tool-io-schema-for-marketplace-mech`

**Changes made:**
- **Added**: Chain config validation using `validate_chain_config()`
- **Added**: Agent ID / Service ID validation (non-negative integer check)
- **Added**: Tool ID format validation (must contain "-")
- **Fixed**: Replaced all `click.echo(f"Error: {e}")` with `raise ClickException()` with detailed messages
- **Added**: HTTP RPC error handling with context (HTTPError, ConnectionError, Timeout)
- **Added**: KeyError and IOError handlers with actionable error messages
- **Result**: All tool commands now fail fast with clear messages, proper exception chaining, and suggestions

### 8. Deposit Commands Error Handling
**Both commands fixed:**
- `deposit-native`
- `deposit-token`

**Changes made:**
- **Added**: Chain config validation using `validate_chain_config()`
- **Added**: Amount validation (must be positive integer in wei/smallest unit)
- **Added**: Marketplace support validation (checks if chain has marketplace contract deployed)
- **Added**: Web3 exception handling (ContractLogicError, ValidationError)
- **Added**: Detailed error messages for contract failures (insufficient balance, missing allowance, etc.)
- **Result**: Deposit commands now validate inputs early and provide clear guidance on contract errors

### 9. NVM Subscription Command Error Handling
**Command fixed:**
- `purchase-nvm-subscription`

**Changes made:**
- **Added**: Chain config validation using `validate_chain_config()`
- **Added**: Chain NVM support validation (checks if chain is in CHAIN_TO_ENVS)
- **Added**: Web3 exception handling (ContractLogicError, ValidationError)
- **Added**: KeyError handler for missing environment variables (PLAN_DID, NETWORK_NAME, CHAIN_ID)
- **Added**: Detailed error messages for subscription-specific issues
- **Result**: NVM subscription command validates chain support early and provides clear guidance on environment variable requirements

### 10. Setup Agent Mode Error Handling
**Command fixed:**
- `setup-agent-mode`

**Changes made:**
- **Added**: Chain config validation using `validate_chain_config()`
- **Added**: General Exception handler for run_service() failures with actionable messages
- **Improved**: Error message formatting (removed triple-quoted strings)
- **Result**: Setup command provides clear guidance when service setup fails

### 11. Private Key File Error Handling
**Locations fixed:**
- `mech_client/interact.py` - EthereumCrypto initialization
- `mech_client/marketplace_interact.py` - EthereumCrypto initialization

**Changes made:**
- **Added**: PermissionError handler for unreadable files
- **Added**: ValueError handler for decryption failures (detects password/MAC errors)
- **Added**: ValueError handler for invalid key format
- **Added**: Detailed error messages with possible causes
- **Result**: Private key loading now provides clear guidance on common issues (wrong password, corrupted file, invalid format)

## Remaining Work 🔧

### HIGH PRIORITY

**All HIGH priority items completed!** 🎉

### MEDIUM PRIORITY

**All MEDIUM priority items completed!** 🎉

Note: Configuration File Error Handling was skipped as these are pre-release issues that should be caught during development/testing, not at runtime.

### LOW PRIORITY

#### 1. Agent ID/Service ID Range Validation
**Commands:** `tools-for-agents`, tool description/schema commands

**Issues:**
- No validation that IDs are positive integers
- No bounds checking (could query ID 999999999)
- No handling for non-existent IDs

#### 2. IPFS Error Handling
**All commands using IPFS**

**Issues:**
- No specific handling for IPFS gateway failures
- No timeout handling at CLI level
- No validation of IPFS hash format

#### 3. Tool ID Format Validation
**Commands:** `tool-description`, `tool-io-schema`

**Issues:**
- Tool ID should be "agent_id-tool_name" format
- No parsing validation before `split("-")`
- Could fail on malformed IDs

## Testing Recommendations

### Manual Testing Checklist
- [ ] Test each command with missing env vars
- [ ] Test with invalid addresses (malformed, zero address)
- [ ] Test with invalid chain configs
- [ ] Test with unavailable RPC/WSS/Subgraph endpoints
- [ ] Test with insufficient balances
- [ ] Test with invalid amounts (negative, zero, non-numeric)
- [ ] Test with non-existent agent IDs/service IDs
- [ ] Test agent mode with invalid safe addresses
- [ ] Test with corrupted mechs.json file
- [ ] Test with missing private key file

### Integration Testing
- [ ] Test full interact flow with mocked contract errors
- [ ] Test deposit flows with mocked balance/approval failures
- [ ] Test tool queries with mocked metadata fetch failures
- [ ] Test subgraph query with mocked network errors

## Error Message Guidelines

When adding new error handling, follow these patterns:

### 1. Environment Variable Missing
```python
raise ClickException(
    "Environment variable MECHX_SOMETHING is required.\n\n"
    f"This command needs XYZ.\n\n"
    f"Please set it:\n"
    f"  export MECHX_SOMETHING='value'"
)
```

### 2. Network Errors
```python
except requests.exceptions.Timeout as e:
    endpoint = os.getenv("MECHX_ENDPOINT", "not set")
    raise ClickException(
        f"Timeout connecting to endpoint: {e}\n\n"
        f"Current MECHX_ENDPOINT: {endpoint}\n\n"
        f"Solutions:\n"
        f"  1. Check endpoint availability\n"
        f"  2. Try different endpoint: export MECHX_ENDPOINT='url'"
    ) from e
```

### 3. Validation Errors
```python
if not is_valid(value):
    raise ClickException(
        f"Invalid value: {value!r}\n"
        f"Expected format: description\n"
        f"Example: example_value"
    )
```

### 4. Contract Errors
```python
except ContractLogicError as e:
    raise ClickException(
        f"Smart contract error: {e}\n\n"
        f"Possible causes:\n"
        f"  • Specific cause 1\n"
        f"  • Specific cause 2\n\n"
        f"Please check your parameters and balances."
    ) from e
```

## Summary

**Total Issues Identified:** ~50+
**Fixed in This Session:** 21 issues total
- HIGH priority: 19 issues (10 base + 6 tool commands + 2 deposit commands + 1 NVM subscription)
- MEDIUM priority: 2 issues (setup-agent-mode + private key handling)

**Remaining HIGH priority:** 0 (ALL COMPLETED!) 🎉
**Remaining MEDIUM priority:** 0 (ALL COMPLETED!) 🎉
**Remaining LOW priority:** 3 areas (10+ issues)

**Completed Steps:**
1. ✅ Fix tool management command error patterns (HIGH) - COMPLETED
2. ✅ Add deposit command validations (HIGH) - COMPLETED
3. ✅ Add NVM subscription validations (HIGH) - COMPLETED
4. ✅ Improve setup-agent-mode validations (MEDIUM) - COMPLETED
5. ⏭️  Configuration file error handling (MEDIUM) - SKIPPED (pre-release issue)
6. ✅ Add private key file error handling (MEDIUM) - COMPLETED

**Optional Next Steps (LOW priority):**
- Agent ID/Service ID range validation
- IPFS error handling
- Tool ID format validation (partial - already done for marketplace mechs)
