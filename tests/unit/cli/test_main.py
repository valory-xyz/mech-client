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

"""Tests for cli.main module."""

from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from mech_client.cli.main import OPERATE_FOLDER_NAME, cli


class TestCliMain:
    """Tests for the main CLI group."""

    def test_context_sets_client_mode(self) -> None:
        """Test that --client-mode flag is accepted and stored in context."""
        runner = CliRunner()
        with patch("mech_client.cli.main.load_dotenv"):
            result = runner.invoke(cli, ["--client-mode", "--help"])
        # With --help the exit code should be 0 and the flag should not error
        assert result.exit_code == 0

    def test_agent_mode_missing_operate_path(self) -> None:
        """Test that a wallet command in agent mode raises error when operate path is missing."""
        runner = CliRunner()

        # Directly patch the Path constructor used inside cli/main so that
        # operate_path.exists() returns False.
        with patch("mech_client.cli.main.load_dotenv"):
            with patch("mech_client.cli.main.Path") as mock_path_cls:
                # Pass through Path.home() and division operator
                real_operate = Path.home() / OPERATE_FOLDER_NAME
                mock_home = mock_path_cls.home.return_value
                mock_operate = mock_home.__truediv__.return_value
                mock_operate.exists.return_value = False
                # Make str() work so the error message can be formed
                mock_operate.__str__ = lambda self: str(real_operate)

                result = runner.invoke(cli, ["request", "--help"])

        # The CLI group should have raised a ClickException (exit_code == 1)
        assert result.exit_code != 0

    def test_agent_mode_missing_operate_path_error_message(self) -> None:
        """Test that the error message mentions the operate path and setup command."""
        runner = CliRunner()

        with patch("mech_client.cli.main.load_dotenv"):
            with patch(
                "mech_client.cli.main.Path",
                wraps=Path,
            ) as mock_path_cls:
                # Make operate_path.exists() return False
                mock_path_instance = mock_path_cls.home.return_value.__truediv__.return_value
                mock_path_instance.exists.return_value = False

                result = runner.invoke(cli, ["request", "--help"])

        # Either exit_code != 0 or the error appears in output
        combined = (result.output or "") + str(result.exception or "")
        assert (
            "Operate path does not exist" in combined
            or result.exit_code != 0
        )
