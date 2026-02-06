# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2025 Valory AG
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
# ------------------------------------------------------------------------------

"""Pytest configuration and shared fixtures."""

from typing import Dict
from unittest.mock import MagicMock, Mock

import pytest
from web3.constants import ADDRESS_ZERO


@pytest.fixture
def mock_ledger_api() -> MagicMock:
    """
    Mock Ethereum API for testing.

    :return: Mock ledger API with common methods
    """
    ledger_api = MagicMock()
    ledger_api.get_balance.return_value = 10**18  # 1 ETH
    ledger_api.build_transaction.return_value = {"data": "0x123"}
    ledger_api.send_signed_transaction.return_value = "0xabcd"
    return ledger_api


@pytest.fixture
def mock_ethereum_crypto() -> MagicMock:
    """
    Mock Ethereum crypto for testing.

    :return: Mock crypto with signing methods
    """
    crypto = MagicMock()
    crypto.address = "0x1234567890123456789012345678901234567890"
    crypto.sign_transaction.return_value = "0xsigned"
    return crypto


@pytest.fixture
def mock_safe_client() -> MagicMock:
    """
    Mock Safe client for testing.

    :return: Mock Safe client
    """
    safe_client = MagicMock()
    safe_client.send_transaction.return_value = b"\xab\xcd"
    safe_client.get_nonce.return_value = 0
    return safe_client


@pytest.fixture
def mock_ethereum_client() -> MagicMock:
    """
    Mock Ethereum client from safe-eth-py.

    :return: Mock Ethereum client
    """
    eth_client = MagicMock()
    return eth_client


@pytest.fixture
def mock_web3_contract() -> MagicMock:
    """
    Mock Web3 contract for testing.

    :return: Mock contract with common methods
    """
    contract = MagicMock()
    contract.address = "0x" + "1" * 40
    contract.functions.balanceOf.return_value.call.return_value = 10**18
    contract.functions.approve.return_value.build_transaction.return_value = {
        "data": "0xapprove"
    }
    return contract


@pytest.fixture
def valid_ethereum_address() -> str:
    """
    Valid Ethereum address for testing.

    :return: Valid Ethereum address
    """
    return "0x1234567890123456789012345678901234567890"


@pytest.fixture
def zero_address() -> str:
    """
    Zero address constant for testing.

    :return: Zero address
    """
    return ADDRESS_ZERO


@pytest.fixture
def sample_chain_config() -> Dict[str, str]:
    """
    Sample chain configuration for testing.

    :return: Dictionary with chain config
    """
    return {
        "name": "gnosis",
        "chain_id": 100,
        "rpc_url": "https://rpc.gnosischain.com",
    }


@pytest.fixture
def sample_tool_metadata() -> Dict:
    """
    Sample tool metadata for testing.

    :return: Tool metadata dictionary
    """
    return {
        "name": "openai-gpt-4",
        "description": "OpenAI GPT-4 model",
        "input": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "User prompt"}
            },
        },
        "output": {"type": "string", "description": "Model response"},
    }


@pytest.fixture
def sample_ipfs_hash() -> str:
    """
    Sample IPFS hash for testing.

    :return: Valid IPFS CIDv0 hash
    """
    return "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"


@pytest.fixture
def sample_tx_hash() -> str:
    """
    Sample transaction hash for testing.

    :return: Valid transaction hash
    """
    return "0x" + "a" * 64


@pytest.fixture
def sample_request_id() -> str:
    """
    Sample request ID for testing.

    :return: Request ID as string
    """
    return "12345"
