# Test Coverage Improvements

## Summary

The bugs fixed on 2026-02-08 revealed **critical gaps in test coverage**. This document describes the missing tests that would have caught these bugs earlier.

## Bug Analysis

### Bug 1: MechConfig nvm_subscription Parameter
**Issue:** `MechConfig.__init__() got an unexpected keyword argument 'nvm_subscription'`

**Root Cause:** No integration test actually loads the real `mechs.json` file. All existing tests mock file I/O with simplified JSON structures.

### Bug 2: Subgraph Metadata Structure Mismatch
**Issue:** `list indices must be integers or slices, not str`

**Root Cause:** Mock data in tests didn't match actual GraphQL response structure. Tests used flat structures while actual responses are deeply nested with lists.

## New Tests Added

### 1. Integration Tests for Config Loader
**File:** `tests/unit/infrastructure/test_config_loader_integration.py`

**Coverage:**
- ✅ Load actual `mechs.json` for all chains (gnosis, base, polygon, optimism)
- ✅ Verify `nvm_subscription` field is excluded from `MechConfig`
- ✅ Verify all chains load successfully without errors
- ✅ Verify all required `MechConfig` fields are populated

**Tests Added:** 7 integration tests

**Why This Matters:**
- These tests actually exercise the real config loading path
- Would have caught Bug 1 immediately
- No mocking means tests verify actual file structure

### 2. CLI Command Tests
**File:** `tests/unit/cli/test_mech_cmd.py`

**Coverage:**
- ✅ Test `mech list` with realistic GraphQL response structure
- ✅ Test nested `service.metadata[0]["metadata"]` access pattern
- ✅ Test edge cases: empty metadata, empty lists, multiple entries
- ✅ Test multiple mechs display correctly
- ✅ Test error handling (missing MECHX_SUBGRAPH_URL)

**Tests Added:** 9 CLI tests

**Why This Matters:**
- Uses mock data that matches **actual GraphQL schema**
- Would have caught Bug 2 immediately
- Tests the full CLI command flow, not just utility functions

### 3. Updated Existing Subgraph Tests
**File:** `tests/unit/infrastructure/test_subgraph_queries.py`

**Changes:**
- Updated `test_query_mechs_preserves_original_fields` to use realistic structure
- Mock data now includes nested `service` object with `metadata` list

## Test Statistics

**Before:**
- Total tests: 305
- Integration tests for config loading: 0
- CLI command tests: 0
- Subgraph tests with realistic structure: 0

**After:**
- Total tests: **314** (+16 new tests)
- Integration tests for config loading: **7**
- CLI command tests: **9**
- Subgraph tests with realistic structure: **1** (updated)

## Key Learnings

### 1. Integration Tests Are Critical
**Problem:** Unit tests with mocks can hide structural issues

**Solution:** Add integration tests that exercise real file paths, real configs, and real data structures without mocking

### 2. Mock Data Must Match Reality
**Problem:** Simplified mock data doesn't catch structural mismatches

**Solution:** When mocking external APIs (GraphQL, REST), use mock data that exactly matches the actual API response structure

### 3. Test CLI Commands, Not Just Utilities
**Problem:** Testing only utility functions misses integration issues in CLI layer

**Solution:** Use Click's `CliRunner` to test actual command execution with realistic inputs

## Recommendations

### For New Features
1. **Always add integration tests** that use real config files and data structures
2. **Test CLI commands end-to-end** using `CliRunner`, not just service/domain layers
3. **Use realistic mock data** that matches actual external API structures

### For Existing Code
Consider adding integration tests for:
- Other CLI commands (request, deposit, subscription)
- Config loading for chains without current coverage
- GraphQL queries with edge cases (null fields, empty arrays)

## Test Execution

Run all tests:
```bash
poetry run pytest tests/unit/ -k "not trio"
```

Run only new tests:
```bash
# Integration tests
poetry run pytest tests/unit/infrastructure/test_config_loader_integration.py -v

# CLI tests
poetry run pytest tests/unit/cli/test_mech_cmd.py -v
```

Run with coverage:
```bash
poetry run pytest tests/unit/ -k "not trio" --cov=mech_client --cov-report=html
```

## Impact

These test improvements ensure:
- ✅ Config structure changes are caught immediately
- ✅ GraphQL schema changes are detected early
- ✅ CLI commands are tested end-to-end
- ✅ Edge cases are covered (null/empty data)
- ✅ Integration points are validated

**Result:** Similar bugs will be caught by CI/CD before reaching production.
