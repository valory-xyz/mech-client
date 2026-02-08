# Token Approval Agent Mode Issue

## Status: ✅ FIXED

**Fixed in:** v0.18.1 (2026-02-08)

## Problem (Historical)

The `TokenPaymentStrategy.approve_if_needed()` method in `mech_client/domain/payment/token.py` only implemented the client mode path. In agent mode, token approvals needed to go through the Safe multisig, otherwise the approval came from the EOA instead of the Safe address, and subsequent token transfers from the Safe would fail due to insufficient allowance.

## Current Implementation

**File:** `mech_client/domain/payment/token.py:85-138`

```python
def approve_if_needed(
    self,
    payer_address: str,
    spender_address: str,
    amount: int,
    private_key: Optional[str] = None,
) -> Optional[str]:
    # ... validation ...

    # Client mode: build, sign, and send
    if self.crypto or private_key:
        if not self.crypto:
            raise ValueError("Crypto object required for token approval")
        crypto = self.crypto
        raw_transaction = self.ledger_api.build_transaction(
            contract_instance=token_contract,
            method_name=method_name,
            method_args=method_args,
            tx_args=tx_args,
            raise_on_try=True,
        )
        signed_transaction = crypto.sign_transaction(raw_transaction)
        transaction_digest = self.ledger_api.send_signed_transaction(
            signed_transaction,
            raise_on_try=True,
        )
        return transaction_digest

    return None
```

**Issue:** This builds, signs, and sends the approval transaction directly from the EOA. In agent mode, this means:
1. The approval is set for the EOA address (not the Safe)
2. When the Safe tries to transfer tokens, it doesn't have approval
3. The token transfer fails with "ERC20: insufficient allowance"

## How It Should Work

### Agent Mode Flow
1. User calls `mechx request` with agent mode (default)
2. MarketplaceService calls `payment_strategy.approve_if_needed()`
3. **Should:** Approval goes through Safe multisig via `executor.execute_transaction()`
4. **Currently:** Approval goes directly from EOA via `crypto.sign_transaction()`
5. Result: Safe has no approval, subsequent transfer fails

### Executor Pattern

The codebase uses the executor pattern to handle both modes:

**Agent Mode (`AgentExecutor`):**
```python
executor.execute_transaction(
    contract=token_contract,
    method_name="approve",
    method_args={"_to": spender_address, "_value": amount},
    tx_args={"sender_address": safe_address, "value": 0, "gas": 60000},
)
# → Executes through Safe.execTransaction()
```

**Client Mode (`ClientExecutor`):**
```python
executor.execute_transaction(...)
# → Builds, signs, and sends directly from EOA
```

## Proposed Solution

### 1. Update `approve_if_needed()` signature

```python
def approve_if_needed(
    self,
    payer_address: str,
    spender_address: str,
    amount: int,
    executor: Optional["TransactionExecutor"] = None,  # Add this
    private_key: Optional[str] = None,
) -> Optional[str]:
```

### 2. Use executor if provided

```python
# Use executor if provided (handles both agent and client mode)
if executor:
    return executor.execute_transaction(
        contract=token_contract,
        method_name=method_name,
        method_args=method_args,
        tx_args=tx_args,
    )

# Fallback: client mode without executor (backward compatibility)
if self.crypto or private_key:
    # ... existing client mode code ...

raise ValueError(
    "Transaction executor or crypto object/private key required for token approval"
)
```

### 3. Update caller in `marketplace_service.py`

**Current (line 194):**
```python
payment_strategy.approve_if_needed(
    payer_address=sender,
    spender_address=balance_tracker,
    amount=price,
    private_key=self.private_key,
)
```

**Should be:**
```python
payment_strategy.approve_if_needed(
    payer_address=sender,
    spender_address=balance_tracker,
    amount=price,
    executor=self.executor,  # Add this
    private_key=self.private_key,
)
```

## Impact

**Current State:**
- ❌ Token payments fail in agent mode
- ✅ Token payments work in client mode (EOA)

**After Fix:**
- ✅ Token payments work in agent mode (Safe)
- ✅ Token payments work in client mode (EOA)

## Related Files

- `mech_client/domain/payment/token.py` - Token payment strategy (needs fix)
- `mech_client/services/marketplace_service.py:194` - Caller (needs update)
- `mech_client/domain/execution/base.py` - Executor interface
- `mech_client/domain/execution/agent_executor.py` - Agent mode executor
- `mech_client/domain/execution/client_executor.py` - Client mode executor

## Testing Recommendation

After implementing the fix:
1. Test token payment in client mode (--client-mode flag)
2. Test token payment in agent mode (default)
3. Verify approval transaction goes through Safe in agent mode
4. Verify subsequent transfer succeeds

## References

- Similar pattern is used correctly for the main request transaction
- See `AgentExecutor.execute_transaction()` for Safe execution pattern
- See `ClientExecutor.execute_transaction()` for EOA execution pattern

## Fix Summary

The fix was implemented successfully with the following changes:

1. **Updated base class** (`mech_client/domain/payment/base.py`): Added `executor` parameter to `approve_if_needed()` signature
2. **Updated token strategy** (`mech_client/domain/payment/token.py`): Implemented executor-based approval with fallback to direct signing
3. **Updated other strategies** (`native.py`, `nvm.py`): Updated signatures to match base class
4. **Updated callers**:
   - `mech_client/services/marketplace_service.py:181` - Now passes `executor=self.executor`
   - `mech_client/services/deposit_service.py:159` - Now passes `executor=self.executor`
5. **Added comprehensive tests** (`tests/unit/domain/test_payment_strategies.py`):
   - Test approval with executor (agent mode)
   - Test approval without executor (client mode, backward compatibility)
   - Test error handling when neither executor nor crypto provided

**Result:**
- ✅ Token payments work in agent mode (Safe multisig)
- ✅ Token payments work in client mode (EOA)
- ✅ All 309 unit tests pass
- ✅ All linters pass (pylint 10.00/10)
