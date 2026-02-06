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

"""ABI loading utilities for smart contracts."""

import json
from pathlib import Path
from typing import List

from mech_client.infrastructure.config.constants import ABI_DIR_PATH


def get_abi(contract_name: str) -> List:
    """Load contract ABI from JSON file.

    :param contract_name: Contract ABI filename (e.g., "MechMarketplace.json")
    :return: Contract ABI as list of ABI elements
    :raises FileNotFoundError: If ABI file doesn't exist
    :raises json.JSONDecodeError: If ABI file is malformed
    """
    abi_path = ABI_DIR_PATH / contract_name
    with open(abi_path, encoding="utf-8") as f:
        abi = json.load(f)

    return abi if abi else []


def get_abi_path(contract_name: str) -> Path:
    """Get full path to contract ABI file.

    :param contract_name: Contract ABI filename (e.g., "MechMarketplace.json")
    :return: Path to ABI file
    """
    return ABI_DIR_PATH / contract_name
