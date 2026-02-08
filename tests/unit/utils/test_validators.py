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

"""Tests for utils.validators module."""

import pytest

from mech_client.infrastructure.config import PaymentType
from mech_client.utils.errors import ValidationError
from mech_client.utils.validators import (
    validate_amount,
    validate_batch_sizes_match,
    validate_ethereum_address,
    validate_extra_attributes,
    validate_ipfs_hash,
    validate_payment_type,
    validate_service_id,
    validate_timeout,
    validate_tool_id,
)


class TestValidateEthereumAddress:
    """Tests for validate_ethereum_address function."""

    def test_valid_address(self, valid_ethereum_address: str) -> None:
        """Test validation of valid Ethereum address."""
        result = validate_ethereum_address(valid_ethereum_address)
        assert result == valid_ethereum_address

    def test_empty_address_raises_error(self) -> None:
        """Test that empty address raises ValidationError."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_ethereum_address("")

    def test_zero_address_raises_error(self, zero_address: str) -> None:
        """Test that zero address raises ValidationError by default."""
        with pytest.raises(ValidationError, match="zero address"):
            validate_ethereum_address(zero_address)

    def test_zero_address_allowed_when_specified(
        self, zero_address: str
    ) -> None:
        """Test that zero address is allowed when allow_zero=True."""
        result = validate_ethereum_address(zero_address, allow_zero=True)
        assert result == zero_address

    def test_invalid_format_raises_error(self) -> None:
        """Test that invalid address format raises ValidationError."""
        with pytest.raises(ValidationError, match="Invalid Ethereum address"):
            validate_ethereum_address("not_an_address")

    def test_too_short_address_raises_error(self) -> None:
        """Test that address too short raises ValidationError."""
        with pytest.raises(ValidationError, match="Invalid Ethereum address"):
            validate_ethereum_address("0x123")


class TestValidateAmount:
    """Tests for validate_amount function."""

    def test_valid_amount(self) -> None:
        """Test validation of valid amount."""
        result = validate_amount(1000)
        assert result == 1000

    def test_amount_with_custom_min_value(self) -> None:
        """Test validation with custom min value."""
        result = validate_amount(100, min_value=50)
        assert result == 100

    def test_zero_amount_raises_error(self) -> None:
        """Test that zero amount raises ValidationError."""
        with pytest.raises(ValidationError, match="at least 1"):
            validate_amount(0)

    def test_negative_amount_raises_error(self) -> None:
        """Test that negative amount raises ValidationError."""
        with pytest.raises(ValidationError, match="at least 1"):
            validate_amount(-100)

    def test_non_integer_raises_error(self) -> None:
        """Test that non-integer type raises ValidationError."""
        with pytest.raises(ValidationError, match="must be an integer"):
            validate_amount("1000")  # type: ignore

    def test_float_raises_error(self) -> None:
        """Test that float type raises ValidationError."""
        with pytest.raises(ValidationError, match="must be an integer"):
            validate_amount(100.5)  # type: ignore


class TestValidateToolId:
    """Tests for validate_tool_id function."""

    def test_valid_tool_id(self) -> None:
        """Test validation of valid tool ID."""
        tool_id = "1-openai-gpt-4"
        result = validate_tool_id(tool_id)
        assert result == tool_id

    def test_tool_id_with_multiple_dashes(self) -> None:
        """Test validation of tool ID with multiple dashes."""
        tool_id = "123-tool-name-with-dashes"
        result = validate_tool_id(tool_id)
        assert result == tool_id

    def test_empty_tool_id_raises_error(self) -> None:
        """Test that empty tool ID raises ValidationError."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_tool_id("")

    def test_tool_id_without_dash_raises_error(self) -> None:
        """Test that tool ID without dash raises ValidationError."""
        with pytest.raises(ValidationError, match="Invalid tool ID format"):
            validate_tool_id("toolname")

    def test_invalid_service_id_raises_error(self) -> None:
        """Test that non-integer service ID raises ValidationError."""
        with pytest.raises(ValidationError, match="Invalid service ID"):
            validate_tool_id("abc-tool-name")

    def test_negative_service_id_raises_error(self) -> None:
        """Test that negative service ID raises ValidationError."""
        with pytest.raises(ValidationError, match="non-negative integer"):
            validate_tool_id("-1-tool-name")


class TestValidatePaymentType:
    """Tests for validate_payment_type function."""

    def test_valid_payment_type_native(self) -> None:
        """Test validation of NATIVE payment type."""
        result = validate_payment_type("NATIVE")
        assert result == PaymentType.NATIVE

    def test_valid_payment_type_token(self) -> None:
        """Test validation of OLAS_TOKEN payment type."""
        result = validate_payment_type("OLAS_TOKEN")
        assert result == PaymentType.OLAS_TOKEN

    def test_lowercase_payment_type(self) -> None:
        """Test validation accepts lowercase payment type."""
        result = validate_payment_type("native")
        assert result == PaymentType.NATIVE

    def test_invalid_payment_type_raises_error(self) -> None:
        """Test that invalid payment type raises ValidationError."""
        with pytest.raises(ValidationError, match="Invalid payment type"):
            validate_payment_type("INVALID")


