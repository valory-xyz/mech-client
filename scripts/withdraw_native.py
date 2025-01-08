import sys
from pathlib import Path
from aea_ledger_ethereum import EthereumApi, EthereumCrypto
from dataclasses import asdict
from web3.contract import Contract as Web3Contract


from mech_client.interact import get_mech_config, PRIVATE_KEY_FILE_PATH
from utils import (
    print_title,
    input_select_chain,
    input_with_default_value,
    get_native_balance_tracker_contract,
)
from mech_client.wss import wait_for_receipt


def withdraw(
    ledger_api: EthereumApi,
    crypto: EthereumCrypto,
    native_balance_tracker_contract: Web3Contract,
):
    sender = crypto.address

    try:
        print("Fetching user balance")
        user_balance = native_balance_tracker_contract.functions.mapRequesterBalances(
            sender
        ).call()

        if user_balance == 0:
            print(f"User balance for {sender} is 0. Nothing to withdraw")
            sys.exit(1)

        formatted_user_balance = user_balance / 1e18
        print(f"Balance for {sender} is {formatted_user_balance}")
    except Exception as e:
        print(f"Error occured while fetching user balance: {e}")

    try:
        print("Sending withdraw tx")

        tx_args = {"sender_address": sender, "value": 0, "gas": 50000}
        raw_transaction = ledger_api.build_transaction(
            contract_instance=native_balance_tracker_contract,
            method_name="withdraw",
            method_args={},
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


def main() -> None:
    """Runs the withdraw functionality for the native mech type"""
    print_title("Native Withdraw")
    print(
        "This script will assist you in withdrawing native balance for mech requests."
    )
    print()

    print("Select the chain to use")

    chain_config = input_select_chain()

    private_key_path = input_with_default_value(
        "Please provide path to your private key", PRIVATE_KEY_FILE_PATH
    )

    mech_config = get_mech_config(chain_config)
    ledger_config = mech_config.ledger_config
    ledger_api = EthereumApi(**asdict(ledger_config))

    if not Path(private_key_path).exists():
        raise FileNotFoundError(
            f"Private key file `{private_key_path}` does not exist!"
        )
    crypto = EthereumCrypto(private_key_path=private_key_path)

    chain_id = mech_config.ledger_config.chain_id
    native_balance_tracker_contract = get_native_balance_tracker_contract(
        ledger_api, chain_id
    )

    withdraw_tx = withdraw(ledger_api, crypto, native_balance_tracker_contract)
    if not withdraw_tx:
        print("Unable to withdraw")
        sys.exit(1)

    transaction_url_formatted = mech_config.transaction_url.format(
        transaction_digest=withdraw_tx
    )
    print(f" - Transaction sent: {transaction_url_formatted}")
    print(" - Waiting for transaction receipt...")
    wait_for_receipt(withdraw_tx, ledger_api)

    print("")
    print("Withdraw Successful")


if __name__ == "__main__":
    main()
