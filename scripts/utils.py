import json
from pathlib import Path
from aea_ledger_ethereum import EthereumApi
from web3.contract import Contract as Web3Contract
from mech_client.marketplace_interact import (
    get_contract,
    CHAIN_TO_PRICE_TOKEN_OLAS,
    CHAIN_TO_PRICE_TOKEN_USDC,
    PaymentType,
)


# based on mech configs
VALID_CHAINS = [
    "gnosis",
    "arbitrum",
    "polygon",
    "base",
    "celo",
    "optimism",
]

CHAIN_TO_NATIVE_BALANCE_TRACKER = {
    100: "0x21cE6799A22A3Da84B7c44a814a9c79ab1d2A50D",
    42161: "",
    137: "0xc096362fa6f4A4B1a9ea68b1043416f3381ce300",
    8453: "0xB3921F8D8215603f0Bd521341Ac45eA8f2d274c1",
    42220: "",
    10: "0x4Cd816ce806FF1003ee459158A093F02AbF042a8",
}

CHAIN_TO_TOKEN_BALANCE_TRACKER_OLAS = {
    100: "0x53Bd432516707a5212A70216284a99A563aAC1D1",
    42161: "",
    137: "0x1521918961bDBC9Ed4C67a7103D5999e4130E6CB",
    8453: "0x43fB32f25dce34EB76c78C7A42C8F40F84BCD237",
    42220: "",
    10: "0x70A0D93fb0dB6EAab871AB0A3BE279DcA37a2bcf",
}

CHAIN_TO_TOKEN_BALANCE_TRACKER_USDC = {
    100: "",
    42161: "",
    137: "0x5C50ebc17d002A4484585C8fbf62f51953493c0B",
    8453: "0x0443C55e151dBA13fae079518F9dd01ff9c21CB2",
    42220: "",
    10: "0xA123748Ce7609F507060F947b70298D0bde621E6",
}


def print_box(text: str, margin: int = 1, character: str = "=") -> None:
    """Print text centered within a box."""

    lines = text.split("\n")
    text_length = max(len(line) for line in lines)
    length = text_length + 2 * margin

    border = character * length
    margin_str = " " * margin

    print(border)
    print(f"{margin_str}{text}{margin_str}")
    print(border)
    print()


def print_title(text: str) -> None:
    """Print title."""
    print()
    print_box(text, 4, "=")


def input_with_default_value(prompt: str, default_value: str) -> str:
    user_input = input(f"{prompt} [{default_value}]: ")
    return str(user_input) if user_input else default_value


def input_select_chain() -> str:
    """Chose a single option from the offered ones"""
    user_input = input(f"Chose one of the following options {VALID_CHAINS}: ").lower()
    if user_input in VALID_CHAINS:
        return user_input
    else:
        print("Invalid option selected. Please try again.")
        return input_select_chain()


def get_native_balance_tracker_contract(
    ledger_api: EthereumApi, chain_id: int
) -> Web3Contract:
    with open(
        Path(__file__).parent.parent
        / "mech_client"
        / "abis"
        / "BalanceTrackerFixedPriceNative.json",
        encoding="utf-8",
    ) as f:
        abi = json.load(f)

    native_balance_tracker_contract = get_contract(
        contract_address=CHAIN_TO_NATIVE_BALANCE_TRACKER[chain_id],
        abi=abi,
        ledger_api=ledger_api,
    )
    return native_balance_tracker_contract


def get_token_balance_tracker_contract(
    ledger_api: EthereumApi, chain_id: int, payment_type: PaymentType = PaymentType.TOKEN
) -> Web3Contract:
    with open(
        Path(__file__).parent.parent
        / "mech_client"
        / "abis"
        / "BalanceTrackerFixedPriceToken.json",
        encoding="utf-8",
    ) as f:
        abi = json.load(f)

    if payment_type == PaymentType.USDC_TOKEN:
        balance_tracker_address = CHAIN_TO_TOKEN_BALANCE_TRACKER_USDC[chain_id]
    else:
        balance_tracker_address = CHAIN_TO_TOKEN_BALANCE_TRACKER_OLAS[chain_id]

    token_balance_tracker_contract = get_contract(
        contract_address=balance_tracker_address,
        abi=abi,
        ledger_api=ledger_api,
    )
    return token_balance_tracker_contract


def get_token_contract(
    ledger_api: EthereumApi, chain_id: int, payment_type: PaymentType = PaymentType.TOKEN
) -> Web3Contract:
    with open(
        Path(__file__).parent.parent / "mech_client" / "abis" / "IToken.json",
        encoding="utf-8",
    ) as f:
        abi = json.load(f)

    if payment_type == PaymentType.USDC_TOKEN:
        token_address = CHAIN_TO_PRICE_TOKEN_USDC[chain_id]
    else:
        token_address = CHAIN_TO_PRICE_TOKEN_OLAS[chain_id]

    token_contract = get_contract(
        contract_address=token_address,
        abi=abi,
        ledger_api=ledger_api,
    )

    return token_contract
