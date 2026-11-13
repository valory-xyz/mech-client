# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2026 Valory AG
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

"""The chat contract: messages in, completion and token usage out.

The prompt is an OpenAI-style ``messages`` list as JSON, and the delivery
carries the completion text plus token usage. The parse order is the
delivery result itself, then a ``response`` or ``result`` field, then
``content``, ``text`` or ``completion`` (or an OpenAI ``choices[0].message``).
A native tool call the model returns unrequested comes back as a fenced bash
block in the completion rather than being dropped.
"""

import json
from typing import Any, Dict, Optional, TypedDict

from mech_client.domain.delivery.models import DeliveryResult

TEXT_KEYS = ("content", "text", "completion")
WRAPPER_KEYS = ("response", "result")
USAGE_KEYS = ("prompt_tokens", "completion_tokens")


class ChatReport(TypedDict):
    """A chat delivery's completion, and the token usage the mech reported."""

    completion: str
    usage: Dict[str, int]


def is_chat_prompt(prompt: str) -> bool:
    """
    Whether a prompt is a chat: a non-empty JSON list of ``{role, ...}`` messages.

    :param prompt: The prompt string
    :return: True for a chat prompt
    """
    try:
        messages = json.loads(prompt)
    except (ValueError, RecursionError):  # deep nesting overflows the decoder
        return False
    return (
        isinstance(messages, list)
        and bool(messages)
        and all(isinstance(m, dict) and "role" in m for m in messages)
    )


def _parse(value: Any) -> Any:
    """Decode a JSON string, leaving anything else as it is.

    :param value: A delivery field
    :return: The decoded value, or the value itself
    """
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, RecursionError):  # an untrusted delivery: any depth
            return value
    return value


def _message(data: Any) -> Any:
    """Descend to the completion: response/result, then OpenAI choices.

    :param data: The delivered content
    :return: The message holding the completion
    """
    data = _parse(data)
    for key in WRAPPER_KEYS:
        if isinstance(data, dict) and key in data:
            data = _parse(data[key])
            break
    if isinstance(data, dict) and isinstance(data.get("choices"), list):
        choices = data["choices"]
        first = choices[0] if choices else None
        message = first.get("message") if isinstance(first, dict) else None
        if isinstance(message, dict):  # an untrusted delivery: any shape
            return {**data, **message}
    return data


def _tool_call_block(call: Any) -> str:
    """Render one native tool call as a fenced bash block.

    :param call: One entry of the message's ``tool_calls``
    :return: The fenced block
    """
    function = call.get("function") if isinstance(call, dict) else None
    function = function if isinstance(function, dict) else {}
    arguments = _parse(function.get("arguments", ""))
    if isinstance(arguments, dict) and isinstance(arguments.get("command"), str):
        body = arguments["command"]
    else:
        name = str(function.get("name") or "tool")
        rendered = arguments if isinstance(arguments, str) else json.dumps(arguments)
        body = f"{name} {rendered}"
    return f"```bash\n{body.strip()}\n```"


def chat_report(delivery: Any) -> Optional[ChatReport]:
    """
    Read the completion and usage out of a chat delivery.

    :param delivery: A :class:`DeliveryResult` from ``send_request``'s
        ``deliveries``, or its content
    :return: The report, or None when the delivery holds no completion
    """
    if isinstance(delivery, DeliveryResult):
        delivery = delivery.data
    message = _message(delivery)
    if isinstance(message, str):
        return {"completion": message, "usage": {}}
    if not isinstance(message, dict):
        return None
    text = next(
        (message[key] for key in TEXT_KEYS if isinstance(message.get(key), str)),
        None,
    )
    calls = message.get("tool_calls")
    blocks = [_tool_call_block(c) for c in calls] if isinstance(calls, list) else []
    if text is None and not blocks:
        return None
    completion = "\n\n".join(([text] if text else []) + blocks)
    usage = message.get("usage")
    return {
        "completion": completion,
        "usage": {
            key: int(usage[key])
            for key in USAGE_KEYS
            if isinstance(usage, dict) and isinstance(usage.get(key), int)
        },
    }
