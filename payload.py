"""Builds the short chat payload with the generated system prompt."""

from __future__ import annotations

import os
import sys
from typing import Any, Dict


def system_prompt(directory: str) -> str:
    repo = os.path.exists(os.path.join(directory, ".git"))
    return f"""You are an AI agent running in OpenCode, a coding agent harness. Help the user accomplish their goals using the tools you have available.

Here is some useful information about the environment you are running in:
<env>
  Working directory: {directory}
  Workspace root folder: {directory}
  Is directory a git repo: {"yes" if repo else "no"}
  Platform: {sys.platform}
</env>"""


def chat_payload(
    model: str,
    prompt: str,
    directory: str,
    max_tokens: int = 32000,
    reasoning_effort: str = "high",
) -> Dict[str, Any]:
    return {
        "model": model,
        "max_tokens": max_tokens,
        "reasoning_effort": reasoning_effort,
        "messages": [
            {"role": "system", "content": system_prompt(directory)},
            {"role": "user", "content": prompt},
        ],
        "tools": [{"type": "function", "function": {"name": "read"}}],
        "tool_choice": "auto",
        "stream": True,
        "stream_options": {"include_usage": True},
    }
