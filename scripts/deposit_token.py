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
from web3.contract import Contract as Web3Contract


from mech_client.interact import (
    get_mech_config,
    PRIVATE_KEY_FILE_PATH,
)
from .utils import (
    print_title,
    get_token_contract,
    get_token_balance_tracker_contract,
)
from mech_client.wss import wait_for_receipt


def check_token_balance(token_contract: Web3Contract, sender: str, amount: int) -> None:
    try:
        print("Fetching user balance")
        user_token_balance = token_contract.functions.balanceOf(sender).call()
        if user_token_balance < amount:
            formatted_user_balance = user_token_balance / 1e18
            formatted_amount = amount / 1e18
            print("User balance low!!")
            print(f"Balance: {formatted_user_balance}")
            print(f"Want to Deposit: {formatted_amount}")
            sys.exit(1)
    except Exception as e:
        print(f"Error occured while fetching user balance: {e}")


def approve(
    crypto: EthereumCrypto,
    ledger_api: EthereumApi,
    token_contract: Web3Contract,
    token_balance_tracker_contract: Web3Contract,
    amount: int,
) -> str:
    sender = crypto.address

    print("Sending approve tx")
    try:
        tx_args = {"sender_address": sender, "value": 0, "gas": 60000}
        raw_transaction = ledger_api.build_transaction(
            contract_instance=token_contract,
            method_name="approve",
            method_args={
                "_to": token_balance_tracker_contract.address,
                "_value": amount,
            },
            tx_args=tx_args,
            raise_on_try=True,
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


def deposit(
    ledger_api: EthereumApi,
    crypto: EthereumCrypto,
    token_balance_tracker_contract: Web3Contract,
    amount: int,
) -> str:
    sender = crypto.address

    print("Sending deposit tx")
    try:
        tx_args = {"sender_address": sender, "value": 0, "gas": 100000}
        raw_transaction = ledger_api.build_transaction(
            contract_instance=token_balance_tracker_contract,
            method_name="deposit",
            method_args={"amount": amount},
            tx_args=tx_args,
            raise_on_try=True,
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
    """Runs the deposit functionality for the token mech type"""
    print_title("Token Deposit")
    print("This script will assist you in depositing token balance for mech requests.")
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
    token_balance_tracker_contract = get_token_balance_tracker_contract(
        ledger_api, chain_id
    )
    token_contract = get_token_contract(ledger_api, chain_id)

    check_token_balance(token_contract, crypto.address, amount_to_deposit)

    approve_tx = approve(
        crypto,
        ledger_api,
        token_contract,
        token_balance_tracker_contract,
        amount_to_deposit,
    )
    if not approve_tx:
        print("Unable to approve")
        sys.exit(1)

    transaction_url_formatted = mech_config.transaction_url.format(
        transaction_digest=approve_tx
    )
    print(f" - Transaction sent: {transaction_url_formatted}")
    print(" - Waiting for transaction receipt...")
    wait_for_receipt(approve_tx, ledger_api)

    deposit_tx = deposit(
        ledger_api,
        crypto,
        token_balance_tracker_contract,
        amount_to_deposit,
    )
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