class TestValidateServiceId:
    """Tests for validate_service_id function."""

    def test_valid_service_id(self) -> None:
        """Test validation of valid service ID."""
        result = validate_service_id(123)
        assert result == 123

    def test_zero_service_id(self) -> None:
        """Test validation of zero service ID."""
        result = validate_service_id(0)
        assert result == 0

    def test_negative_service_id_raises_error(self) -> None:
        """Test that negative service ID raises ValidationError."""
        with pytest.raises(ValidationError, match="non-negative"):
            validate_service_id(-1)

    def test_non_integer_raises_error(self) -> None:
        """Test that non-integer type raises ValidationError."""
        with pytest.raises(ValidationError, match="must be an integer"):
            validate_service_id("123")  # type: ignore


class TestValidateIpfsHash:
    """Tests for validate_ipfs_hash function."""

    def test_valid_ipfs_hash_cidv0(self, sample_ipfs_hash: str) -> None:
        """Test validation of valid CIDv0 IPFS hash."""
        result = validate_ipfs_hash(sample_ipfs_hash)
        assert result == sample_ipfs_hash

    def test_valid_ipfs_hash_cidv1(self) -> None:
        """Test validation of valid CIDv1 IPFS hash."""
        cidv1_hash = "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
        result = validate_ipfs_hash(cidv1_hash)
        assert result == cidv1_hash

    def test_valid_ipfs_hash_hex(self) -> None:
        """Test validation of valid hex IPFS hash."""
        hex_hash = "f01701220" + "a" * 64
        result = validate_ipfs_hash(hex_hash)
        assert result == hex_hash

    def test_empty_hash_raises_error(self) -> None:
        """Test that empty hash raises ValidationError."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_ipfs_hash("")

    def test_invalid_hash_format_raises_error(self) -> None:
        """Test that invalid hash format raises ValidationError."""
        with pytest.raises(ValidationError, match="Invalid IPFS hash"):
            validate_ipfs_hash("invalid_hash")


class TestValidateBatchSizesMatch:
    """Tests for validate_batch_sizes_match function."""

    def test_matching_sizes(self) -> None:
        """Test validation of matching batch sizes."""
        prompts = ["prompt1", "prompt2"]
        tools = ["tool1", "tool2"]
        # Should not raise
        validate_batch_sizes_match(prompts, tools)

    def test_empty_lists(self) -> None:
        """Test validation of empty lists."""
        validate_batch_sizes_match([], [])

    def test_mismatched_sizes_raises_error(self) -> None:
        """Test that mismatched sizes raise ValidationError."""
        prompts = ["prompt1", "prompt2"]
        tools = ["tool1"]
        with pytest.raises(ValidationError, match="must match"):
            validate_batch_sizes_match(prompts, tools)


class TestValidateTimeout:
    """Tests for validate_timeout function."""

    def test_valid_timeout(self) -> None:
        """Test validation of valid timeout."""
        result = validate_timeout(600.0)
        assert result == 600.0

    def test_none_returns_default(self) -> None:
        """Test that None returns default timeout."""
        result = validate_timeout(None)
        assert result == 900.0

    def test_integer_timeout(self) -> None:
        """Test validation of integer timeout."""
        result = validate_timeout(300)
        assert result == 300.0

    def test_zero_timeout_raises_error(self) -> None:
        """Test that zero timeout raises ValidationError."""
        with pytest.raises(ValidationError, match="must be positive"):
            validate_timeout(0)

    def test_negative_timeout_raises_error(self) -> None:
        """Test that negative timeout raises ValidationError."""
        with pytest.raises(ValidationError, match="must be positive"):
            validate_timeout(-100)

    def test_non_numeric_raises_error(self) -> None:
        """Test that non-numeric type raises ValidationError."""
        with pytest.raises(ValidationError, match="must be a number"):
            validate_timeout("300")  # type: ignore


class TestValidateExtraAttributes:
    """Tests for validate_extra_attributes function."""

    def test_valid_attributes(self) -> None:
        """Test validation of valid extra attributes."""
        attrs = {"key1": "value1", "key2": 123, "key3": True}
        result = validate_extra_attributes(attrs)
        assert result == attrs

    def test_empty_dict(self) -> None:
        """Test validation of empty dictionary."""
        result = validate_extra_attributes({})
        assert result == {}

    def test_non_dict_raises_error(self) -> None:
        """Test that non-dictionary type raises ValidationError."""
        with pytest.raises(ValidationError, match="must be a dictionary"):
            validate_extra_attributes("not_a_dict")  # type: ignore

    def test_non_string_key_raises_error(self) -> None:
        """Test that non-string key raises ValidationError."""
        with pytest.raises(ValidationError, match="key must be a string"):
            validate_extra_attributes({123: "value"})  # type: ignore

    def test_complex_value_raises_error(self) -> None:
        """Test that complex value type raises ValidationError."""
        with pytest.raises(
            ValidationError, match="must be a primitive type"
        ):
            validate_extra_attributes({"key": {"nested": "dict"}})
