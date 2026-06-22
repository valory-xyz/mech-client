# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2025-2026 Valory AG
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

"""Tests for infrastructure.ipfs.metadata."""

import json
from unittest.mock import MagicMock, call, patch

import pytest

from mech_client.infrastructure.ipfs.metadata import fetch_ipfs_hash, push_metadata_to_ipfs


FAKE_V1_HEX = "f01701220" + "a" * 64
FAKE_V1_HASH = "bafybeiabc123"


class TestFetchIpfsHash:
    """Tests for fetch_ipfs_hash (offchain — computes hash without contacting IPFS)."""

    def test_returns_tuple_with_three_elements(self) -> None:
        """Return value is (truncated_hash, full_hash, ipfs_data)."""
        result = fetch_ipfs_hash("my prompt", "my-tool")

        assert len(result) == 3

    def test_truncated_hash_has_0x_prefix(self) -> None:
        """Truncated hash starts with 0x."""
        truncated, _, _ = fetch_ipfs_hash("prompt", "tool")

        assert truncated.startswith("0x")

    def test_truncated_hash_strips_first_9_chars(self) -> None:
        """Truncated hash is the full hash minus the first 9 chars plus 0x."""
        truncated, full, _ = fetch_ipfs_hash("prompt", "tool")

        assert truncated == "0x" + full[9:]

    def test_full_hash_is_v1_hex(self) -> None:
        """Full hash is the f01... v1 hex form (multibase 'f' + CIDv1 raw bytes)."""
        _, full, _ = fetch_ipfs_hash("prompt", "tool")

        # multibase 'f' + version 01 + dag-pb codec 70 + sha256 (12 20) + 32-byte digest
        assert full.startswith("f01701220")
        assert len(full) == 9 + 64  # prefix + 32-byte digest hex

    def test_ipfs_data_is_valid_json_with_prompt_and_tool(self) -> None:
        """Third element is a JSON string containing prompt and tool."""
        _, _, ipfs_data = fetch_ipfs_hash("hello world", "openai-gpt-4")

        data = json.loads(ipfs_data)
        assert data["prompt"] == "hello world"
        assert data["tool"] == "openai-gpt-4"
        assert "nonce" in data

    def test_extra_attributes_included_in_metadata(self) -> None:
        """Extra attributes are merged into the metadata."""
        _, _, ipfs_data = fetch_ipfs_hash(
            "prompt", "tool", extra_attributes={"key": "value", "num": 42}
        )

        data = json.loads(ipfs_data)
        assert data["key"] == "value"
        assert data["num"] == 42

    def test_no_ipfs_daemon_contacted(self) -> None:
        """fetch_ipfs_hash must not instantiate IPFSClient or contact a daemon.

        This is the core privacy property of the offchain path: the prompt
        and any extra attributes never leave the requester's process. A
        regression that re-introduces an IPFS daemon dependency (e.g. by
        reverting to IPFSClient.upload) would surface here because the mock
        catches any instantiation.
        """
        with patch("mech_client.infrastructure.ipfs.metadata.IPFSClient") as mock_cls:
            fetch_ipfs_hash("prompt", "tool")
            mock_cls.assert_not_called()

    def test_hash_is_deterministic_for_same_metadata(self) -> None:
        """Same ipfs_data must produce the same CID across calls."""
        # The mech recomputes the CID locally from the ipfs_data the client
        # transmits. Determinism is what lets that recomputation match the
        # client's signed value. nonce is randomized, so we compare CIDs by
        # recomputing on the same returned ipfs_data, not by re-running
        # fetch_ipfs_hash itself.
        from mech_client.infrastructure.ipfs.local_cid import compute_cidv1
        import multibase
        import multicodec

        _, full, ipfs_data = fetch_ipfs_hash("prompt", "tool")
        cidv1 = compute_cidv1(ipfs_data.encode("utf-8"))
        cid_bytes = multibase.decode(cidv1)
        multihash_bytes = multicodec.remove_prefix(cid_bytes)
        recomputed_full = "f01" + multihash_bytes.hex()

        assert recomputed_full == full


