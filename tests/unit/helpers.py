# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2026 Valory AG
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

"""Shared unit-test helpers."""

from unittest.mock import MagicMock

DEFAULT_SIGNER_ADDRESS = "0x" + "1" * 40
DEFAULT_TX_HASH = "0x" + "ff" * 32
DEFAULT_SIGNATURE = b"\xab" * 65


def create_mock_signer(
    address: str = DEFAULT_SIGNER_ADDRESS,
    tx_hash: str = DEFAULT_TX_HASH,
    signature: bytes = DEFAULT_SIGNATURE,
) -> MagicMock:
    """
    Create a mock Signer.

    :param address: EOA address the signer reports
    :param tx_hash: Transaction hash send_transaction returns
    :param signature: Signature bytes sign_message returns
    :return: Mock signer instance
    """
    mock_signer = MagicMock()
    mock_signer.address = address
    mock_signer.send_transaction.return_value = tx_hash
    mock_signer.sign_message.return_value = signature
    return mock_signer
