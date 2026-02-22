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

"""Tests for infrastructure.operate.manager and key_manager."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestOperateManager:
    """Tests for OperateManager."""

    def test_default_operate_path(self) -> None:
        """Test that default operate path is in home directory."""
        with patch("mech_client.infrastructure.operate.manager.OperateApp"):
            from mech_client.infrastructure.operate.manager import (  # pylint: disable=import-outside-toplevel
                OperateManager,
                OPERATE_FOLDER_NAME,
            )

            manager = OperateManager()
            assert manager.operate_path == Path.home() / OPERATE_FOLDER_NAME

    def test_custom_operate_path(self, tmp_path: Path) -> None:
        """Test that custom operate path is accepted."""
        with patch("mech_client.infrastructure.operate.manager.OperateApp"):
            from mech_client.infrastructure.operate.manager import (  # pylint: disable=import-outside-toplevel
                OperateManager,
            )

            manager = OperateManager(operate_path=tmp_path)
            assert manager.operate_path == tmp_path

    def test_env_path_is_under_operate_path(self, tmp_path: Path) -> None:
        """Test that env_path is .env under operate_path."""
        with patch("mech_client.infrastructure.operate.manager.OperateApp"):
            from mech_client.infrastructure.operate.manager import (  # pylint: disable=import-outside-toplevel
                OperateManager,
            )

            manager = OperateManager(operate_path=tmp_path)
            assert manager.env_path == tmp_path / ".env"

    def test_operate_property_lazy_loads(self, tmp_path: Path) -> None:
        """Test that operate property creates OperateApp only on first access."""
        with patch(
            "mech_client.infrastructure.operate.manager.OperateApp"
        ) as mock_app_cls:
            mock_app_cls.return_value = MagicMock()
            from mech_client.infrastructure.operate.manager import (  # pylint: disable=import-outside-toplevel
                OperateManager,
            )

            manager = OperateManager(operate_path=tmp_path)
            assert manager._operate is None  # pylint: disable=protected-access

            _ = manager.operate  # trigger lazy load
            mock_app_cls.assert_called_once_with(tmp_path)

    def test_operate_property_caches_instance(self, tmp_path: Path) -> None:
        """Test that operate property returns the same instance on repeated access."""
        with patch(
            "mech_client.infrastructure.operate.manager.OperateApp"
        ) as mock_app_cls:
            mock_instance = MagicMock()
            mock_app_cls.return_value = mock_instance
            from mech_client.infrastructure.operate.manager import (  # pylint: disable=import-outside-toplevel
                OperateManager,
            )

            manager = OperateManager(operate_path=tmp_path)
            op1 = manager.operate
            op2 = manager.operate
            assert op1 is op2
            mock_app_cls.assert_called_once()

    def test_is_initialized_true_when_path_exists(self, tmp_path: Path) -> None:
        """Test is_initialized returns True when operate_path exists."""
        with patch("mech_client.infrastructure.operate.manager.OperateApp"):
            from mech_client.infrastructure.operate.manager import (  # pylint: disable=import-outside-toplevel
                OperateManager,
            )

            manager = OperateManager(operate_path=tmp_path)
            assert manager.is_initialized() is True

    def test_is_initialized_false_when_path_missing(self, tmp_path: Path) -> None:
        """Test is_initialized returns False when operate_path does not exist."""
        with patch("mech_client.infrastructure.operate.manager.OperateApp"):
            from mech_client.infrastructure.operate.manager import (  # pylint: disable=import-outside-toplevel
                OperateManager,
            )

            missing_path = tmp_path / "nonexistent"
            manager = OperateManager(operate_path=missing_path)
            assert manager.is_initialized() is False

    def test_get_password_from_env_file(self, tmp_path: Path) -> None:
        """Test get_password reads password from .env file when present."""
        env_file = tmp_path / ".env"
        env_file.write_text("OPERATE_PASSWORD=mysecretpassword\n")

        with patch("mech_client.infrastructure.operate.manager.OperateApp"):
            with patch(
                "mech_client.infrastructure.operate.manager.EnvironmentConfig.load"
            ) as mock_env_load:
                mock_env_load.return_value.operate_password = "mysecretpassword"
                from mech_client.infrastructure.operate.manager import (  # pylint: disable=import-outside-toplevel
                    OperateManager,
                )

                manager = OperateManager(operate_path=tmp_path)
                pwd = manager.get_password()

        assert pwd == "mysecretpassword"
        assert os.environ.get("OPERATE_PASSWORD") == "mysecretpassword"

    @patch("mech_client.infrastructure.operate.manager.ask_password_if_needed")
    def test_get_password_prompts_when_no_env_file(
        self, mock_ask: MagicMock, tmp_path: Path
    ) -> None:
        """Test get_password prompts user when no .env file exists."""
        with patch(
            "mech_client.infrastructure.operate.manager.OperateApp"
        ) as mock_app_cls:
            mock_operate = MagicMock()
            mock_operate.password = "prompted_password"
            mock_app_cls.return_value = mock_operate
            with patch("mech_client.infrastructure.operate.manager.set_key"):
                from mech_client.infrastructure.operate.manager import (  # pylint: disable=import-outside-toplevel
                    OperateManager,
                )

                manager = OperateManager(operate_path=tmp_path / "new_dir")
                pwd = manager.get_password()

        mock_ask.assert_called_once()
        assert pwd == "prompted_password"

    @patch("mech_client.infrastructure.operate.manager.ask_password_if_needed")
    def test_get_password_raises_when_password_not_set(
        self, mock_ask: MagicMock, tmp_path: Path
    ) -> None:
        """Test get_password raises Exception when password cannot be obtained."""
        with patch(
            "mech_client.infrastructure.operate.manager.OperateApp"
        ) as mock_app_cls:
            mock_operate = MagicMock()
            mock_operate.password = None  # password was not set
            mock_app_cls.return_value = mock_operate
            from mech_client.infrastructure.operate.manager import (  # pylint: disable=import-outside-toplevel
                OperateManager,
            )

            manager = OperateManager(operate_path=tmp_path / "new_dir")
            with pytest.raises(Exception, match="Password could not be set"):
                manager.get_password()


class TestFetchAgentModeKeys:
    """Tests for fetch_agent_mode_keys function."""

    @patch("mech_client.infrastructure.operate.key_manager.OperateManager")
    @patch("mech_client.infrastructure.operate.key_manager.KeysManager")
    @patch("mech_client.infrastructure.operate.key_manager.EnvironmentConfig.load")
    @patch("mech_client.infrastructure.operate.key_manager.operate_logger")
    def test_success(
        self,
        mock_logger: MagicMock,
        mock_env_load: MagicMock,
        mock_keys_manager_cls: MagicMock,
        mock_operate_manager_cls: MagicMock,
    ) -> None:
        """Test successful key fetching for a deployed service."""
        from mech_client.infrastructure.operate.key_manager import (  # pylint: disable=import-outside-toplevel
            fetch_agent_mode_keys,
        )

        # Set up OperateManager mock
        mock_manager = MagicMock()
        mock_operate_manager_cls.return_value = mock_manager
        mock_operate = MagicMock()
        mock_manager.operate = mock_operate

        # Service manager mock
        mock_service_manager = MagicMock()
        mock_operate.service_manager.return_value = mock_service_manager
        mock_service_manager.json = [
            {"home_chain": "gnosis", "service_config_id": "config-123"}
        ]

        # Service instance mock
        mock_service = MagicMock()
        mock_service_manager.load.return_value = mock_service
        mock_service.agent_addresses = ["0xAgentAddress"]
        mock_service.chain_configs = {
            "gnosis": MagicMock(chain_data=MagicMock(multisig="0xSafeAddress"))
        }

        # KeysManager mock
        mock_keys_manager = MagicMock()
        mock_keys_manager_cls.return_value = mock_keys_manager
        expected_key_path = Path("/path/to/keyfile.json")
        mock_keys_manager.get_private_key_file.return_value = expected_key_path

        # Env config
        mock_env_load.return_value.operate_password = "testpassword"

        safe_address, key_path, password = fetch_agent_mode_keys("gnosis")

        assert safe_address == "0xSafeAddress"
        assert key_path == str(expected_key_path)
        assert password == "testpassword"

    @patch("mech_client.infrastructure.operate.key_manager.OperateManager")
    @patch("mech_client.infrastructure.operate.key_manager.KeysManager")
    @patch("mech_client.infrastructure.operate.key_manager.EnvironmentConfig.load")
    @patch("mech_client.infrastructure.operate.key_manager.operate_logger")
    def test_raises_when_no_service_for_chain(
        self,
        mock_logger: MagicMock,
        mock_env_load: MagicMock,
        mock_keys_manager_cls: MagicMock,
        mock_operate_manager_cls: MagicMock,
    ) -> None:
        """Test exception raised when no service found for the given chain."""
        from mech_client.infrastructure.operate.key_manager import (  # pylint: disable=import-outside-toplevel
            fetch_agent_mode_keys,
        )

        mock_manager = MagicMock()
        mock_operate_manager_cls.return_value = mock_manager
        mock_operate = MagicMock()
        mock_manager.operate = mock_operate

        mock_service_manager = MagicMock()
        mock_operate.service_manager.return_value = mock_service_manager
        # No services for "polygon"
        mock_service_manager.json = [
            {"home_chain": "gnosis", "service_config_id": "config-123"}
        ]

        with pytest.raises(Exception, match="Cannot find deployed service id"):
            fetch_agent_mode_keys("polygon")
