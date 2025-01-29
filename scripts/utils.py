import json
from pathlib import Path
from aea_ledger_ethereum import EthereumApi
from web3.contract import Contract as Web3Contract
from mech_client.marketplace_interact import get_contract, CHAIN_TO_OLAS


# @note remove after testing
CHAIN_TO_OLAS[10200] = "0xC36686E4eAa899734C8C1C7C7f48a8858039DD6D"


# based on mech configs
VALID_CHAINS = [
    "gnosis",
    "arbitrum",
    "polygon",
    "base",
    "celo",
    "optimism",
    "chiado-native",
]

# @todo update after mainnet deployments
CHAIN_TO_NATIVE_BALANCE_TRACKER = {
    100: "",
    10200: "0xD97Db5D3eB1bfF1F88F5c6e2a5259Fb9D2A9875c",
    42161: "",
    137: "",
    8453: "",
    42220: "",
    10: "",
}

# @todo update after mainnet deployments
CHAIN_TO_TOKEN_BALANCE_TRACKER = {
    100: "",
    10200: "0x412eb3f42648533ae3024d41Db57A0fE4329953A",
    42161: "",
    137: "",
    8453: "",
    42220: "",
    10: "",
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


def input_select_chain():
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
    ledger_api: EthereumApi, chain_id: int
) -> Web3Contract:
    with open(
        Path(__file__).parent.parent
        / "mech_client"
        / "abis"
        / "BalanceTrackerFixedPriceToken.json",
        encoding="utf-8",
    ) as f:
        abi = json.load(f)

    token_balance_tracker_contract = get_contract(
        contract_address=CHAIN_TO_TOKEN_BALANCE_TRACKER[chain_id],
        abi=abi,
        ledger_api=ledger_api,
    )
    return token_balance_tracker_contract


def get_token_contract(ledger_api: EthereumApi, chain_id: int) -> Web3Contract:
    with open(
        Path(__file__).parent.parent / "mech_client" / "abis" / "IToken.json",
        encoding="utf-8",
    ) as f:
        abi = json.load(f)

    token_contract = get_contract(
        contract_address=CHAIN_TO_OLAS[chain_id], abi=abi, ledger_api=ledger_api
    )

    return token_contract
