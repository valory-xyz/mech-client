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

"""Operate middleware manager for agent mode operations."""

import os
from pathlib import Path
from typing import Optional

from dotenv import set_key
from operate.cli import OperateApp
from operate.quickstart.run_service import ask_password_if_needed

from mech_client.infrastructure.config.environment import EnvironmentConfig


OPERATE_FOLDER_NAME = ".operate_mech_client"


class OperateManager:
    """Manager for Operate middleware integration.

    Provides methods for setting up agent mode, managing passwords,
    and accessing Operate services.
    """

    def __init__(self, operate_path: Optional[Path] = None):
        """
        Initialize Operate manager.

        :param operate_path: Path to operate directory (default: ~/.operate_mech_client)
        """
        if operate_path is None:
            operate_path = Path.home() / OPERATE_FOLDER_NAME
        self.operate_path = operate_path
        self.env_path = operate_path / ".env"
        self._operate: Optional[OperateApp] = None

    @property
    def operate(self) -> OperateApp:
        """Get OperateApp instance (lazy-loaded).

        :return: OperateApp instance
        """
        if self._operate is None:
            self._operate = OperateApp(self.operate_path)
        return self._operate

    def get_password(self) -> str:
        """
        Load password from .env if present, otherwise prompt and persist.

        :return: Operate password
        :raises Exception: If password could not be set
        """
        # Try loading from environment file
        if self.env_path.exists():
            from dotenv import load_dotenv  # pylint: disable=import-outside-toplevel

            load_dotenv(dotenv_path=self.env_path, override=False)
            env_config = EnvironmentConfig.load()
            if env_config.operate_password:
                # Set env vars for olas-operate-middleware to consume
                os.environ["OPERATE_PASSWORD"] = env_config.operate_password
                os.environ["ATTENDED"] = "false"
                return env_config.operate_password

        # Prompt for password
        ask_password_if_needed(self.operate)
        if not self.operate.password:
            raise Exception("Password could not be set for Operate.")

        # Persist password
        os.environ["OPERATE_PASSWORD"] = self.operate.password
        self.env_path.parent.mkdir(parents=True, exist_ok=True)
        set_key(str(self.env_path), "OPERATE_PASSWORD", os.environ["OPERATE_PASSWORD"])
        os.environ["ATTENDED"] = "false"
        return os.environ["OPERATE_PASSWORD"]

    def is_initialized(self) -> bool:
        """
        Check if operate directory exists and is initialized.

        :return: True if initialized, False otherwise
        """
        return self.operate_path.exists()
