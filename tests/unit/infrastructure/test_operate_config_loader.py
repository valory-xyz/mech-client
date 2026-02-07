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

"""Tests for operate configuration loader."""

from unittest.mock import MagicMock, patch

import pytest

from mech_client.infrastructure.operate.config_loader import (
    _extract_rpc_from_service,
    _find_service_for_chain,
    load_rpc_from_operate,
)


class TestLoadRpcFromOperate:
    """Tests for load_rpc_from_operate function."""

    @patch("mech_client.infrastructure.operate.config_loader.OperateManager")
    def test_returns_none_when_operate_not_initialized(
        self, mock_manager_class: MagicMock
    ) -> None:
        """Test that None is returned when operate is not initialized."""
        mock_manager = MagicMock()
        mock_manager.is_initialized.return_value = False
        mock_manager_class.return_value = mock_manager

        result = load_rpc_from_operate("gnosis")

        assert result is None
        mock_manager.is_initialized.assert_called_once()

    @patch("mech_client.infrastructure.operate.config_loader.OperateManager")
    def test_returns_rpc_when_service_found_with_valid_config(
        self, mock_manager_class: MagicMock
    ) -> None:
        """Test that RPC is returned when service has valid configuration."""
        # Setup mock manager
        mock_manager = MagicMock()
        mock_manager.is_initialized.return_value = True
        mock_manager_class.return_value = mock_manager

        # Setup mock service with RPC config
        mock_ledger_config = MagicMock()
        mock_ledger_config.rpc = "https://rpc.from.operate.com"

        mock_chain_data = MagicMock()
        mock_chain_data.ledger_config = mock_ledger_config

        mock_service = MagicMock()
        mock_service.chain_configs = {"gnosis": mock_chain_data}

        mock_service_manager = MagicMock()
        mock_service_manager.json = [
            {"home_chain": "gnosis", "service_config_id": "test-service-id"}
        ]
        mock_service_manager.load.return_value = mock_service

        mock_operate = MagicMock()
        mock_operate.service_manager.return_value = mock_service_manager
        mock_manager.operate = mock_operate

        result = load_rpc_from_operate("gnosis")

        assert result == "https://rpc.from.operate.com"
        mock_service_manager.load.assert_called_once_with("test-service-id")

    @patch("mech_client.infrastructure.operate.config_loader.OperateManager")
    def test_returns_none_when_service_not_found(
        self, mock_manager_class: MagicMock
    ) -> None:
        """Test that None is returned when no service found for chain."""
        mock_manager = MagicMock()
        mock_manager.is_initialized.return_value = True
        mock_manager_class.return_value = mock_manager

        mock_service_manager = MagicMock()
        mock_service_manager.json = [
            {"home_chain": "base", "service_config_id": "base-service"}
        ]

        mock_operate = MagicMock()
        mock_operate.service_manager.return_value = mock_service_manager
        mock_manager.operate = mock_operate

        result = load_rpc_from_operate("gnosis")

        assert result is None

    @patch("mech_client.infrastructure.operate.config_loader.OperateManager")
    def test_returns_none_when_chain_not_in_service_configs(
        self, mock_manager_class: MagicMock
    ) -> None:
        """Test that None is returned when chain not in service chain_configs."""
        mock_manager = MagicMock()
        mock_manager.is_initialized.return_value = True
        mock_manager_class.return_value = mock_manager

        mock_service = MagicMock()
        mock_service.chain_configs = {"base": MagicMock()}

        mock_service_manager = MagicMock()
        mock_service_manager.json = [
            {"home_chain": "gnosis", "service_config_id": "test-service"}
        ]
        mock_service_manager.load.return_value = mock_service

        mock_operate = MagicMock()
        mock_operate.service_manager.return_value = mock_service_manager
        mock_manager.operate = mock_operate

        result = load_rpc_from_operate("gnosis")

        assert result is None

    @patch("mech_client.infrastructure.operate.config_loader.OperateManager")
    def test_returns_none_when_ledger_config_missing(
        self, mock_manager_class: MagicMock
    ) -> None:
        """Test that None is returned when ledger_config is missing."""
        mock_manager = MagicMock()
        mock_manager.is_initialized.return_value = True
        mock_manager_class.return_value = mock_manager

        mock_chain_data = MagicMock()
        mock_chain_data.ledger_config = None

        mock_service = MagicMock()
        mock_service.chain_configs = {"gnosis": mock_chain_data}

        mock_service_manager = MagicMock()
        mock_service_manager.json = [
            {"home_chain": "gnosis", "service_config_id": "test-service"}
        ]
        mock_service_manager.load.return_value = mock_service

        mock_operate = MagicMock()
        mock_operate.service_manager.return_value = mock_service_manager
        mock_manager.operate = mock_operate

        result = load_rpc_from_operate("gnosis")

        assert result is None

    @patch("mech_client.infrastructure.operate.config_loader.OperateManager")
    def test_returns_none_when_rpc_attribute_missing(
        self, mock_manager_class: MagicMock
    ) -> None:
        """Test that None is returned when rpc attribute is missing."""
        mock_manager = MagicMock()
        mock_manager.is_initialized.return_value = True
        mock_manager_class.return_value = mock_manager

        # Create ledger_config without rpc attribute
        mock_ledger_config = MagicMock(spec=[])  # No attributes

        mock_chain_data = MagicMock()
        mock_chain_data.ledger_config = mock_ledger_config

        mock_service = MagicMock()
        mock_service.chain_configs = {"gnosis": mock_chain_data}

        mock_service_manager = MagicMock()
        mock_service_manager.json = [
            {"home_chain": "gnosis", "service_config_id": "test-service"}
        ]
        mock_service_manager.load.return_value = mock_service

        mock_operate = MagicMock()
        mock_operate.service_manager.return_value = mock_service_manager
        mock_manager.operate = mock_operate

        result = load_rpc_from_operate("gnosis")

        assert result is None

    @patch("mech_client.infrastructure.operate.config_loader.OperateManager")
    def test_returns_none_on_exception(self, mock_manager_class: MagicMock) -> None:
        """Test that None is returned when an exception occurs."""
        mock_manager = MagicMock()
        mock_manager.is_initialized.side_effect = Exception("Test error")
        mock_manager_class.return_value = mock_manager

        result = load_rpc_from_operate("gnosis")

        assert result is None