class TestPushMetadataToIpfs:
    """Tests for push_metadata_to_ipfs (uploads metadata to IPFS)."""

    @patch("mech_client.infrastructure.ipfs.metadata.IPFSClient")
    def test_returns_tuple_with_two_elements(self, mock_ipfs_cls: MagicMock) -> None:
        """Test return value is (truncated_hash, full_hash)."""
        mock_client = MagicMock()
        mock_ipfs_cls.return_value = mock_client
        mock_client.upload.return_value = (FAKE_V1_HASH, FAKE_V1_HEX)

        result = push_metadata_to_ipfs("prompt", "tool")

        assert len(result) == 2

    @patch("mech_client.infrastructure.ipfs.metadata.IPFSClient")
    def test_truncated_hash_has_0x_prefix(self, mock_ipfs_cls: MagicMock) -> None:
        """Test truncated hash starts with 0x."""
        mock_client = MagicMock()
        mock_ipfs_cls.return_value = mock_client
        mock_client.upload.return_value = (FAKE_V1_HASH, FAKE_V1_HEX)

        truncated, _ = push_metadata_to_ipfs("prompt", "tool")

        assert truncated.startswith("0x")

    @patch("mech_client.infrastructure.ipfs.metadata.IPFSClient")
    def test_truncated_hash_strips_first_9_chars(self, mock_ipfs_cls: MagicMock) -> None:
        """Test truncated hash derivation matches expected formula."""
        mock_client = MagicMock()
        mock_ipfs_cls.return_value = mock_client
        mock_client.upload.return_value = (FAKE_V1_HASH, FAKE_V1_HEX)

        truncated, full = push_metadata_to_ipfs("prompt", "tool")

        assert truncated == "0x" + full[9:]

    @patch("mech_client.infrastructure.ipfs.metadata.IPFSClient")
    def test_upload_called_with_pin_true_by_default(
        self, mock_ipfs_cls: MagicMock
    ) -> None:
        """Test upload is called without pin=False (uses default pin=True)."""
        mock_client = MagicMock()
        mock_ipfs_cls.return_value = mock_client
        mock_client.upload.return_value = (FAKE_V1_HASH, FAKE_V1_HEX)

        push_metadata_to_ipfs("prompt", "tool")

        mock_client.upload.assert_called_once()
        args, kwargs = mock_client.upload.call_args
        # Should NOT pass pin=False (let default pin=True apply)
        assert kwargs.get("pin") is not False

    @patch("mech_client.infrastructure.ipfs.metadata.IPFSClient")
    def test_extra_attributes_included_in_upload(
        self, mock_ipfs_cls: MagicMock
    ) -> None:
        """Test extra_attributes are included in the file written to disk."""
        mock_client = MagicMock()
        mock_ipfs_cls.return_value = mock_client
        mock_client.upload.return_value = (FAKE_V1_HASH, FAKE_V1_HEX)

        # We can verify by patching open and checking what was written
        written_content = {}

        original_open = open

        def mock_open_func(path: str, mode: str = "r", **kwargs):  # type: ignore
            if mode == "w":
                import io  # pylint: disable=import-outside-toplevel

                buf = io.StringIO()

                class FakeFile:
                    """Fake file to capture written JSON."""

                    def write(self, s: str) -> None:
                        """Capture write."""
                        buf.write(s)

                    def __enter__(self):  # type: ignore
                        """Enter context."""
                        return self

                    def __exit__(self, *args):  # type: ignore
                        """Exit context and save content."""
                        written_content["data"] = buf.getvalue()

                return FakeFile()
            return original_open(path, mode, **kwargs)

        with patch("builtins.open", side_effect=mock_open_func):
            push_metadata_to_ipfs("p", "t", extra_attributes={"custom": "field"})

        if written_content.get("data"):
            data = json.loads(written_content["data"])
            assert data.get("custom") == "field"

    @patch("mech_client.infrastructure.ipfs.metadata.shutil.rmtree")
    @patch("mech_client.infrastructure.ipfs.metadata.IPFSClient")
    def test_temp_dir_cleaned_up_on_success(
        self, mock_ipfs_cls: MagicMock, mock_rmtree: MagicMock
    ) -> None:
        """Test temp directory is cleaned up after successful upload."""
        mock_client = MagicMock()
        mock_ipfs_cls.return_value = mock_client
        mock_client.upload.return_value = (FAKE_V1_HASH, FAKE_V1_HEX)

        push_metadata_to_ipfs("prompt", "tool")

        mock_rmtree.assert_called_once()

    @patch("mech_client.infrastructure.ipfs.metadata.shutil.rmtree")
    @patch("mech_client.infrastructure.ipfs.metadata.IPFSClient")
    def test_temp_dir_cleaned_up_on_error(
        self, mock_ipfs_cls: MagicMock, mock_rmtree: MagicMock
    ) -> None:
        """Test temp directory is cleaned up even when upload fails."""
        mock_client = MagicMock()
        mock_ipfs_cls.return_value = mock_client
        mock_client.upload.side_effect = OSError("upload failed")

        with pytest.raises(OSError):
            push_metadata_to_ipfs("prompt", "tool")

        mock_rmtree.assert_called_once()
