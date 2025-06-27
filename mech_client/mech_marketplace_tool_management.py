"""Module for managing mechanical tools and their interactions with blockchain."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from aea_ledger_ethereum import EthereumApi

from mech_client.marketplace_interact import ADDRESS_ZERO, get_contract, get_mech_config


ABI_DIR_PATH = Path(__file__).parent / "abis"
COMPLEMENTARY_METADATA_HASH_ABI_PATH = (
    ABI_DIR_PATH / "ComplementaryServiceMetadata.json"
)
ENCODING = "utf-8"
DEFAULT_TIMEOUT = 10
TOOLS = "tools"
TOOL_METADATA = "toolMetadata"
DEFAULT_CONFIG = "gnosis"


@dataclass
class ToolInfo:
    """Tool info"""

    tool_name: str
    unique_identifier: str


@dataclass
class ToolsForMarketplaceMech:
    """Tools info list"""

    service_id: int
    tools: List[ToolInfo]


def fetch_tools(
    service_id: int,
    ledger_api: EthereumApi,
    complementary_metadata_hash_address: str,
    contract_abi_path: Path,
) -> Dict[str, Any]:
    """Fetch tools for specified mech's service ID."""
    with open(contract_abi_path, encoding=ENCODING) as f:
        abi = json.load(f)

    metadata_contract = get_contract(
        contract_address=complementary_metadata_hash_address,
        abi=abi,
        ledger_api=ledger_api,
    )
    metadata_uri = metadata_contract.functions.tokenURI(service_id).call()
    return requests.get(metadata_uri, timeout=DEFAULT_TIMEOUT).json()


def get_mech_tools(
    service_id: int, chain_config: str = DEFAULT_CONFIG
) -> Optional[Dict[str, Any]]:
    """
    Fetch tools for a given mech's service ID.

    :param service_id: The service ID of the mech.
    :param chain_config: The chain configuration to use (default is "gnosis").
    :return: A dictionary containing the JSON response from the `tokenURI` contract call, typically including tools and metadata.
    """
    # Get the mech configuration
    mech_config = get_mech_config(chain_config)
    ledger_config = mech_config.ledger_config

    # Setup Ethereum API
    ledger_api = EthereumApi(**asdict(ledger_config))

    if mech_config.complementary_metadata_hash_address == ADDRESS_ZERO:
        print(f"Metadata hash not yet implemented on {chain_config}")
        return None

    try:
        # Fetch tools for the given mech's service ID
        return fetch_tools(
            service_id=service_id,
            ledger_api=ledger_api,
            complementary_metadata_hash_address=mech_config.complementary_metadata_hash_address,
            contract_abi_path=COMPLEMENTARY_METADATA_HASH_ABI_PATH,
        )
    except (json.JSONDecodeError, NotImplementedError) as e:
        print(f"An error occurred while fetching tools for mech with {service_id}: {e}")
        return None


def get_tools_for_marketplace_mech(
    service_id: int, chain_config: str = DEFAULT_CONFIG
) -> ToolsForMarketplaceMech:
    """
    Retrieve tools for specified mech's service id.

    :param service_id: specific mech's service ID to fetch tools for.
    :param chain_config: The chain configuration to use.
    :return: Dictionary of tools with identifiers or a mapping of service IDs to tools.
    """
    empty_response = ToolsForMarketplaceMech(service_id=service_id, tools=[])

    try:
        result = get_mech_tools(service_id, chain_config)
        if result is None:
            return empty_response

        tools = result.get(TOOLS, [])
        tool_metadata = result.get(TOOL_METADATA, {})
        if not isinstance(tools, list) or not isinstance(tool_metadata, dict):
            return empty_response

        tools_with_ids = [
            ToolInfo(tool_name=tool, unique_identifier=f"{service_id}-{tool}")
            for tool in tools
        ]
        return ToolsForMarketplaceMech(service_id=service_id, tools=tools_with_ids)

    except (json.JSONDecodeError, NotImplementedError) as e:
        print(f"Error in get_tools_for_marketplace_mech: {str(e)}")
        raise


def get_tool_description(
    unique_identifier: str, chain_config: str = DEFAULT_CONFIG
) -> str:
    """
    Fetch the description of a specific tool based on a unique identifier.

    :param unique_identifier: The unique identifier for the tool.
    :param chain_config: The chain configuration to use.
    :return: Description of the tool or a default message if not available.
    """
    default_response = "Description not available"

    _, tool_info = _get_tool_metadata(unique_identifier, chain_config)
    return (
        tool_info.get("description", default_response)
        if tool_info
        else default_response
    )


def get_tool_io_schema(
    unique_identifier: str, chain_config: str = DEFAULT_CONFIG
) -> Dict[str, Any]:
    """
    Fetch the input and output schema along with tool name and description of a specific tool based on a unique identifier.

    :param unique_identifier: The unique identifier for the tool.
    :param chain_config: The chain configuration to use.
    :return: Dictionary containing name, description, input and output schemas.
    """
    _, tool_info = _get_tool_metadata(unique_identifier, chain_config)
    if tool_info:
        return {
            "name": tool_info.get("name", {}),
            "description": tool_info.get("description", {}),
            "input": tool_info.get("input", {}),
            "output": tool_info.get("output", {}),
        }

    return {"input": {}, "output": {}}


def _get_tool_metadata(
    unique_identifier: str, chain_config: str = DEFAULT_CONFIG
) -> Tuple[str, Optional[Dict[str, Any]]]:
    """
    Helper function to extract tool metadata from the chain config and unique identifier.

    :param unique_identifier: The unique identifier in the format "<service_id>-<tool_name>".
    :param chain_config: The chain configuration to use.
    :return: Tuple of tool name and its metadata dictionary (or None if not found).
    """
    service_id_str, *tool_parts = unique_identifier.split("-")
    try:
        service_id = int(service_id_str)
    except ValueError as exc:
        raise ValueError(
            f"Unexpected unique identifier format: {unique_identifier}"
        ) from exc
    tool_name = "-".join(tool_parts)

    result = get_mech_tools(service_id, chain_config)

    if isinstance(result, dict):
        tool_metadata = result.get(TOOL_METADATA, {})
        tool_info = tool_metadata.get(tool_name)
        if isinstance(tool_info, dict):
            return tool_name, tool_info

    return tool_name, None


def extract_input_schema(input_data: Dict[str, Any]) -> List[Tuple[str, Any]]:
    """
    Extract the schema from input data.

    :param input_data: A dictionary representing the input data.
    :return: A list of key-value pairs representing the input schema.
    """
    return [(key, input_data[key]) for key in input_data]


def extract_output_schema(output_data: Dict[str, Any]) -> List[Tuple[str, str, str]]:
    """
    Extract the output schema from the output data.

    :param output_data: A dictionary representing the output data.
    :return: A list of list of tuples representing the output schema.
    """
    schema = output_data.get("schema", {})
    if "properties" not in schema:
        return []

    return [
        (key, value.get("type", ""), value.get("description", ""))
        for key, value in schema["properties"].items()
    ]