class TestFindServiceForChain:
    """Tests for _find_service_for_chain helper function."""

    def test_returns_service_when_found(self) -> None:
        """Test that service is returned when chain matches."""
        mock_service = MagicMock()
        mock_service_manager = MagicMock()
        mock_service_manager.json = [
            {"home_chain": "gnosis", "service_config_id": "test-service"}
        ]
        mock_service_manager.load.return_value = mock_service

        mock_operate = MagicMock()
        mock_operate.service_manager.return_value = mock_service_manager

        result = _find_service_for_chain(mock_operate, "gnosis")

        assert result == mock_service
        mock_service_manager.load.assert_called_once_with("test-service")

    def test_returns_none_when_not_found(self) -> None:
        """Test that None is returned when no matching chain."""
        mock_service_manager = MagicMock()
        mock_service_manager.json = [
            {"home_chain": "base", "service_config_id": "base-service"}
        ]

        mock_operate = MagicMock()
        mock_operate.service_manager.return_value = mock_service_manager

        result = _find_service_for_chain(mock_operate, "gnosis")

        assert result is None

    def test_returns_first_matching_service(self) -> None:
        """Test that first matching service is returned when multiple exist."""
        mock_service = MagicMock()
        mock_service_manager = MagicMock()
        mock_service_manager.json = [
            {"home_chain": "gnosis", "service_config_id": "first-service"},
            {"home_chain": "gnosis", "service_config_id": "second-service"},
        ]
        mock_service_manager.load.return_value = mock_service

        mock_operate = MagicMock()
        mock_operate.service_manager.return_value = mock_service_manager

        result = _find_service_for_chain(mock_operate, "gnosis")

        assert result == mock_service
        # Should only load the first matching service
        mock_service_manager.load.assert_called_once_with("first-service")


class TestExtractRpcFromService:
    """Tests for _extract_rpc_from_service helper function."""

    def test_extracts_rpc_successfully(self) -> None:
        """Test successful RPC extraction."""
        mock_ledger_config = MagicMock()
        mock_ledger_config.rpc = "https://test.rpc.com"

        mock_chain_data = MagicMock()
        mock_chain_data.ledger_config = mock_ledger_config

        mock_service = MagicMock()
        mock_service.chain_configs = {"gnosis": mock_chain_data}

        result = _extract_rpc_from_service(mock_service, "gnosis")

        assert result == "https://test.rpc.com"

    def test_returns_none_when_chain_not_in_configs(self) -> None:
        """Test None returned when chain not in chain_configs."""
        mock_service = MagicMock()
        mock_service.chain_configs = {"base": MagicMock()}

        result = _extract_rpc_from_service(mock_service, "gnosis")

        assert result is None

    def test_returns_none_when_ledger_config_missing(self) -> None:
        """Test None returned when ledger_config is None."""
        mock_chain_data = MagicMock()
        mock_chain_data.ledger_config = None

        mock_service = MagicMock()
        mock_service.chain_configs = {"gnosis": mock_chain_data}

        result = _extract_rpc_from_service(mock_service, "gnosis")

        assert result is None

    def test_returns_none_when_ledger_config_attribute_missing(self) -> None:
        """Test None returned when ledger_config attribute doesn't exist."""
        mock_chain_data = MagicMock(spec=[])  # No attributes

        mock_service = MagicMock()
        mock_service.chain_configs = {"gnosis": mock_chain_data}

        result = _extract_rpc_from_service(mock_service, "gnosis")

        assert result is None

    def test_returns_none_when_rpc_missing(self) -> None:
        """Test None returned when rpc is None."""
        mock_ledger_config = MagicMock()
        mock_ledger_config.rpc = None

        mock_chain_data = MagicMock()
        mock_chain_data.ledger_config = mock_ledger_config

        mock_service = MagicMock()
        mock_service.chain_configs = {"gnosis": mock_chain_data}

        result = _extract_rpc_from_service(mock_service, "gnosis")

        assert result is None

    def test_returns_none_when_rpc_attribute_missing(self) -> None:
        """Test None returned when rpc attribute doesn't exist."""
        mock_ledger_config = MagicMock(spec=[])  # No rpc attribute

        mock_chain_data = MagicMock()
        mock_chain_data.ledger_config = mock_ledger_config

        mock_service = MagicMock()
        mock_service.chain_configs = {"gnosis": mock_chain_data}

        result = _extract_rpc_from_service(mock_service, "gnosis")

        assert result is None
