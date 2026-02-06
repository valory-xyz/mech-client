# Migration Guide

This guide helps developers migrate code from pre-v0.17.0 to the new layered architecture introduced in v0.17.0.

## Table of Contents

- [Overview](#overview)
- [What Changed](#what-changed)
- [Migration Checklist](#migration-checklist)
- [Module Mappings](#module-mappings)
- [Common Migration Patterns](#common-migration-patterns)
- [Breaking Changes](#breaking-changes)
- [Examples](#examples)

## Overview

Version 0.17.0 introduced a comprehensive architectural refactoring that:
- Separated concerns into distinct layers (CLI, Service, Domain, Infrastructure)
- Introduced the Strategy pattern for payments and execution
- Replaced monolithic modules with focused, single-responsibility components
- Improved testability through dependency injection

This migration guide helps you update code that depends on mech-client internals.

**Note**: If you only use the CLI (`mechx` command), no migration is needed. The CLI interface remains stable.

## What Changed

### High-Level Changes

| Aspect | Before v0.17.0 | After v0.17.0 |
|--------|----------------|----------------|
| **Structure** | Flat module structure | Layered architecture |
| **Payment** | Scattered payment logic | Payment strategies |
| **Execution** | Mixed execution modes | Execution strategies |
| **Delivery** | Inline delivery code | Delivery watchers |
| **Config** | Various config files | Centralized config layer |
| **Testing** | Limited tests | Comprehensive test suite |

### File Relocations

Major components moved to new locations:

```
OLD: mech_client/interact.py (monolithic)
NEW:
  - mech_client/services/marketplace_service.py
  - mech_client/domain/payment/*.py
  - mech_client/domain/execution/*.py
  - mech_client/domain/delivery/*.py

OLD: mech_client/mech_tool.py
NEW:
  - mech_client/services/tool_service.py
  - mech_client/domain/tools/marketplace_manager.py

OLD: mech_client/subgraph.py
NEW:
  - mech_client/infrastructure/subgraph/client.py
  - mech_client/infrastructure/subgraph/queries.py

OLD: mech_client/ipfs.py
NEW:
  - mech_client/infrastructure/ipfs/client.py
  - mech_client/infrastructure/ipfs/converters.py

OLD: mech_client/safe_tx.py
NEW:
  - mech_client/infrastructure/blockchain/safe_client.py
  - mech_client/domain/execution/agent.py
```

## Migration Checklist

Use this checklist when migrating:

- [ ] **Update imports** to new module locations
- [ ] **Replace direct function calls** with service/strategy calls
- [ ] **Update payment logic** to use PaymentStrategy
- [ ] **Update execution logic** to use TransactionExecutor
- [ ] **Update delivery logic** to use DeliveryWatcher
- [ ] **Replace config access** with MechConfig
- [ ] **Update error handling** to use custom exceptions
- [ ] **Add type hints** if missing
- [ ] **Write/update tests** using new testing patterns
- [ ] **Run linters** to ensure code quality

## Module Mappings

### Core Functionality

#### Marketplace Interactions

**Before:**
```python
from mech_client.interact import (
    interact,
    get_balances,
    deposit_token,
)

# Call functions directly
result = interact(
    prompt=prompt,
    tool=tool,
    # ... many parameters
)
```

**After:**
```python
from mech_client.services.marketplace_service import MarketplaceService
from mech_client.domain.payment import PaymentType

# Create service
service = MarketplaceService(
    chain_config="gnosis",
    ledger_api=ledger_api,
    payer_address=address,
    # ... dependencies
)

# Use service method
result = service.send_request(
    priority_mech=mech_address,
    tools=[tool],
    prompts=[prompt],
    payment_type=PaymentType.NATIVE,
)
```

#### Tool Operations

**Before:**
```python
from mech_client.mech_tool import (
    list_all_tools_for_marketplace_mech,
    get_tool_description,
)

tools = list_all_tools_for_marketplace_mech(service_id, chain_config)
description = get_tool_description(tool_id, chain_config)
```

**After:**
```python
from mech_client.services.tool_service import ToolService

# Create service
service = ToolService(
    chain_config="gnosis",
    ledger_api=ledger_api,
)

# Use service methods
tools = service.list_tools(service_id=service_id)
description = service.get_description(tool_id=tool_id)
```

#### Subgraph Queries

**Before:**
```python
from mech_client.subgraph import query_mechs

mechs = query_mechs(chain_config)
```

**After:**
```python
from mech_client.infrastructure.subgraph.client import SubgraphClient

# Create client
client = SubgraphClient(subgraph_url=subgraph_url)

# Query mechs
result = client.query_mechs(
    order_by="service__totalDeliveries",
    order_direction="desc",
)
mechs = result["meches"]
```

#### IPFS Operations

**Before:**
```python
from mech_client.ipfs import push_to_ipfs, get_from_ipfs

# Upload
v1_hash, v1_hex = push_to_ipfs(file_path)

# Download
data = get_from_ipfs(ipfs_hash, request_id)
```

**After:**
```python
from mech_client.infrastructure.ipfs.client import IPFSClient

# Create client
client = IPFSClient()

# Upload
v1_hash, v1_hex = client.upload(file_path)

# Download
data = client.get_json(ipfs_hash, request_id)
```

### Configuration

**Before:**
```python
# Direct config file access
from mech_client.configs import mechs

chain_config = mechs["gnosis"]
marketplace_contract = chain_config["mech_marketplace_contract"]
```

**After:**
```python
from mech_client.infrastructure.config import get_mech_config

# Load config
config = get_mech_config("gnosis")
marketplace_contract = config.mech_marketplace_contract
rpc_url = config.rpc_url  # Respects MECHX_CHAIN_RPC env var
```

### Validation

**Before:**
```python
# Manual validation
if not address.startswith("0x") or len(address) != 42:
    raise ValueError("Invalid address")

if amount <= 0:
    raise ValueError("Amount must be positive")
```

**After:**
```python
from mech_client.utils.validators import (
    validate_ethereum_address,
    validate_amount,
)

# Use validators
validate_ethereum_address(address)
validate_amount(amount)
```

### Error Handling

**Before:**
```python
# Generic exceptions
raise Exception("RPC connection failed")
raise ValueError("Invalid payment type")
```

**After:**
```python
from mech_client.utils.errors import RpcError, ValidationError

# Specific exceptions with context
raise RpcError("Connection failed", rpc_url=rpc_url)
raise ValidationError("Invalid payment type", value=payment_type)
```

## Common Migration Patterns

### Pattern 1: Payment Logic

**Before (mixed payment logic):**
```python
def send_request_with_native_payment(
    marketplace_contract,
    ledger_api,
    payer,
    amount,
):
    # Check balance
    balance = ledger_api.get_balance(payer)
    if balance < amount:
        raise ValueError("Insufficient balance")

    # Send transaction
    tx = marketplace_contract.functions.request(
        # ... params
    ).build_transaction({
        "from": payer,
        "value": amount,
    })

    # Sign and send
    # ... execution logic
```

**After (using strategies):**
```python
from mech_client.domain.payment import (
    PaymentStrategyFactory,
    PaymentType,
)

def send_request(
    marketplace_contract,
    ledger_api,
    payer,
    amount,
    payment_type,
):
    # Get strategy
    strategy = PaymentStrategyFactory.create(
        payment_type=payment_type,
        ledger_api=ledger_api,
    )

    # Check balance (strategy-specific)
    if not strategy.check_balance(payer, amount):
        raise ValueError("Insufficient balance")

    # Approve if needed (strategy-specific)
    strategy.approve_if_needed(payer, amount, marketplace_address)

    # Build transaction (strategy provides payment params)
    # ... rest of logic
```

### Pattern 2: Execution Logic

**Before (mixed execution modes):**
```python
def execute_transaction(tx_params, agent_mode, safe_address=None):
    if agent_mode:
        # Safe execution logic
        from mech_client.safe_tx import send_safe_tx
        return send_safe_tx(safe_address, tx_params)
    else:
        # Direct execution logic
        signed_tx = ledger_api.sign_transaction(tx_params)
        return ledger_api.send_signed_transaction(signed_tx)
```

**After (using strategies):**
```python
from mech_client.domain.execution import ExecutorFactory

def execute_transaction(tx_params, mode, ledger_api, safe_address=None):
    # Get executor
    executor = ExecutorFactory.create(
        mode=mode,
        ledger_api=ledger_api,
        safe_address=safe_address,
    )

    # Execute (mode-specific)
    return executor.execute(tx_params)
```

### Pattern 3: Delivery Watching

**Before (inline polling):**
```python
def wait_for_delivery(request_id, marketplace_contract, timeout=900):
    start_time = time.time()
    while True:
        result = marketplace_contract.functions.mapRequestIdInfos(
            bytes.fromhex(request_id)
        ).call()

        if result[1] != ADDRESS_ZERO:
            return result

        if time.time() - start_time > timeout:
            raise TimeoutError("Delivery timeout")

        time.sleep(3)
```

**After (using watcher):**
```python
from mech_client.domain.delivery import OnchainDeliveryWatcher

async def wait_for_delivery(
    request_id,
    marketplace_contract,
    ledger_api,
    timeout=900,
):
    watcher = OnchainDeliveryWatcher(
        marketplace_contract=marketplace_contract,
        ledger_api=ledger_api,
        timeout=timeout,
    )

    results = await watcher.watch([request_id])
    return results[request_id]
```

### Pattern 4: Configuration Access

**Before (direct dictionary access):**
```python
import json
from pathlib import Path

def load_config(chain):
    config_path = Path(__file__).parent / "configs" / "mechs.json"
    with open(config_path) as f:
        configs = json.load(f)
    return configs[chain]

config = load_config("gnosis")
marketplace = config["mech_marketplace_contract"]
rpc = config.get("rpc_url", "https://default.rpc.com")
```

**After (using config loader):**
```python
from mech_client.infrastructure.config import get_mech_config

# Load config (handles env var overrides)
config = get_mech_config("gnosis")
marketplace = config.mech_marketplace_contract
rpc = config.rpc_url  # Respects MECHX_CHAIN_RPC
```

## Breaking Changes

### 1. Function Signatures

Many functions have new signatures:

**Before:**
```python
interact(
    prompt: str,
    tool: str,
    agent_id: int,
    private_key_path: str,
    chain_config: str,
    # ... 20+ parameters
)
```

**After:**
```python
# Now split into service initialization and method call
service = MarketplaceService(
    chain_config=chain_config,
    ledger_api=ledger_api,
    # ... configuration
)

service.send_request(
    priority_mech=mech_address,
    tools=[tool],
    prompts=[prompt],
    # ... request-specific params
)
```

### 2. Return Types

Some return types changed for clarity:

**Before:**
```python
# Returns mixed types
def get_tool_info(tool_id: str) -> dict:
    return {
        "name": "tool_name",
        "description": "...",
        # ... unstructured dict
    }
```

**After:**
```python
from mech_client.domain.tools import ToolInfo

# Returns typed dataclass
def get_tool_info(tool_id: str) -> ToolInfo:
    return ToolInfo(
        tool_name="tool_name",
        unique_identifier=tool_id,
        # ... typed structure
    )
```

### 3. Module Locations

All internal modules relocated:

```python
# OLD IMPORTS (broken in v0.17.0)
from mech_client.interact import interact
from mech_client.mech_tool import list_all_tools_for_marketplace_mech
from mech_client.subgraph import query_mechs
from mech_client.ipfs import push_to_ipfs

# NEW IMPORTS (v0.17.0+)
from mech_client.services.marketplace_service import MarketplaceService
from mech_client.services.tool_service import ToolService
from mech_client.infrastructure.subgraph.client import SubgraphClient
from mech_client.infrastructure.ipfs.client import IPFSClient
```

### 4. Payment Types

Payment configuration changed to use enum:

**Before:**
```python
# String-based payment types
payment_type = "native"
payment_type = "token"
```

**After:**
```python
from mech_client.domain.payment import PaymentType

# Enum-based payment types
payment_type = PaymentType.NATIVE
payment_type = PaymentType.TOKEN
payment_type = PaymentType.NATIVE_NVM
```

### 5. Async Functions

Some functions now use async/await:

**Before:**
```python
# Synchronous
def watch_for_delivery(request_ids):
    # ... polling logic
    return results
```

**After:**
```python
# Asynchronous
async def watch(self, request_ids: List[str]) -> Dict[str, Any]:
    # ... async polling logic
    return results

# Usage
results = await watcher.watch(request_ids)
```

## Examples

### Example 1: Sending a Marketplace Request

**Before v0.17.0:**
```python
from mech_client.interact import interact

result = interact(
    prompt="What is 2+2?",
    tool="openai-gpt-4",
    agent_id=1,
    priority_mech_address="0x...",
    private_key_path="ethereum_private_key.txt",
    chain_config="gnosis",
    use_agent_mode=False,
    request_from_marketplace=True,
    # ... many more parameters
)
```

**After v0.17.0:**
```python
from mech_client.services.marketplace_service import MarketplaceService
from mech_client.infrastructure.config import get_mech_config
from mech_client.domain.payment import PaymentType
from aea_ledger_ethereum import EthereumApi, EthereumCrypto

# Setup
config = get_mech_config("gnosis")
crypto = EthereumCrypto("ethereum_private_key.txt")
ledger_api = EthereumApi(**config.ledger_config.__dict__)

# Create service
service = MarketplaceService(
    chain_config="gnosis",
    ledger_api=ledger_api,
    payer_address=crypto.address,
    mode="client",
)

# Send request
result = service.send_request(
    priority_mech="0x...",
    tools=["openai-gpt-4"],
    prompts=["What is 2+2?"],
    payment_type=PaymentType.NATIVE,
)

print(f"Transaction hash: {result['tx_hash']}")
print(f"Request IDs: {result['request_ids']}")
```

### Example 2: Depositing Tokens

**Before v0.17.0:**
```python
from mech_client.interact import deposit_token

tx_hash = deposit_token(
    amount=1000000000000000000,
    token_type="olas",
    private_key_path="ethereum_private_key.txt",
    chain_config="gnosis",
    use_agent_mode=False,
)
```

**After v0.17.0:**
```python
from mech_client.services.deposit_service import DepositService
from mech_client.infrastructure.config import get_mech_config
from mech_client.domain.payment import PaymentType
from aea_ledger_ethereum import EthereumApi, EthereumCrypto

# Setup
config = get_mech_config("gnosis")
crypto = EthereumCrypto("ethereum_private_key.txt")
ledger_api = EthereumApi(**config.ledger_config.__dict__)

# Create service
service = DepositService(
    chain_config="gnosis",
    ledger_api=ledger_api,
    depositor_address=crypto.address,
    mode="client",
)

# Deposit tokens
tx_hash = service.deposit_token(
    amount=1000000000000000000,
    payment_type=PaymentType.TOKEN,  # OLAS
)

print(f"Deposit transaction: {tx_hash}")
```

### Example 3: Listing Tools

**Before v0.17.0:**
```python
from mech_client.mech_tool import list_all_tools_for_marketplace_mech

tools = list_all_tools_for_marketplace_mech(
    service_id=1,
    chain_config="gnosis",
)

for tool in tools:
    print(f"{tool['name']}: {tool['id']}")
```

**After v0.17.0:**
```python
from mech_client.services.tool_service import ToolService
from mech_client.infrastructure.config import get_mech_config
from aea_ledger_ethereum import EthereumApi

# Setup
config = get_mech_config("gnosis")
ledger_api = EthereumApi(**config.ledger_config.__dict__)

# Create service
service = ToolService(
    chain_config="gnosis",
    ledger_api=ledger_api,
)

# List tools
tools = service.list_tools(service_id=1)

for tool_name, tool_id in tools:
    print(f"{tool_name}: {tool_id}")
```

## Testing Migration

### Before: No Tests

Most code had no tests before v0.17.0.

### After: Comprehensive Testing

Now you should write tests for your code:

```python
# tests/test_my_feature.py
from unittest.mock import MagicMock
import pytest

from mech_client.services.marketplace_service import MarketplaceService
from mech_client.domain.payment import PaymentType

def test_send_request_success(mock_ledger_api: MagicMock) -> None:
    """Test successful request sending."""
    # Arrange
    service = MarketplaceService(
        chain_config="gnosis",
        ledger_api=mock_ledger_api,
        payer_address="0x...",
        mode="client",
    )

    # Act
    result = service.send_request(
        priority_mech="0x...",
        tools=["tool1"],
        prompts=["prompt1"],
        payment_type=PaymentType.NATIVE,
    )

    # Assert
    assert "tx_hash" in result
    assert "request_ids" in result
```

See [TESTING.md](./TESTING.md) for comprehensive testing guidelines.

## Getting Help

If you encounter issues during migration:

1. **Check the documentation**:
   - [ARCHITECTURE.md](./ARCHITECTURE.md) - New architecture overview
   - [TESTING.md](./TESTING.md) - Testing guidelines
   - [README.md](./README.md) - Usage examples

2. **Review the code**:
   - Look at similar functionality in the new structure
   - Check the tests for usage examples
   - Review service layer for orchestration patterns

3. **Ask for help**:
   - Open an issue on GitHub
   - Include your migration attempt
   - Provide context about your use case

## Summary

The v0.17.0 refactoring brings significant improvements:
- ✅ **Better separation of concerns**
- ✅ **Easier testing**
- ✅ **More maintainable code**
- ✅ **Clearer interfaces**
- ✅ **Type safety**
- ✅ **Comprehensive documentation**

While migration requires some effort, the new architecture provides a solid foundation for future development and makes the codebase much easier to understand and extend.
