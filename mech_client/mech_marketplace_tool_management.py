"""Module for managing mechanical tools and their interactions with blockchain."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import requests
from aea_ledger_ethereum import EthereumApi

from mech_client.marketplace_interact import ADDRESS_ZERO, get_contract, get_mech_config


ABI_DIR_PATH = Path(__file__).parent / "abis"
COMPLEMENTARY_METADATA_HASH_ABI_PATH = (
    ABI_DIR_PATH / "ComplementaryServiceMetadata.json"
)
ENCODING = "utf-8"
DEFAULT_TIMEOUT = 10


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
    include_metadata: bool = False,
) -> Union[List[str], Tuple[List[str], Dict[str, Any]]]:
    """Fetch tools for specified mech's service ID, optionally include metadata."""
    with open(contract_abi_path, encoding=ENCODING) as f:
        abi = json.load(f)

    metadata_contract = get_contract(
        contract_address=complementary_metadata_hash_address,
        abi=abi,
        ledger_api=ledger_api,
    )
    metadata_uri = metadata_contract.functions.tokenURI(service_id).call()
    response = requests.get(metadata_uri, timeout=DEFAULT_TIMEOUT).json()
    tools = response.get("tools", [])

    if include_metadata:
        tool_metadata = response.get("toolMetadata", {})
        return tools, tool_metadata
    return tools


def get_mech_tools(
    service_id: int, chain_config: str = "gnosis", include_metadata: bool = False
) -> Optional[Union[List[str], Tuple[List[str], Dict[str, Any]]]]:
    """
    Fetch tools for a given mech's service ID.

    :param service_id: The service ID of the mech.
    :param chain_config: The chain configuration to use (default is "gnosis").
    :param include_metadata: To include tools metadata or not (default is False)
    :return: A list of tools if successful, or a tuple of (list of tools, metadata) if metadata is included, or None if an error occurs.
    """
    try:
        # Get the mech configuration
        mech_config = get_mech_config(chain_config)
        ledger_config = mech_config.ledger_config

        # Setup Ethereum API
        ledger_api = EthereumApi(**asdict(ledger_config))

        if mech_config.complementary_metadata_hash_address == ADDRESS_ZERO:
            raise NotImplementedError(
                f"Metadata hash not yet implemented on {chain_config}"
            )

        # Fetch tools for the given mech's service ID
        return fetch_tools(
            service_id=service_id,
            ledger_api=ledger_api,
            complementary_metadata_hash_address=mech_config.complementary_metadata_hash_address,
            contract_abi_path=COMPLEMENTARY_METADATA_HASH_ABI_PATH,
            include_metadata=include_metadata,
        )
    except (json.JSONDecodeError, NotImplementedError) as e:
        print(f"An error occurred while fetching tools for mech with {service_id}: {e}")
        return None


def get_tools_for_marketplace_mech(
    service_id: int, chain_config: str = "gnosis"
) -> ToolsForMarketplaceMech:
    """
    Retrieve tools for specified mech's service id.

    :param service_id: specific mech's service ID to fetch tools for.
    :param chain_config: The chain configuration to use.
    :return: Dictionary of tools with identifiers or a mapping of service IDs to tools.
    """
    empty_response = ToolsForMarketplaceMech(service_id=service_id, tools=[])

    try:
        result = get_mech_tools(service_id, chain_config, True)
        if result is None:
            return empty_response

        (tools, tool_metadata) = result
        if not isinstance(tools, list) or not isinstance(tool_metadata, dict):
            return empty_response

        tools_with_ids = [
            ToolInfo(tool_name=tool, unique_identifier=f"{service_id}-{tool}")
            for tool in tools
        ]
        return ToolsForMarketplaceMech(service_id=service_id, tools=tools_with_ids)

    except Exception as e:
        print(f"Error in get_tools_for_agents: {str(e)}")
        raise


def get_tool_description(unique_identifier: str, chain_config: str = "gnosis") -> str:
    """
    Fetch the description of a specific tool based on a unique identifier.

    :param unique_identifier: The unique identifier for the tool.
    :param chain_config: The chain configuration to use.
    :return: Description of the tool or a default message if not available.
    """
    service_id_str, *tool_parts = unique_identifier.split("-")
    try:
        service_id = int(service_id_str)
    except ValueError as exc:
        raise ValueError(
            f"Unexpected unique identifier format: {unique_identifier}"
        ) from exc
    tool_name = "-".join(tool_parts)

    # Get the mech configuration
    mech_config = get_mech_config(chain_config)
    ledger_api = EthereumApi(**asdict(mech_config.ledger_config))

    tools_result = fetch_tools(
        service_id=service_id,
        ledger_api=ledger_api,
        complementary_metadata_hash_address=mech_config.complementary_metadata_hash_address,
        contract_abi_path=COMPLEMENTARY_METADATA_HASH_ABI_PATH,
        include_metadata=True,
    )
    if isinstance(tools_result, tuple) and len(tools_result) == 2:
        _, tool_metadata = tools_result
        tool_info = tool_metadata.get(tool_name, {})
        if isinstance(tool_info, dict):
            return tool_info.get("description", "Description not available")
    return "Description not available"


def get_tool_io_schema(
    unique_identifier: str, chain_config: str = "gnosis"
) -> Dict[str, Any]:
    """
    Fetch the input and output schema along with tool name and description of a specific tool based on a unique identifier.

    :param unique_identifier: The unique identifier for the tool.
    :param chain_config: The chain configuration to use.
    :return: Dictionary containing name, description, input and output schemas.
    """
    service_id_str, *tool_parts = unique_identifier.split("-")
    try:
        service_id = int(service_id_str)
    except ValueError as exc:
        raise ValueError(
            f"Unexpected unique identifier format: {unique_identifier}"
        ) from exc
    tool_name = "-".join(tool_parts)

    # Get the mech configuration
    mech_config = get_mech_config(chain_config)
    ledger_api = EthereumApi(**asdict(mech_config.ledger_config))

    tools_result = fetch_tools(
        service_id=service_id,
        ledger_api=ledger_api,
        complementary_metadata_hash_address=mech_config.complementary_metadata_hash_address,
        contract_abi_path=COMPLEMENTARY_METADATA_HASH_ABI_PATH,
        include_metadata=True,
    )
    if isinstance(tools_result, tuple) and len(tools_result) == 2:
        _, tool_metadata = tools_result
        tool_info = tool_metadata.get(tool_name, {})
        if isinstance(tool_info, dict):
            return {
                "name": tool_info.get("name", {}),
                "description": tool_info.get("description", {}),
                "input": tool_info.get("input", {}),
                "output": tool_info.get("output", {}),
            }

    return {"input": {}, "output": {}}


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
