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

from pathlib import Path
from typing import Optional

from operate.cli import OperateApp


OPERATE_FOLDER_NAME = ".operate_mech_client"


class OperateManager:
    """Manager for Operate middleware integration.

    Provides methods for setting up agent mode and accessing Operate services.
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

    def is_initialized(self) -> bool:
        """
        Check if operate directory exists and is initialized.

        :return: True if initialized, False otherwise
        """
        return self.operate_path.exists()
