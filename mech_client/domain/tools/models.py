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

"""Tool data models."""

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class ToolInfo:
    """Information about a single tool.

    Attributes:
        tool_name: Name of the tool (e.g., "openai-gpt-4")
        unique_identifier: Unique ID for the tool (service_id-tool_name)
    """

    tool_name: str
    unique_identifier: str


@dataclass
class ToolsForMarketplaceMech:
    """Collection of tools for a marketplace mech.

    Attributes:
        service_id: Olas service ID for the mech
        tools: List of tool information
    """

    service_id: int
    tools: List[ToolInfo]


@dataclass
class ToolSchema:
    """Tool input/output schema.

    Attributes:
        name: Tool name
        description: Tool description
        input_schema: Input field definitions
        output_schema: Output field definitions
    """

    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
