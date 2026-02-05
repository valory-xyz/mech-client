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

"""Deposit functionality for mech marketplace prepaid balances."""

import sys
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from aea_ledger_ethereum import EthereumApi, EthereumCrypto
from web3.contract import Contract as Web3Contract

from mech_client.contract_addresses import CHAIN_TO_NATIVE_BALANCE_TRACKER
from mech_client.interact import PRIVATE_KEY_FILE_PATH, get_mech_config
from mech_client.marketplace_interact import (
    get_token_balance_tracker_contract,
    get_token_contract,
)
from mech_client.safe import EthereumClient, get_safe_nonce, send_safe_tx
from mech_client.wss import wait_for_receipt


def print_title(text: str) -> None:
    """Print title with formatting."""
    margin = 4
    character = "="
    text_length = len(text)
    length = text_length + 2 * margin
    border = character * length
    margin_str = " " * margin

    print()
    print(border)
    print(f"{margin_str}{text}{margin_str}")
    print(border)
    print()


def deposit_native(  # pylint: disable=too-many-arguments
    ledger_api: EthereumApi,
    crypto: EthereumCrypto,
    ethereum_client: EthereumClient,
    agent_mode: bool,
    safe_address: Optional[str],
    to: str,
    amount: int,
) -> str:
    """
    Deposit native tokens to the balance tracker for prepaid requests.

    :param ledger_api: The Ethereum API used for interacting with the ledger.
    :type ledger_api: EthereumApi
    :param crypto: The Ethereum crypto object.
    :type crypto: EthereumCrypto
    :param ethereum_client: The Ethereum Client used for interacting with the safe.
    :type ethereum_client: EthereumClient
    :param agent_mode: Specifies whether agent mode is active or not.
    :type agent_mode: bool
    :param safe_address: Specifies the safe address related to the configured service, empty if client mode.
    :type safe_address: Optional[str]
    :param to: The balance tracker contract address to deposit to.
    :type to: str
    :param amount: Amount of native token to deposit (in wei).
    :type amount: int
    :return: The transaction digest.
    :rtype: str
    """
    sender = safe_address or crypto.address

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
    except Exception as e:  # pylint: disable=broad-except
        print(f"Error occured while fetching user balance: {e}")
        return str(e)

    try:
        print("Sending deposit tx")
        if not agent_mode:
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

        transaction_digest = send_safe_tx(
            ethereum_client=ethereum_client,
            tx_data="0x",
            to_adress=to,
            safe_address=str(safe_address),
            signer_pkey=crypto.private_key,
            value=amount,
        )
        return transaction_digest.to_0x_hex()

    except Exception as e:  # pylint: disable=broad-except
        print(f"Error occured while sending the transaction: {e}")
        return str(e)


def check_token_balance(token_contract: Web3Contract, sender: str, amount: int) -> None:
    """
    Check if the sender has sufficient token balance for deposit.

    :param token_contract: The token contract instance.
    :type token_contract: Web3Contract
    :param sender: The sender address.
    :type sender: str
    :param amount: The amount to check (in token's smallest unit).
    :type amount: int
    """
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
    except Exception as e:  # pylint: disable=broad-except
        print(f"Error occured while fetching user balance: {e}")


