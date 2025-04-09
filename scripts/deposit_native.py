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


import sys
from pathlib import Path
from typing import Optional
from aea_ledger_ethereum import EthereumApi, EthereumCrypto
from dataclasses import asdict

from mech_client.interact import get_mech_config, PRIVATE_KEY_FILE_PATH
from .utils import (
    print_title,
    CHAIN_TO_NATIVE_BALANCE_TRACKER,
)
from mech_client.wss import wait_for_receipt


def deposit(
    ledger_api: EthereumApi,
    crypto: EthereumCrypto,
    to: str,
    amount: int,
) -> str:
    sender = crypto.address

    try:
        print("Fetching user balance")
        user_balance = ledger_api.get_balance(address=sender)
        if user_balance < amount:
            formatted_user_balance = user_balance / 1e18
            formatted_amount = amount / 1e18
            print("User balance low!!")
            print(f"Balance: {formatted_user_balance}")
            print(f"Want to Deposit: {formatted_amount}")
            sys.exit(1)
    except Exception as e:
        print(f"Error occured while fetching user balance: {e}")
        return str(e)

    try:
        print("Sending deposit tx")
        raw_transaction = ledger_api.get_transfer_transaction(
            sender_address=sender,
            destination_address=to,
            amount=amount,
            tx_fee=50000,
            tx_nonce="0x",
        )
        signed_transaction = crypto.sign_transaction(raw_transaction)
        transaction_digest = ledger_api.send_signed_transaction(
            signed_transaction,
            raise_on_try=True,
        )
        return transaction_digest
    except Exception as e:  # pylint: disable=broad-except
        print(f"Error occured while sending the transaction: {e}")
        return str(e)


def main(
    amount: str,
    private_key_path: Optional[str] = None,
    chain_config: Optional[str] = None,
) -> None:
    """Runs the deposit functionality for the native mech type"""
    print_title("Native Deposit")
    print("This script will assist you in depositing native balance for mech requests.")
    print()

    amount_to_deposit = int(float(amount) * 10**18)
    private_key_path = private_key_path or PRIVATE_KEY_FILE_PATH

    mech_config = get_mech_config(chain_config)
    ledger_config = mech_config.ledger_config
    ledger_api = EthereumApi(**asdict(ledger_config))

    if not Path(private_key_path).exists():
        raise FileNotFoundError(
            f"Private key file `{private_key_path}` does not exist!"
        )
    crypto = EthereumCrypto(private_key_path=private_key_path)

    print(f"Sender address: {crypto.address}")

    chain_id = mech_config.ledger_config.chain_id
    to = CHAIN_TO_NATIVE_BALANCE_TRACKER[chain_id]

    deposit_tx = deposit(ledger_api, crypto, to, amount_to_deposit)
    if not deposit_tx:
        print("Unable to deposit")
        sys.exit(1)

    transaction_url_formatted = mech_config.transaction_url.format(
        transaction_digest=deposit_tx
    )
    print(f" - Transaction sent: {transaction_url_formatted}")
    print(" - Waiting for transaction receipt...")
    wait_for_receipt(deposit_tx, ledger_api)

    print("")
    print("Deposit Successful")
