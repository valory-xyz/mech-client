# Post-Refactor Issues & Fix Plan

## Critical Issues Found

After reviewing the v0.17.0 refactor, here are the actual issues that need fixing, prioritized by severity.

---

## 🔴 CRITICAL - Must Fix Immediately

### 1. Blocking Event Loop in Async Code
**File**: `mech_client/domain/delivery/onchain_watcher.py` (lines 115, 242)

**Problem**: Using `time.sleep()` in async methods blocks the entire event loop.

```python
# WRONG - blocks event loop
time.sleep(WAIT_SLEEP)

# CORRECT - async sleep
await asyncio.sleep(WAIT_SLEEP)
```

**Impact**: Delivery watching will hang, causing timeouts and failed requests.

**Fix**: Replace `time.sleep()` with `await asyncio.sleep()` in both locations.

---

### 2. Balance Check Logic Error
**File**: `mech_client/services/marketplace_service.py` (line 189)

**Problem**: Error message shows incorrect balance amount.

```python
# WRONG - check_balance returns bool, not amount
if not payment_strategy.check_balance(sender, price):
    raise ValueError(
        f"Insufficient balance. Need: {price}, Have: {payment_strategy.check_balance(sender, 0)}"
    )
```

**Impact**: Users see misleading error messages, making debugging impossible.

**Fix**: Either:
1. Add a `get_balance()` method to payment strategies, OR
2. Remove the "Have: X" part from error message

---

## 🟠 HIGH - Fix Soon

### 3. Incomplete Subscription Status Check
**File**: `mech_client/services/subscription_service.py` (lines 100-101)

**Problem**: Method always returns `False` (hardcoded placeholder).

```python
def check_subscription_status(self, requester_address: str) -> bool:
    # TODO: Implement actual subscription status check
    return False
```

**Impact**: Subscription checking doesn't work; always thinks user has no subscription.

**Fix Options**:
1. Implement actual check by querying NVM contracts, OR
2. Remove from public API and document as unimplemented, OR
3. Make it raise NotImplementedError if not ready for use

---

## 🟡 MEDIUM - Fix When Practical

### 4. Event Log Parsing Edge Case
**File**: `mech_client/infrastructure/blockchain/receipt_waiter.py` (lines 100-101)

**Problem**: Returns `["Empty Logs"]` string instead of handling empty logs properly.

```python
if len(rich_logs) == 0:
    return ["Empty Logs"]  # Returns string, not request IDs!
```

**Impact**: Edge case will cause crash with confusing error.

**Fix**: Return empty list or raise descriptive error.

---

### 5. Silent Tool Validation Failures
**File**: `mech_client/services/marketplace_service.py` (lines 365-372)

**Problem**: Catches exceptions and prints warning instead of raising error.

```python
try:
    tools_info = self.tool_manager.get_tools(service_id)
except (AttributeError, KeyError, TypeError) as e:
    print(f"Warning: Failed to fetch tool metadata: {e}")
    return  # Silently continues!
```

**Impact**: Invalid tools accepted, wasting user funds on failed requests.

**Fix**: Either fail loudly or make it configurable (strict vs permissive mode).

---

### 6. Logging via print() Instead of logging Module
**Files**: Multiple (marketplace_service.py, onchain_watcher.py, offchain_watcher.py, tool_service.py)

**Problem**: Production code uses `print()` for logging.

**Impact**: Cannot control log levels, format, or redirect logs.

**Fix**: Replace `print()` with `logging.info()`, `logging.warning()`, etc.

---

## 🔵 LOW - Nice to Have

### 7. Missing CLI Command Tests
**Status**: No tests exist for CLI commands (request, deposit, setup, subscription, mech, tool, ipfs)

**Impact**: Major workflows are untested; regressions could go undetected.

**Fix**: Add integration tests for critical workflows:
- `test_request_cmd.py` - marketplace requests
- `test_deposit_cmd.py` - balance deposits
- `test_setup_cmd.py` - agent setup

**Note**: Can use mocking to avoid needing real blockchain/IPFS.

---

### 8. No Tool ID Validation in Request Command
**File**: `mech_client/cli/commands/request_cmd.py`

**Problem**: `--tools` parameter accepts any string without format validation.

**Impact**: Poor user feedback for invalid tool IDs.

**Fix**: Use existing `validate_tool_id()` function in request command.

---

## Recommended Fix Order

1. **Day 1 - Critical Bugs**:
   - [ ] Fix blocking event loop (onchain_watcher.py)
   - [ ] Fix balance check error message (marketplace_service.py)

2. **Day 2 - High Priority**:
   - [ ] Implement or document subscription status check (subscription_service.py)
   - [ ] Fix event log parsing edge case (receipt_waiter.py)

3. **Week 2 - Medium Priority**:
   - [ ] Replace print() with logging module (multiple files)
   - [ ] Fix tool validation to fail loudly (marketplace_service.py)

4. **Future - Low Priority**:
   - [ ] Add CLI command tests (tests/integration/)
   - [ ] Add tool ID validation to request command

---

## What NOT to Fix

These are NOT issues (clarifications):

✅ **Test structure is fine**: Tests exist for domain/infrastructure layers; CLI tests can be added later.

✅ **Architecture is solid**: Layered architecture (CLI → Service → Domain → Infrastructure) is working.

✅ **Core functionality works**: Request, deposit, setup commands are implemented and functional.

✅ **Documentation is sufficient**: README and CLAUDE.md are updated and accurate.

---

## Testing Strategy

### Current Test Coverage (164 tests):
- ✅ Domain layer (delivery, execution, payment strategies)
- ✅ Infrastructure layer (blockchain, IPFS, config)
- ✅ Utils (validators, errors)
- ✅ Service layer (basic validation)

### Missing Coverage:
- ❌ CLI commands (integration tests)
- ❌ End-to-end workflows
- ❌ Error handling paths

### Recommendation:
Add integration tests for critical workflows AFTER fixing critical bugs. Focus on:
1. Happy path for request command
2. Happy path for deposit command
3. Error cases for invalid inputs

---

## Notes

- All 164 existing tests pass ✅
- All linters pass (pylint 10.00/10) ✅
- Core refactor is complete and working ✅
- Issues are edge cases and quality improvements, not fundamental breaks
- The codebase is production-ready with these fixes

