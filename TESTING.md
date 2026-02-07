# Testing Guide

This document provides comprehensive guidance on testing the mech-client codebase.

## Table of Contents

- [Overview](#overview)
- [Test Structure](#test-structure)
- [Running Tests](#running-tests)
- [Writing Tests](#writing-tests)
- [Testing Patterns](#testing-patterns)
- [Test Fixtures](#test-fixtures)
- [Mocking Guidelines](#mocking-guidelines)
- [Coverage Goals](#coverage-goals)

## Overview

The mech-client uses pytest for testing with a comprehensive suite of unit tests covering all architectural layers. The testing strategy emphasizes:

- **Layer isolation**: Test each layer independently
- **Mock external dependencies**: Use mocks for I/O and external systems
- **Interface testing**: Verify contracts between layers
- **Error handling**: Test both success and failure paths
- **Async support**: Test async components with anyio

### Test Statistics

- **Total tests**: 277 (excluding unsupported trio backend)
- **Test files**: 22
- **Test classes**: 68+
- **Coverage**: ~50% (target: 70%)

### Test Breakdown by Layer

| Layer | Tests | Files | Coverage Focus |
|-------|-------|-------|----------------|
| Utils | 75 | 2 | Validators, error handling |
| Domain | 80 | 7 | Strategies, watchers, factories, tools, subscriptions |
| Services | 41 | 5 | Orchestration, workflows, deposits, setup, subscriptions |
| Infrastructure | 81 | 10 | Adapters, clients, loaders, Safe, NVM contracts |

## Test Structure

```
tests/
├── conftest.py                              # Shared fixtures for all tests
├── pytest.ini                               # Pytest configuration
├── unit/                                    # Unit tests
│   ├── __init__.py
│   ├── utils/                               # Utils layer tests (75 tests)
│   │   ├── __init__.py
│   │   ├── test_validators.py              # 45 tests
│   │   └── test_errors.py                  # 30 tests
│   ├── domain/                              # Domain layer tests (80 tests)
│   │   ├── __init__.py
│   │   ├── test_payment_strategies.py      # 15 tests
│   │   ├── test_execution_strategies.py    # 4 tests
│   │   ├── test_delivery_watchers.py       # 11 tests (asyncio)
│   │   ├── test_offchain_watcher.py        # 14 tests (asyncio)
│   │   ├── test_tool_manager.py            # 22 tests
│   │   ├── test_subscription_builders.py   # 8 tests (NVM subscription)
│   │   └── test_subscription_manager.py    # 6 tests (NVM subscription)
│   ├── services/                            # Service layer tests (41 tests)
│   │   ├── __init__.py
│   │   ├── test_tool_service.py            # 10 tests
│   │   ├── test_marketplace_service.py     # 9 tests
│   │   ├── test_deposit_service.py         # 10 tests
│   │   ├── test_setup_service.py           # 7 tests
│   │   └── test_subscription_service.py    # 5 tests (NVM subscription)
│   └── infrastructure/                      # Infrastructure layer tests (81 tests)
│       ├── __init__.py
│       ├── test_config_loader.py           # 7 tests
│       ├── test_ipfs_client.py             # 8 tests
│       ├── test_abi_loader.py              # 7 tests
│       ├── test_contracts.py               # 3 tests
│       ├── test_receipt_waiter.py          # 8 tests
│       ├── test_subgraph_client.py         # 9 tests
│       ├── test_subgraph_queries.py        # 15 tests
│       ├── test_safe_client.py             # 16 tests
│       ├── test_nvm_config.py              # 9 tests (NVM subscription)
│       └── test_nvm_contracts.py           # 3 tests (NVM subscription)
└── integration/                             # Integration tests (future)
    └── test_cli_commands.py                 # End-to-end CLI tests
```

## Running Tests

### Basic Usage

```bash
# Run all unit tests (excludes trio backend)
poetry run pytest tests/unit/ -k "not trio"

# Run specific test file
poetry run pytest tests/unit/domain/test_payment_strategies.py

# Run specific test class
poetry run pytest tests/unit/domain/test_payment_strategies.py::TestNativePaymentStrategy

# Run specific test method
poetry run pytest tests/unit/domain/test_payment_strategies.py::TestNativePaymentStrategy::test_check_balance_sufficient

# Run with verbose output
poetry run pytest tests/unit/ -v

# Run with output capture disabled (see print statements)
poetry run pytest tests/unit/ -s

# Run and stop on first failure
poetry run pytest tests/unit/ -x
```

### Coverage Reports

```bash
# Run with coverage
poetry run pytest tests/unit/ --cov=mech_client

# Generate HTML coverage report
poetry run pytest tests/unit/ --cov=mech_client --cov-report=html

# View coverage report
open htmlcov/index.html

# Show missing lines
poetry run pytest tests/unit/ --cov=mech_client --cov-report=term-missing
```

### Running Specific Layers

```bash
# Run utils tests only
poetry run pytest tests/unit/utils/

# Run domain tests only
poetry run pytest tests/unit/domain/

# Run service tests only
poetry run pytest tests/unit/services/

# Run infrastructure tests only
poetry run pytest tests/unit/infrastructure/
```

### Async Tests

```bash
# Run async tests (asyncio backend only)
poetry run pytest tests/unit/domain/test_delivery_watchers.py -k asyncio

# Run all tests excluding trio backend (trio not installed)
poetry run pytest tests/unit/ -k "not trio"
```

### Parallel Execution

```bash
# Run tests in parallel (requires pytest-xdist)
poetry run pytest tests/unit/ -n auto
```

## Writing Tests

### Test File Structure

Each test file should follow this structure:

```python
# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2025 Valory AG
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   ...
#
# ------------------------------------------------------------------------------

"""Tests for <module_name>."""

from unittest.mock import MagicMock, patch

import pytest

from mech_client.<layer>.<module> import <ComponentToTest>


class TestComponentName:
    """Tests for ComponentName class."""

    def test_feature_success_case(self) -> None:
        """Test feature with valid inputs."""
        # Arrange
        component = ComponentName(dependencies)

        # Act
        result = component.method(args)

        # Assert
        assert result == expected_value

    def test_feature_error_case(self) -> None:
        """Test feature with invalid inputs."""
        with pytest.raises(ExpectedException, match="error message"):
            component.method(invalid_args)
```

### Naming Conventions

**Test Files**: `test_<module_name>.py`
- `test_validators.py`
- `test_payment_strategies.py`
- `test_ipfs_client.py`

**Test Classes**: `Test<ComponentName>`
- `TestNativePaymentStrategy`
- `TestIPFSClient`
- `TestMarketplaceService`

**Test Methods**: `test_<feature>_<scenario>`
- `test_check_balance_sufficient()`
- `test_upload_file_success()`
- `test_invalid_address_raises_error()`

### Test Documentation

Each test should have a clear docstring:

```python
def test_native_payment_check_balance_sufficient(self) -> None:
    """Test that check_balance returns True when balance is sufficient."""
    # Test implementation
```

## Testing Patterns

### 1. Arrange-Act-Assert (AAA)

Structure tests using the AAA pattern:

```python
def test_validate_ethereum_address_valid(self) -> None:
    """Test validation of valid Ethereum address."""
    # Arrange
    valid_address = "0x1234567890123456789012345678901234567890"

    # Act
    result = validate_ethereum_address(valid_address)

    # Assert
    assert result == valid_address
```

### 2. One Assertion Per Test (Guideline)

Prefer focused tests with clear purpose:

```python
# Good: Focused test
def test_check_balance_returns_true_when_sufficient(self) -> None:
    """Test check_balance returns True for sufficient balance."""
    strategy = NativePaymentStrategy(mock_ledger_api)
    mock_ledger_api.get_balance.return_value = 10**18

    result = strategy.check_balance(address, 5 * 10**17)

    assert result is True

# Good: Separate test for failure case
def test_check_balance_returns_false_when_insufficient(self) -> None:
    """Test check_balance returns False for insufficient balance."""
    strategy = NativePaymentStrategy(mock_ledger_api)
    mock_ledger_api.get_balance.return_value = 10**17

    result = strategy.check_balance(address, 5 * 10**17)

    assert result is False
```

### 3. Test Exceptions

Use `pytest.raises` for exception testing:

```python
def test_invalid_address_raises_validation_error(self) -> None:
    """Test that invalid address raises ValidationError."""
    with pytest.raises(ValidationError, match="Invalid Ethereum address"):
        validate_ethereum_address("not_an_address")
```

### 4. Parametrized Tests

Use `pytest.mark.parametrize` for testing multiple inputs:

```python
@pytest.mark.parametrize(
    "amount,expected",
    [
        (0, False),
        (-1, False),
        (1, True),
        (10**18, True),
    ],
)
def test_validate_amount(amount: int, expected: bool) -> None:
    """Test amount validation with various inputs."""
    if expected:
        validate_amount(amount)
    else:
        with pytest.raises(ValidationError):
            validate_amount(amount)
```

### 5. Fixture Usage

Use fixtures for common test setup:

```python
@pytest.fixture
def mock_ledger_api() -> MagicMock:
    """Create mock ledger API."""
    ledger_api = MagicMock()
    ledger_api.get_balance.return_value = 10**18
    return ledger_api

def test_with_fixture(mock_ledger_api: MagicMock) -> None:
    """Test using fixture."""
    strategy = NativePaymentStrategy(mock_ledger_api)
    assert strategy.check_balance(address, amount)
```

### 6. Async Testing

Use `@pytest.mark.anyio` for async tests:

```python
@pytest.mark.anyio
async def test_delivery_watcher_success(
    mock_contract: MagicMock,
    mock_ledger_api: MagicMock,
) -> None:
    """Test successful delivery watching."""
    watcher = OnchainDeliveryWatcher(mock_contract, mock_ledger_api)

    result = await watcher.watch([request_id])

    assert request_id in result
```

### 7. Testing Factories

Test that factories create correct strategy types:

```python
def test_factory_creates_native_strategy() -> None:
    """Test factory creates NativePaymentStrategy for NATIVE type."""
    strategy = PaymentStrategyFactory.create(
        PaymentType.NATIVE, mock_ledger_api
    )

    assert isinstance(strategy, NativePaymentStrategy)
    assert isinstance(strategy, PaymentStrategy)  # Interface check
```

### 8. Testing Error Messages

Verify error messages contain helpful information:

```python
def test_error_message_contains_context() -> None:
    """Test that error message includes context."""
    with pytest.raises(RpcError) as exc_info:
        raise RpcError(
            "Connection failed",
            rpc_url="https://rpc.example.com"
        )

    error_msg = str(exc_info.value)
    assert "Connection failed" in error_msg
    assert "https://rpc.example.com" in error_msg
```

### 9. Testing Chain-Specific Logic (NVM Subscriptions)

Test chain-specific behavior separately:

```python
def test_gnosis_native_payment() -> None:
    """Test Gnosis uses native xDAI payment."""
    config = NVMConfig(
        token_address="0x0000000000000000000000000000000000000000",  # nosec
        # ... other config
    )

    assert config.requires_token_approval() is False
    assert config.get_transaction_value() > 0  # Native value

def test_base_token_payment() -> None:
    """Test Base uses USDC token payment."""
    config = NVMConfig(
        token_address="0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",  # USDC
        # ... other config
    )

    assert config.requires_token_approval() is True
    assert config.get_transaction_value() == 0  # No native value
```

### 10. Testing Infrastructure Without Real Dependencies

Mock base class methods to test infrastructure without loading ABIs:

```python
@patch("mech_client.infrastructure.nvm.contracts.base.NVMContractWrapper._load_contract")
def test_contract_factory(mock_load_contract: MagicMock) -> None:
    """Test contract factory without loading real ABIs."""
    from mech_client.infrastructure.nvm.contracts.factory import NVMContractFactory

    # Mock contract loading
    mock_contract = MagicMock()
    mock_load_contract.return_value = mock_contract

    # Factory creates real wrapper instances but uses mocked contract
    result = NVMContractFactory.create(mock_w3, "lock_payment")

    assert isinstance(result, LockPaymentContract)
    mock_load_contract.assert_called_once()
```

## Test Fixtures

### Shared Fixtures (`tests/conftest.py`)

The following fixtures are available globally:

```python
@pytest.fixture
def mock_ledger_api() -> MagicMock:
    """Mock Ethereum ledger API."""
    ledger_api = MagicMock()
    ledger_api.get_balance.return_value = 10**18
    ledger_api.api.eth.get_transaction_receipt.return_value = {
        "status": 1,
        "transactionHash": "0x123...",
    }
    return ledger_api

@pytest.fixture
def mock_ethereum_crypto() -> MagicMock:
    """Mock Ethereum crypto for signing."""
    crypto = MagicMock()
    crypto.address = "0x1234567890123456789012345678901234567890"
    return crypto

@pytest.fixture
def mock_safe_client() -> MagicMock:
    """Mock Safe client."""
    return MagicMock()

@pytest.fixture
def mock_web3_contract() -> MagicMock:
    """Mock Web3 contract instance."""
    return MagicMock()

@pytest.fixture
def valid_ethereum_address() -> str:
    """Valid Ethereum address for testing."""
    return "0x1234567890123456789012345678901234567890"

@pytest.fixture
def zero_address() -> str:
    """Zero address constant."""
    return "0x0000000000000000000000000000000000000000"

@pytest.fixture
def sample_ipfs_hash() -> str:
    """Sample IPFS CIDv0 hash."""
    return "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"

@pytest.fixture
def sample_tx_hash() -> str:
    """Sample transaction hash."""
    return "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
```

### Creating Custom Fixtures

For layer-specific fixtures, create them in the layer's `conftest.py`:

```python
# tests/unit/domain/conftest.py
import pytest
from unittest.mock import MagicMock

@pytest.fixture
def mock_payment_strategy() -> MagicMock:
    """Mock payment strategy."""
    strategy = MagicMock()
    strategy.check_balance.return_value = True
    strategy.approve_if_needed.return_value = None
    return strategy
```

## Mocking Guidelines

### 1. Mock External Dependencies

Always mock external systems (blockchain, IPFS, network):

```python
@patch("mech_client.infrastructure.ipfs.client.IPFSTool")
def test_ipfs_upload(mock_ipfs_tool: MagicMock) -> None:
    """Test IPFS upload."""
    mock_tool_instance = MagicMock()
    mock_ipfs_tool.return_value = mock_tool_instance
    mock_tool_instance.client.add.return_value = {"Hash": "QmTest..."}

    client = IPFSClient()
    v1_hash, v1_hex = client.upload("/path/to/file")

    assert isinstance(v1_hash, str)
    assert v1_hex.startswith("f01")
```

### 2. Mock at Module Level

Patch at the module where the dependency is used, not where it's defined:

```python
# Good: Patch where it's used
@patch("mech_client.domain.payment.token.get_contract")
def test_token_strategy(mock_get_contract: MagicMock) -> None:
    pass

# Bad: Patch where it's defined
@patch("mech_client.infrastructure.blockchain.contracts.get_contract")
def test_token_strategy(mock_get_contract: MagicMock) -> None:
    pass
```

### 3. Use MagicMock for Complex Objects

```python
def test_with_complex_mock() -> None:
    """Test with nested mock structure."""
    mock_ledger_api = MagicMock()
    mock_ledger_api.api.eth.get_balance.return_value = 10**18
    mock_ledger_api.api.eth.get_transaction_count.return_value = 5

    # Use the mock
    strategy = NativePaymentStrategy(mock_ledger_api)
    result = strategy.check_balance(address, amount)
```

### 4. Mock Return Values

Use `return_value` for single calls, `side_effect` for multiple:

```python
# Single return value
mock_obj.method.return_value = "result"

# Multiple return values (called multiple times)
mock_obj.method.side_effect = ["result1", "result2", "result3"]

# Raise exception
mock_obj.method.side_effect = ValueError("Error message")

# Different results based on call count
mock_obj.method.side_effect = [
    "first_call_result",
    ValueError("second_call_fails"),
    "third_call_result",
]
```

### 5. Verify Mock Calls

```python
def test_verify_mock_calls() -> None:
    """Test that mock was called correctly."""
    mock_ipfs = MagicMock()

    client = IPFSClient()
    client.ipfs_tool = mock_ipfs
    client.upload("/path/to/file")

    # Verify called once
    mock_ipfs.client.add.assert_called_once()

    # Verify called with specific arguments
    mock_ipfs.client.add.assert_called_once_with(
        "/path/to/file",
        pin=True,
        recursive=True,
        wrap_with_directory=False,
    )

    # Verify call count
    assert mock_ipfs.client.add.call_count == 1
```

### 6. Mock Files

Use `mock_open` for file operations:

```python
@patch("builtins.open", new_callable=mock_open, read_data='{"key": "value"}')
def test_load_json_file(mock_file: mock_open) -> None:
    """Test loading JSON from file."""
    data = load_json("config.json")

    assert data == {"key": "value"}
    mock_file.assert_called_once_with("config.json", "r")
```

### 7. Mock Environment Variables

Use `@patch.dict` for environment variables:

```python
@patch.dict("os.environ", {"MECHX_CHAIN_RPC": "https://custom.rpc.com"})
def test_env_var_override() -> None:
    """Test environment variable override."""
    config = MechConfig(...)
    assert config.rpc_url == "https://custom.rpc.com"
```

### 8. Avoid Over-Mocking

Don't mock what you're testing:

```python
# Bad: Mocking the component under test
def test_payment_strategy_bad() -> None:
    mock_strategy = MagicMock()
    mock_strategy.check_balance.return_value = True
    assert mock_strategy.check_balance(address, amount) is True  # Meaningless

# Good: Test real component with mocked dependencies
def test_payment_strategy_good(mock_ledger_api: MagicMock) -> None:
    mock_ledger_api.get_balance.return_value = 10**18
    strategy = NativePaymentStrategy(mock_ledger_api)
    assert strategy.check_balance(address, 5 * 10**17) is True  # Real logic
```

## Coverage Goals

### Current Coverage

- **Overall**: ~40%
- **Utils**: ~90% (high priority, well-tested)
- **Domain**: ~70% (strategies and watchers covered)
- **Services**: ~40% (core flows covered)
- **Infrastructure**: ~50% (adapters covered)

### Target Coverage

- **Overall**: 70%
- **Critical paths**: 90%+ (payment, execution, validation)
- **Infrastructure adapters**: 60%+ (focus on error handling)
- **CLI**: 50%+ (focus on command routing)

### Measuring Coverage

```bash
# Generate coverage report
poetry run pytest tests/unit/ --cov=mech_client --cov-report=html

# View report
open htmlcov/index.html

# Show coverage by file
poetry run pytest tests/unit/ --cov=mech_client --cov-report=term

# Show missing lines
poetry run pytest tests/unit/ --cov=mech_client --cov-report=term-missing

# Fail if coverage below threshold
poetry run pytest tests/unit/ --cov=mech_client --cov-fail-under=40
```

### Coverage Exclusions

Some code is intentionally excluded from coverage:

```python
# Exclude from coverage (use sparingly)
if TYPE_CHECKING:  # pragma: no cover
    from typing import Protocol

def debug_only_function():  # pragma: no cover
    """Only used for debugging."""
    pass
```

## Running Linters

Tests must pass linting before merging:

```bash
# Run all linters
tox -e black-check,isort-check,flake8,mypy,pylint,bandit,darglint,vulture && tox -e liccheck

# Fix formatting issues
tox -e black
tox -e isort

# Type check
tox -e mypy

# Security check
tox -e bandit

# Check for unused code
tox -e vulture
```

## Continuous Integration

Tests run automatically on:
- Every pull request
- Every commit to main
- Nightly builds

CI Requirements:
- ✅ All tests pass
- ✅ All linters pass (pylint must be 10.00/10)
- ✅ Coverage doesn't decrease

## Troubleshooting

### Common Issues

**Issue**: Tests fail with `ModuleNotFoundError`
```bash
# Solution: Install dependencies
poetry install
```

**Issue**: Async tests skipped with "trio not installed"
```bash
# Solution: Run with filter to exclude trio backend
poetry run pytest tests/unit/ -k "not trio"
```

**Issue**: Mock not being called
```python
# Solution: Ensure mock is properly patched at usage location
@patch("mech_client.domain.payment.token.get_contract")  # Where it's used
def test_token_strategy(mock_get_contract: MagicMock) -> None:
    pass
```

**Issue**: Timeout in async tests
```python
# Solution: Use shorter timeouts in tests
watcher = OnchainDeliveryWatcher(
    contract, ledger_api,
    timeout=0.5  # Short timeout for tests
)
```

**Issue**: Linter failures after adding tests
```bash
# Solution: Run formatters
tox -e black
tox -e isort

# Then check again
tox -e black-check,isort-check,flake8,mypy
```

## Best Practices Summary

1. **Write tests first** (TDD) when adding new features
2. **Test one thing** per test method
3. **Use descriptive names** for tests
4. **Mock external dependencies** but not the code under test
5. **Test both success and failure** paths
6. **Use fixtures** for common setup
7. **Keep tests fast** by mocking I/O
8. **Document complex tests** with clear docstrings
9. **Run tests frequently** during development
10. **Maintain test quality** like production code

## Contributing

When contributing tests:
1. Follow existing patterns in the layer you're testing
2. Add tests for new features
3. Update tests when modifying existing code
4. Ensure all linters pass
5. Maintain or improve coverage
6. Document complex test scenarios

## Further Reading

- [CLAUDE.md](./CLAUDE.md) - Development guidelines and patterns
- [ARCHITECTURE.md](./ARCHITECTURE.md) - System architecture overview
- [docs/COMMANDS.md](./docs/COMMANDS.md) - Command reference with dependency diagrams
- [pytest documentation](https://docs.pytest.org/)
- [unittest.mock documentation](https://docs.python.org/3/library/unittest.mock.html)
