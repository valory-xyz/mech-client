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

"""Tool service for managing mech tools."""

from typing import Any, Dict, List, Tuple

from mech_client.domain.tools import ToolManager, ToolsForMarketplaceMech


class ToolService:
    """Service for tool discovery and management.

    Provides high-level operations for listing tools, getting descriptions,
    and retrieving schemas.
    """

    def __init__(self, chain_config: str):
        """
        Initialize tool service.

        :param chain_config: Chain configuration name (gnosis, base, etc.)
        """
        self.chain_config = chain_config
        self.tool_manager = ToolManager(chain_config)

    def list_tools(self, service_id: int) -> List[Tuple[str, str]]:
        """
        List all tools for a mech service.

        :param service_id: Service ID of the mech
        :return: List of (tool_name, unique_identifier) tuples
        :raises ValueError: If service not found or has no tools
        """
        tools_info = self.tool_manager.get_tools(service_id)
        if not tools_info:
            raise ValueError(f"No tools found for service {service_id}")

        return [(tool.tool_name, tool.unique_identifier) for tool in tools_info.tools]

    def get_description(self, tool_id: str) -> str:
        """
        Get description for a specific tool.

        :param tool_id: Tool ID in format "service_id-tool_name"
        :return: Tool description
        :raises ValueError: If tool not found
        """
        return self.tool_manager.get_tool_description(tool_id)

    def get_schema(self, tool_id: str) -> Dict[str, Any]:
        """
        Get input/output schema for a specific tool.

        :param tool_id: Tool ID in format "service_id-tool_name"
        :return: Dictionary with name, description, input, output
        :raises ValueError: If tool not found
        """
        return self.tool_manager.get_tool_schema(tool_id)

    def get_tools_info(self, service_id: int) -> ToolsForMarketplaceMech:
        """
        Get complete tools information for a service.

        :param service_id: Service ID of the mech
        :return: ToolsForMarketplaceMech with full tool list
        :raises ValueError: If service not found
        """
        tools_info = self.tool_manager.get_tools(service_id)
        if not tools_info:
            raise ValueError(f"No tools found for service {service_id}")
        return tools_info

    def format_input_schema(self, schema: Dict[str, Any]) -> List[Tuple[str, str]]:
        """
        Format input schema for display.

        :param schema: Input schema dictionary
        :return: List of (field, value) tuples for display
        """
        formatted = []
        for key, value in schema.items():
            if isinstance(value, dict):
                formatted.append((key, str(value)))
            else:
                formatted.append((key, str(value)))
        return formatted

    def format_output_schema(
        self, schema: Dict[str, Any]
    ) -> List[Tuple[str, str, str]]:
        """
        Format output schema for display.

        :param schema: Output schema dictionary
        :return: List of (field, type, description) tuples for display
        """
        formatted = []
        properties = schema.get("properties", {})
        for field_name, field_info in properties.items():
            field_type = field_info.get("type", "unknown")
            description = field_info.get("description", "No description")
            formatted.append((field_name, field_type, description))
        return formatted
