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

"""Tests for key manager."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mech_client.infrastructure.operate.key_manager import fetch_agent_mode_keys


class TestFetchAgentModeKeys:
    """Tests for fetch_agent_mode_keys function."""

    @patch("mech_client.infrastructure.operate.key_manager.OperateManager")
    def test_fetch_keys_returns_none_password(
        self,
        mock_operate_manager_cls: MagicMock,
    ) -> None:
        """Test that fetch_agent_mode_keys returns None as password."""
        # Setup
        mock_manager = MagicMock()
        mock_manager.operate_path = Path("/fake/.operate_mech_client")
        mock_operate_manager_cls.return_value = mock_manager

        mock_service = MagicMock()
        mock_service.agent_addresses = ["0xAgent1234"]
        mock_chain_data = MagicMock()
        mock_chain_data.multisig = "0xSafe5678"
        mock_service.chain_configs = {
            "gnosis": MagicMock(chain_data=mock_chain_data)
        }

        mock_service_manager = MagicMock()
        mock_service_manager.json = [
            {"home_chain": "gnosis", "service_config_id": "test-id"}
        ]
        mock_service_manager.load.return_value = mock_service

        mock_manager.operate.service_manager.return_value = mock_service_manager

        # Execute
        safe_address, key_path, password = fetch_agent_mode_keys("gnosis")

        # Verify password is None
        assert password is None
        assert safe_address == "0xSafe5678"

    @patch("mech_client.infrastructure.operate.key_manager.OperateManager")
    def test_fetch_keys_constructs_key_path(
        self,
        mock_operate_manager_cls: MagicMock,
    ) -> None:
        """Test that key path is {keys_dir}/{agent_address}_private_key."""
        # Setup
        operate_path = Path("/fake/.operate_mech_client")
        mock_manager = MagicMock()
        mock_manager.operate_path = operate_path
        mock_operate_manager_cls.return_value = mock_manager

        mock_service = MagicMock()
        mock_service.agent_addresses = ["0xAgent1234"]
        mock_chain_data = MagicMock()
        mock_chain_data.multisig = "0xSafe5678"
        mock_service.chain_configs = {
            "gnosis": MagicMock(chain_data=mock_chain_data)
        }

        mock_service_manager = MagicMock()
        mock_service_manager.json = [
            {"home_chain": "gnosis", "service_config_id": "test-id"}
        ]
        mock_service_manager.load.return_value = mock_service

        mock_manager.operate.service_manager.return_value = mock_service_manager

        # Execute
        _, key_path, _ = fetch_agent_mode_keys("gnosis")

        # Verify key path
        expected = str(operate_path / "keys" / "0xAgent1234_private_key")
        assert key_path == expected

    @patch("mech_client.infrastructure.operate.key_manager.OperateManager")
    def test_fetch_keys_no_service_raises(
        self,
        mock_operate_manager_cls: MagicMock,
    ) -> None:
        """Test that exception is raised when no service found for chain."""
        # Setup
        mock_manager = MagicMock()
        mock_manager.operate_path = Path("/fake/.operate_mech_client")
        mock_operate_manager_cls.return_value = mock_manager

        mock_service_manager = MagicMock()
        mock_service_manager.json = [
            {"home_chain": "polygon", "service_config_id": "test-id"}
        ]
        mock_manager.operate.service_manager.return_value = mock_service_manager

        # Execute & Verify
        with pytest.raises(
            Exception, match="Cannot find deployed service id for chain gnosis"
        ):
            fetch_agent_mode_keys("gnosis")
