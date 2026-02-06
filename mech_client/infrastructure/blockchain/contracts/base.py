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

"""Base contract utilities and wrapper."""

from typing import List

from aea_ledger_ethereum import EthereumApi
from web3.contract import Contract as Web3Contract


def get_contract(
    contract_address: str,
    abi: List,
    ledger_api: EthereumApi,
) -> Web3Contract:
    """
    Create a Web3 contract instance.

    :param contract_address: The address of the contract
    :param abi: Contract ABI as list
    :param ledger_api: The Ethereum API used for interacting with the ledger
    :return: The contract instance
    """
    return ledger_api.get_contract_instance(
        {"abi": abi, "bytecode": "0x"}, contract_address
    )
