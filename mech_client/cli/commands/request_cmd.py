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

"""Request command for sending AI task requests to mechs."""

import asyncio
import os
from typing import Any, Dict, List, Optional

import click
from click import ClickException

from mech_client.cli.common import common_wallet_options, setup_wallet_command
from mech_client.cli.validators import validate_chain_config, validate_ethereum_address
from mech_client.services.marketplace_service import MarketplaceService
from mech_client.utils.errors.handlers import handle_cli_errors


@click.command()
@click.option(
    "--prompts",
    type=str,
    multiple=True,
    required=True,
    help="One or more prompts to send as AI task requests.",
)
@click.option(
    "--priority-mech",
    type=str,
    help="Priority mech address to use for the request (0x...).",
)
@click.option(
    "--use-prepaid",
    type=bool,
    help="Use prepaid balance instead of per-request payment.",
)
@click.option(
    "--use-offchain",
    type=bool,
    help="Use offchain mech (requires MECHX_MECH_OFFCHAIN_URL).",
)
@click.option(
    "--tools",
    type=str,
    multiple=True,
    help="One or more tool identifiers (must match number of prompts).",
)
@click.option(
    "--extra-attribute",
    type=str,
    multiple=True,
    help="Extra attribute (key=value) to be included in request metadata.",
    metavar="KEY=VALUE",
)
@click.option(
    "--retries",
    type=int,
    help="Number of retries for sending a transaction.",
)
@click.option(
    "--timeout",
    type=float,
    help="Timeout in seconds to wait for the transaction.",
)
@click.option(
    "--sleep",
    type=float,
    help="Sleep duration in seconds before retrying the transaction.",
)
@common_wallet_options
@click.pass_context
@handle_cli_errors
# pylint: disable=too-many-arguments,too-many-locals,too-many-statements,unused-argument
def request(
    ctx: click.Context,
    prompts: tuple,
    priority_mech: str,
    chain_config: str,
    use_prepaid: bool,
    use_offchain: bool,
    key: Optional[str],
    tools: Optional[tuple],
    extra_attribute: Optional[List[str]] = None,
    retries: Optional[int] = None,
    timeout: Optional[float] = None,
    sleep: Optional[float] = None,
) -> None:
    r"""Send an AI task request to a mech on-chain.

    Sends one or more prompts to AI mechs via the Mech Marketplace contract.
    Supports batch requests (multiple prompts/tools), various payment methods
    (native, token, prepaid, NVM subscription), and both on-chain and
    off-chain delivery.

    Examples:
      # Single request with native payment
      mechx request --prompts "Summarize this" --tools openai-gpt-4 \
        --chain-config gnosis

      # Batch request with prepaid balance
      mechx request --prompts "Prompt 1" --prompts "Prompt 2" \
        --tools tool1 --tools tool2 --use-prepaid --chain-config gnosis
    """
    # Validate chain config
    validated_chain = validate_chain_config(chain_config)

    # Parse extra attributes
    extra_attributes_dict: Dict[str, Any] = {}
    if extra_attribute:
        for pair in extra_attribute:
            if "=" not in pair:
                raise ClickException(
                    f"Invalid extra attribute format: {pair!r}\n"
                    f"Expected format: key=value"
                )
            k, v = pair.split("=", 1)
            extra_attributes_dict[k] = v

    # Process flags
    use_offchain = use_offchain or False
    use_prepaid = use_prepaid or use_offchain

    # Validate offchain URL if needed
    mech_offchain_url = os.getenv("MECHX_MECH_OFFCHAIN_URL")
    if use_offchain and not mech_offchain_url:
        raise ClickException(
            "MECHX_MECH_OFFCHAIN_URL is required when using "
            "--use-offchain.\n"
            "Set it to your offchain mech HTTP endpoint:\n"
            "  export MECHX_MECH_OFFCHAIN_URL='https://your-url'"
        )

    # Validate tools
    if not tools:
        raise ClickException(
            "Tools are required. Use --tools flag to specify one or " "more tools."
        )

    if len(prompts) != len(tools):
        raise ClickException(
            f"The number of prompts ({len(prompts)}) must match the "
            f"number of tools ({len(tools)})"
        )

    # Validate priority_mech address
    if priority_mech:
        validate_ethereum_address(priority_mech, "Priority mech address")

    # Setup wallet command (agent mode detection, key loading, etc.)
    wallet_ctx = setup_wallet_command(ctx, validated_chain, key)

    # Create marketplace service
    service = MarketplaceService(
        chain_config=validated_chain,
        agent_mode=wallet_ctx.agent_mode,
        crypto=wallet_ctx.crypto,
        safe_address=wallet_ctx.safe_address,
        ethereum_client=wallet_ctx.ethereum_client,
    )

    # Send request
    click.echo("\nSending marketplace request...")
    result = asyncio.run(
        service.send_request(
            prompts=prompts,
            tools=tools,  # type: ignore
            priority_mech=priority_mech,
            use_prepaid=use_prepaid,
            use_offchain=use_offchain,
            mech_offchain_url=mech_offchain_url,
            extra_attributes=extra_attributes_dict,
            timeout=timeout,
        )
    )

    # Display results
    click.echo(f"\n✓ Transaction hash: {result['tx_hash']}")
    click.echo(f"✓ Request IDs: {result['request_ids']}")
    if result.get("delivery_results"):
        click.echo("\n✓ Delivery results:")
        for request_id, data_url in result["delivery_results"].items():
            click.echo(f"  Request {request_id}: {data_url}")
