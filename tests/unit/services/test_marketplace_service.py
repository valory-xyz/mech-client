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

"""Tests for marketplace service."""

from unittest.mock import MagicMock, patch

import pytest

from mech_client.services.marketplace_service import MarketplaceService


class TestMarketplaceServiceValidation:
    """Tests for input validation in marketplace service."""

    def test_send_request_validates_prompt_tool_count(self) -> None:
        """Test that mismatched prompts/tools raises ValueError."""
        # Create a minimal mock service without full initialization
        service = MagicMock(spec=MarketplaceService)
        service.send_request = MarketplaceService.send_request.__get__(
            service, MarketplaceService
        )

        # The validation happens before any API calls, so we don't need mocks
        with pytest.raises(ValueError, match="must match"):
            # This will raise in the validation step
            import asyncio

            asyncio.run(
                service.send_request(
                    prompts=("prompt1", "prompt2"),
                    tools=("tool1",),  # Only one tool for two prompts
                )
            )
