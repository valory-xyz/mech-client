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

"""Tests for tool service."""

from unittest.mock import MagicMock, patch

import pytest

from mech_client.domain.tools import ToolInfo, ToolsForMarketplaceMech
from mech_client.services.tool_service import ToolService


class TestToolServiceInitialization:
    """Tests for ToolService initialization."""

    @patch("mech_client.services.tool_service.ToolManager")
    def test_initialization(self, mock_tool_manager: MagicMock) -> None:
        """Test service initialization."""
        service = ToolService(chain_config="gnosis")

        assert service.chain_config == "gnosis"
        mock_tool_manager.assert_called_once_with("gnosis")


class TestToolServiceOperations:
    """Tests for tool service operations."""


    @patch("mech_client.services.tool_service.ToolManager")
    def test_get_description(self, mock_tool_manager: MagicMock) -> None:
        """Test getting tool description."""
        mock_manager_instance = MagicMock()
        mock_tool_manager.return_value = mock_manager_instance
        mock_manager_instance.get_tool_description.return_value = (
            "GPT-4 language model"
        )

        service = ToolService(chain_config="gnosis")
        result = service.get_description(tool_id="1-openai-gpt-4")

        assert result == "GPT-4 language model"
        mock_manager_instance.get_tool_description.assert_called_once_with(
            "1-openai-gpt-4"
        )

    @patch("mech_client.services.tool_service.ToolManager")
    def test_get_schema(self, mock_tool_manager: MagicMock) -> None:
        """Test getting tool schema."""
        mock_manager_instance = MagicMock()
        mock_tool_manager.return_value = mock_manager_instance

        schema = {
            "name": "openai-gpt-4",
            "description": "GPT-4 model",
            "input": {"type": "object", "properties": {"prompt": {"type": "string"}}},
            "output": {"type": "string"},
        }
        mock_manager_instance.get_tool_schema.return_value = schema

        service = ToolService(chain_config="gnosis")
        result = service.get_schema(tool_id="1-openai-gpt-4")

        assert result == schema
        mock_manager_instance.get_tool_schema.assert_called_once_with("1-openai-gpt-4")

    @patch("mech_client.services.tool_service.ToolManager")
    def test_get_tools_info_success(self, mock_tool_manager: MagicMock) -> None:
        """Test getting complete tools info."""
        mock_manager_instance = MagicMock()
        mock_tool_manager.return_value = mock_manager_instance

        tools_info = ToolsForMarketplaceMech(
            service_id=1,
            tools=[],
        )
        mock_manager_instance.get_tools.return_value = tools_info

        service = ToolService(chain_config="gnosis")
        result = service.get_tools_info(service_id=1)

        assert result == tools_info
        mock_manager_instance.get_tools.assert_called_once_with(1)

    @patch("mech_client.services.tool_service.ToolManager")
    def test_get_tools_info_not_found(self, mock_tool_manager: MagicMock) -> None:
        """Test getting tools info when not found."""
        mock_manager_instance = MagicMock()
        mock_tool_manager.return_value = mock_manager_instance
        mock_manager_instance.get_tools.return_value = None

        service = ToolService(chain_config="gnosis")

        with pytest.raises(ValueError, match="No tools found"):
            service.get_tools_info(service_id=999)


class TestToolServiceFormatting:
    """Tests for schema formatting methods."""

    @patch("mech_client.services.tool_service.ToolManager")
    def test_format_input_schema(self, mock_tool_manager: MagicMock) -> None:
        """Test formatting input schema for display."""
        service = ToolService(chain_config="gnosis")

        schema = {
            "type": "object",
            "properties": {"prompt": {"type": "string"}, "temperature": 0.7},
        }

        result = service.format_input_schema(schema)

        assert len(result) == 2
        assert ("type", "object") in result
        assert ("properties", str(schema["properties"])) in result

    @patch("mech_client.services.tool_service.ToolManager")
    def test_format_output_schema(self, mock_tool_manager: MagicMock) -> None:
        """Test formatting output schema for display."""
        service = ToolService(chain_config="gnosis")

        schema = {
            "type": "object",
            "properties": {
                "result": {"type": "string", "description": "Model output"},
                "confidence": {"type": "number", "description": "Confidence score"},
            },
        }

        result = service.format_output_schema(schema)

        assert len(result) == 2
        assert ("result", "string", "Model output") in result
        assert ("confidence", "number", "Confidence score") in result

    @patch("mech_client.services.tool_service.ToolManager")
    def test_format_output_schema_missing_fields(
        self, mock_tool_manager: MagicMock
    ) -> None:
        """Test formatting output schema with missing optional fields."""
        service = ToolService(chain_config="gnosis")

        schema = {
            "type": "object",
            "properties": {
                "result": {},  # Missing type and description
            },
        }

        result = service.format_output_schema(schema)

        assert len(result) == 1
        assert result[0] == ("result", "unknown", "No description")
