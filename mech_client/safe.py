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

"""Mech client Safe Module."""
from typing import Optional

from hexbytes import HexBytes
from safe_eth.eth import EthereumClient  # pylint:disable=import-error
from safe_eth.safe import Safe  # pylint:disable=import-error
from web3.constants import ADDRESS_ZERO


def send_safe_tx(  # pylint: disable=too-many-arguments
    ethereum_client: EthereumClient,
    tx_data: str,
    to_adress: str,
    safe_address: str,
    signer_pkey: str,
    value: int = 0,
) -> Optional[HexBytes]:
    """Send a Safe transaction"""
    # Get the safe
    safe = Safe(  # pylint:disable=abstract-class-instantiated
        safe_address, ethereum_client
    )

    estimated_gas = safe.estimate_tx_gas_with_safe(
        to=to_adress, value=value, data=bytes.fromhex(tx_data[2:]), operation=0
    )

    # Build, sign and send the safe transaction
    safe_tx = safe.build_multisig_tx(
        to=to_adress,
        value=value,
        data=bytes.fromhex(tx_data[2:]),
        operation=0,
        safe_tx_gas=estimated_gas,
        base_gas=0,
        gas_price=0,
        gas_token=ADDRESS_ZERO,
        refund_receiver=ADDRESS_ZERO,
    )
    safe_tx.sign(signer_pkey)
    try:
        tx_hash, _ = safe_tx.execute(signer_pkey)
        return tx_hash
    except Exception as e:  # pylint: disable=broad-except
        print(f"Exception while sending a safe transaction: {e}")
        return None


def get_safe_nonce(ethereum_client: EthereumClient, safe_address: str) -> int:
    """Get the Safe nonce"""
    safe = Safe(  # pylint:disable=abstract-class-instantiated
        safe_address, ethereum_client
    )
    return safe.retrieve_nonce()
