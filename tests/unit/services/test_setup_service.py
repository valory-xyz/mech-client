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

"""Tests for setup service."""

import logging
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mech_client.services.setup_service import SetupService


class TestSetupServiceInitialization:
    """Tests for SetupService initialization."""

    @patch("mech_client.services.setup_service.OperateManager")
    def test_initialization(self, mock_operate_manager: MagicMock) -> None:
        """Test SetupService initialization."""
        # Setup
        chain_config = "gnosis"
        template_path = Path("/path/to/template.json")

        # Execute
        service = SetupService(chain_config, template_path)

        # Verify
        assert service.chain_config == chain_config
        assert service.template_path == template_path
        mock_operate_manager.assert_called_once()


class TestSetupMethod:
    """Tests for SetupService.setup method."""

    @patch("mech_client.services.setup_service.run_service")
    @patch("mech_client.services.setup_service.OperateManager")
    def test_setup_success_with_unattended_env_setup(
        self,
        mock_operate_manager: MagicMock,
        mock_run_service: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test setup configures unattended middleware env vars and calls run_service."""
        # Setup
        chain_config = "gnosis"
        template_path = Path("/path/to/template.json")

        monkeypatch.delenv("ATTENDED", raising=False)
        monkeypatch.delenv("GNOSIS_LEDGER_RPC", raising=False)
        monkeypatch.delenv("STAKING_PROGRAM", raising=False)

        mock_operate = MagicMock()
        mock_operate_manager.return_value.operate = mock_operate
        mock_operate_manager.return_value.get_password.return_value = "password"

        service = SetupService(chain_config, template_path)

        with patch.object(service, "_get_rpc_url", return_value="https://rpc.test"):
            # Execute
            service.setup()

        # Verify operate setup was called
        mock_operate.setup.assert_called_once()
        mock_operate_manager.return_value.get_password.assert_called_once()

        # Verify unattended env vars are set for middleware quickstart
        assert os.environ["ATTENDED"] == "false"
        assert os.environ["GNOSIS_LEDGER_RPC"] == "https://rpc.test"
        assert os.environ["STAKING_PROGRAM"] == "1"

        # Verify run_service was called
        mock_run_service.assert_called_once_with(
            operate=mock_operate,
            config_path=template_path,
            build_only=True,
            use_binary=True,
            skip_dependency_check=False,
        )

    @patch("mech_client.services.setup_service.run_service")
    @patch("mech_client.services.setup_service.OperateManager")
    def test_setup_raises_on_run_service_failure(
        self,
        mock_operate_manager: MagicMock,
        mock_run_service: MagicMock,
    ) -> None:
        """Test setup raises exception when run_service fails."""
        # Setup
        chain_config = "gnosis"
        template_path = Path("/path/to/template.json")

        mock_operate = MagicMock()
        mock_operate_manager.return_value.operate = mock_operate
        mock_operate_manager.return_value.get_password.return_value = "password"

        mock_run_service.side_effect = Exception("RPC error")

        service = SetupService(chain_config, template_path)

        # Execute & Verify
        with pytest.raises(Exception, match="RPC error"):
            service.setup()


class TestGetRpcUrl:
    """Tests for SetupService._get_rpc_url method."""

    @patch("mech_client.services.setup_service.get_mech_config")
    @patch("mech_client.services.setup_service.OperateManager")
    def test_get_rpc_url_uses_env_var(
        self,
        mock_operate_manager: MagicMock,
        mock_get_mech_config: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test _get_rpc_url uses MECHX_CHAIN_RPC environment variable."""
        # Setup
        chain_config = "gnosis"
        template_path = Path("/path/to/template.json")
        custom_rpc = "https://custom-rpc.com"

        monkeypatch.setenv("MECHX_CHAIN_RPC", custom_rpc)
        service = SetupService(chain_config, template_path)

        # Execute
        result = service._get_rpc_url()

        # Verify
        assert result == custom_rpc
        mock_get_mech_config.assert_not_called()

    @patch("mech_client.services.setup_service.get_mech_config")
    @patch("mech_client.services.setup_service.OperateManager")
    def test_get_rpc_url_falls_back_to_mechs_json(
        self,
        mock_operate_manager: MagicMock,
        mock_get_mech_config: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test _get_rpc_url falls back to mechs.json when env var not set."""
        # Setup
        chain_config = "gnosis"
        template_path = Path("/path/to/template.json")
        default_rpc = "https://default-rpc.com"

        monkeypatch.delenv("MECHX_CHAIN_RPC", raising=False)

        mock_mech_config = MagicMock()
        mock_mech_config.rpc_url = default_rpc
        mock_get_mech_config.return_value = mock_mech_config

        service = SetupService(chain_config, template_path)

        # Execute
        result = service._get_rpc_url()

        # Verify
        assert result == default_rpc
        mock_get_mech_config.assert_called_once_with("gnosis")


class TestDisplayWallets:
    """Tests for SetupService.display_wallets method."""

    @patch("mech_client.services.setup_service.OperateManager")
    def test_display_wallets_success(
        self,
        mock_operate_manager: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test display_wallets successfully extracts and displays wallet info."""
        mech_logger = logging.getLogger("mech_client")
        mech_logger.propagate = True
        caplog.set_level(logging.INFO)
        # Setup
        chain_config = "gnosis"
        template_path = Path("/path/to/template.json")

        # Mock wallet with ChainType enum key
        # The operate library uses ChainType enum objects as keys
        mock_chain_type = MagicMock()
        mock_chain_type.value = "gnosis"

        mock_wallet = MagicMock()
        mock_wallet.address = "0x1234"
        mock_wallet.safes = {mock_chain_type: "0x5678"}

        # Mock service
        mock_service = MagicMock()
        mock_service.agent_addresses = ["0xABCD"]
        mock_chain_data = MagicMock()
        mock_chain_data.multisig = "0xEFGH"
        mock_chain_data.token = 2651  # Service token ID for marketplace URL
        mock_service.chain_configs = {"gnosis": MagicMock(chain_data=mock_chain_data)}

        # Mock service manager
        mock_service_manager = MagicMock()
        mock_service_manager.json = [
            {"home_chain": "gnosis", "service_config_id": "test-id"}
        ]
        mock_service_manager.load.return_value = mock_service

        # Mock operate
        mock_operate = MagicMock()
        mock_operate.wallet_manager.load.return_value = mock_wallet
        mock_operate.service_manager.return_value = mock_service_manager
        mock_operate_manager.return_value.operate = mock_operate

        service = SetupService(chain_config, template_path)

        # Execute
        result = service.display_wallets()

        # Verify
        assert result is not None
        assert result["master_eoa"] == "0x1234"
        assert result["master_safe"] == "0x5678"
        assert result["agent_eoa"] == "0xABCD"
        assert result["agent_safe"] == "0xEFGH"

        # Verify marketplace URL is logged
        assert "Marketplace: https://marketplace.olas.network/gnosis/ai-agents/2651" in caplog.text
        mech_logger.propagate = False

    @patch("mech_client.services.setup_service.OperateManager")
    def test_display_wallets_with_undeployed_service(
        self,
        mock_operate_manager: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test display_wallets shows 'URL unknown' when service token is -1."""
        mech_logger = logging.getLogger("mech_client")
        mech_logger.propagate = True
        caplog.set_level(logging.INFO)
        # Setup
        chain_config = "gnosis"
        template_path = Path("/path/to/template.json")

        # Mock wallet with ChainType enum key
        mock_chain_type = MagicMock()
        mock_chain_type.value = "gnosis"

        mock_wallet = MagicMock()
        mock_wallet.address = "0x1234"
        mock_wallet.safes = {mock_chain_type: "0x5678"}

        # Mock service with token = -1 (not deployed on-chain yet)
        mock_service = MagicMock()
        mock_service.agent_addresses = ["0xABCD"]
        mock_chain_data = MagicMock()
        mock_chain_data.multisig = "0xEFGH"
        mock_chain_data.token = -1  # Service not deployed on-chain
        mock_service.chain_configs = {"gnosis": MagicMock(chain_data=mock_chain_data)}

        # Mock service manager
        mock_service_manager = MagicMock()
        mock_service_manager.json = [
            {"home_chain": "gnosis", "service_config_id": "test-id"}
        ]
        mock_service_manager.load.return_value = mock_service

        # Mock operate
        mock_operate = MagicMock()
        mock_operate.wallet_manager.load.return_value = mock_wallet
        mock_operate.service_manager.return_value = mock_service_manager
        mock_operate_manager.return_value.operate = mock_operate

        service = SetupService(chain_config, template_path)

        # Execute
        result = service.display_wallets()

        # Verify
        assert result is not None
        assert result["master_eoa"] == "0x1234"
        assert result["master_safe"] == "0x5678"
        assert result["agent_eoa"] == "0xABCD"
        assert result["agent_safe"] == "0xEFGH"

        # Verify "URL unknown" is logged
        assert "Marketplace: URL unknown" in caplog.text
        mech_logger.propagate = False

    @patch("mech_client.services.setup_service.OperateManager")
    def test_display_wallets_no_service_found(
        self,
        mock_operate_manager: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test display_wallets returns None when service not found."""
        mech_logger = logging.getLogger("mech_client")
        mech_logger.propagate = True
        caplog.set_level(logging.WARNING)
        # Setup
        chain_config = "gnosis"
        template_path = Path("/path/to/template.json")

        # Mock wallet
        mock_wallet = MagicMock()
        mock_wallet.address = "0x1234"
        mock_wallet.safes = {"gnosis": "0x5678"}

        # Mock service manager with no matching service
        mock_service_manager = MagicMock()
        mock_service_manager.json = [
            {"home_chain": "polygon", "service_config_id": "test-id"}
        ]

        # Mock operate
        mock_operate = MagicMock()
        mock_operate.wallet_manager.load.return_value = mock_wallet
        mock_operate.service_manager.return_value = mock_service_manager
        mock_operate_manager.return_value.operate = mock_operate

        service = SetupService(chain_config, template_path)

        # Execute
        result = service.display_wallets()

        # Verify
        assert result is None
        assert "Could not find service for gnosis" in caplog.text
        mech_logger.propagate = False