def approve_token(  # pylint: disable=too-many-arguments,too-many-locals
    crypto: EthereumCrypto,
    ledger_api: EthereumApi,
    ethereum_client: EthereumClient,
    agent_mode: bool,
    safe_address: Optional[str],
    token_contract: Web3Contract,
    token_balance_tracker_contract: Web3Contract,
    amount: int,
) -> str:
    """
    Approve tokens for deposit to the balance tracker.

    :param crypto: The Ethereum crypto object.
    :type crypto: EthereumCrypto
    :param ledger_api: The Ethereum API used for interacting with the ledger.
    :type ledger_api: EthereumApi
    :param ethereum_client: The Ethereum Client used for interacting with the safe.
    :type ethereum_client: EthereumClient
    :param agent_mode: Specifies whether agent mode is active or not.
    :type agent_mode: bool
    :param safe_address: Specifies the safe address related to the configured service, empty if client mode.
    :type safe_address: Optional[str]
    :param token_contract: The token contract instance.
    :type token_contract: Web3Contract
    :param token_balance_tracker_contract: The balance tracker contract instance.
    :type token_balance_tracker_contract: Web3Contract
    :param amount: Amount of tokens to approve (in token's smallest unit).
    :type amount: int
    :return: The transaction digest.
    :rtype: str
    """
    # Tokens will be on the safe and EOA pays for gas
    # so for agent mode, sender has to be safe
    sender = safe_address or crypto.address

    print("Sending approve tx")
    try:
        tx_args = {"sender_address": sender, "value": 0, "gas": 60000}
        method_name = "approve"
        method_args = {
            "_to": token_balance_tracker_contract.address,
            "_value": amount,
        }

        if not agent_mode:
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

        function = token_contract.functions[method_name](**method_args)
        transaction = function.build_transaction(
            {
                "chainId": int(
                    ledger_api._chain_id  # pylint: disable=protected-access
                ),
                "gas": 0,
                "nonce": get_safe_nonce(ethereum_client, str(safe_address)),
            }
        )
        transaction_digest = send_safe_tx(
            ethereum_client=ethereum_client,
            tx_data=transaction["data"],
            to_adress=token_contract.address,
            safe_address=str(safe_address),
            signer_pkey=crypto.private_key,
            value=0,
        )
        return transaction_digest.to_0x_hex()

    except Exception as e:  # pylint: disable=broad-except
        print(f"Error occured while sending the transaction: {e}")
        return str(e)


def deposit_token(  # pylint: disable=too-many-arguments,too-many-locals
    ledger_api: EthereumApi,
    crypto: EthereumCrypto,
    ethereum_client: EthereumClient,
    agent_mode: bool,
    safe_address: Optional[str],
    token_balance_tracker_contract: Web3Contract,
    amount: int,
) -> str:
    """
    Deposit tokens to the balance tracker for prepaid requests.

    :param ledger_api: The Ethereum API used for interacting with the ledger.
    :type ledger_api: EthereumApi
    :param crypto: The Ethereum crypto object.
    :type crypto: EthereumCrypto
    :param ethereum_client: The Ethereum Client used for interacting with the safe.
    :type ethereum_client: EthereumClient
    :param agent_mode: Specifies whether agent mode is active or not.
    :type agent_mode: bool
    :param safe_address: Specifies the safe address related to the configured service, empty if client mode.
    :type safe_address: Optional[str]
    :param token_balance_tracker_contract: The balance tracker contract instance.
    :type token_balance_tracker_contract: Web3Contract
    :param amount: Amount of tokens to deposit (in token's smallest unit).
    :type amount: int
    :return: The transaction digest.
    :rtype: str
    """
    # Tokens will be on the safe and EOA pays for gas
    # so for agent mode, sender has to be safe
    sender = safe_address or crypto.address

    print("Sending deposit tx")
    try:
        tx_args = {"sender_address": sender, "value": 0, "gas": 100000}
        method_name = "deposit"
        method_args = {"amount": amount}

        if not agent_mode:
            raw_transaction = ledger_api.build_transaction(
                contract_instance=token_balance_tracker_contract,
                method_name=method_name,
                method_args=method_args,
                tx_args=tx_args,
                raise_on_try=True,
            )
            signed_transaction = crypto.sign_transaction(raw_transaction)
            transaction_digest = ledger_api.send_signed_transaction(
                signed_transaction,
                raise_on_try=True,
            )
            return transaction_digest

        function = token_balance_tracker_contract.functions[method_name](**method_args)
        transaction = function.build_transaction(
            {
                "chainId": int(
                    ledger_api._chain_id  # pylint: disable=protected-access
                ),
                "gas": 0,
                "nonce": get_safe_nonce(ethereum_client, str(safe_address)),
            }
        )
        transaction_digest = send_safe_tx(
            ethereum_client=ethereum_client,
            tx_data=transaction["data"],
            to_adress=token_balance_tracker_contract.address,
            safe_address=str(safe_address),
            signer_pkey=crypto.private_key,
            value=0,
        )
        return transaction_digest.to_0x_hex()

    except Exception as e:  # pylint: disable=broad-except
        print(f"Error occured while sending the transaction: {e}")
        return str(e)


def deposit_native_main(  # pylint: disable=too-many-arguments,too-many-locals
    agent_mode: bool,
    amount: str,
    safe_address: Optional[str] = None,
    private_key_path: Optional[str] = None,
    private_key_password: Optional[str] = None,
    chain_config: Optional[str] = None,
) -> None:
    """
    Main function for depositing native tokens.

    :param agent_mode: Specifies whether agent mode is active or not.
    :type agent_mode: bool
    :param amount: Amount to deposit (as string, will be converted to wei).
    :type amount: str
    :param safe_address: Safe address for agent mode.
    :type safe_address: Optional[str]
    :param private_key_path: Path to the private key file.
    :type private_key_path: Optional[str]
    :param private_key_password: Password for encrypted private key.
    :type private_key_password: Optional[str]
    :param chain_config: Chain configuration identifier.
    :type chain_config: Optional[str]
    """
    print_title("Native Deposit")
    print("This script will assist you in depositing native balance for mech requests.")
    print()

    amount_to_deposit = int(float(amount) * 10**18)
    private_key_path = private_key_path or PRIVATE_KEY_FILE_PATH

    mech_config = get_mech_config(chain_config)
    ledger_rpc = mech_config.ledger_config.address
    ethereum_client = EthereumClient(ledger_rpc)
    ledger_config = mech_config.ledger_config
    ledger_api = EthereumApi(**asdict(ledger_config))

    if not Path(private_key_path).exists():
        raise FileNotFoundError(
            f"Private key file `{private_key_path}` does not exist!"
        )
    crypto = EthereumCrypto(
        private_key_path=private_key_path, password=private_key_password
    )

    sender = safe_address or crypto.address
    print(f"Sender address: {sender}")

    chain_id = mech_config.ledger_config.chain_id
    to = CHAIN_TO_NATIVE_BALANCE_TRACKER[chain_id]

    deposit_tx = deposit_native(
        ledger_api,
        crypto,
        ethereum_client,
        agent_mode,
        safe_address,
        to,
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


def deposit_token_main(  # pylint: disable=too-many-arguments,too-many-locals,too-many-statements
    agent_mode: bool,
    amount: str,
    safe_address: Optional[str] = None,
    private_key_path: Optional[str] = None,
    private_key_password: Optional[str] = None,
    chain_config: Optional[str] = None,
) -> None:
    """
    Main function for depositing tokens.

    :param agent_mode: Specifies whether agent mode is active or not.
    :type agent_mode: bool
    :param amount: Amount to deposit (as string, will be converted to token's smallest unit).
    :type amount: str
    :param safe_address: Safe address for agent mode.
    :type safe_address: Optional[str]
    :param private_key_path: Path to the private key file.
    :type private_key_path: Optional[str]
    :param private_key_password: Password for encrypted private key.
    :type private_key_password: Optional[str]
    :param chain_config: Chain configuration identifier.
    :type chain_config: Optional[str]
    """
    print_title("Token Deposit")
    print("This script will assist you in depositing token balance for mech requests.")
    print()

    amount_to_deposit = int(float(amount) * 10**18)
    private_key_path = private_key_path or PRIVATE_KEY_FILE_PATH

    mech_config = get_mech_config(chain_config)
    ledger_rpc = mech_config.ledger_config.address
    ethereum_client = EthereumClient(ledger_rpc)
    ledger_config = mech_config.ledger_config
    ledger_api = EthereumApi(**asdict(ledger_config))

    if not Path(private_key_path).exists():
        raise FileNotFoundError(
            f"Private key file `{private_key_path}` does not exist!"
        )
    crypto = EthereumCrypto(
        private_key_path=private_key_path, password=private_key_password
    )

    chain_id = mech_config.ledger_config.chain_id
    token_balance_tracker_contract = get_token_balance_tracker_contract(
        ledger_api, chain_id
    )
    token_contract = get_token_contract(ledger_api, chain_id)

    # Tokens will be on the safe and EOA pays for gas
    # so for agent mode, sender has to be safe
    sender = safe_address or crypto.address
    print(f"Sender address: {sender}")

    check_token_balance(token_contract, sender, amount_to_deposit)

    approve_tx = approve_token(
        crypto,
        ledger_api,
        ethereum_client,
        agent_mode,
        safe_address,
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

    deposit_tx = deposit_token(
        ledger_api,
        crypto,
        ethereum_client,
        agent_mode,
        safe_address,
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
