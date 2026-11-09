"""Header generation and request/response helpers, mirrored from lib.ts.

Project ID : sha1("directory:" + canonicalDirectory)
Session ID : "ses_" + 12 hex from two's-complement(~((now * 4096) + counter))
             followed by 14 chars from a 62-char alphabet
Trace IDs  : 32/16 hex chars built from 32-bit random draws
b3         : "<traceId>-<spanId>-<sampled>-<parentSpanId>"
traceparent: "00-<traceId>-<spanId>-01"
API key    : "public" unless OPENCODE_API_KEY overrides
User-Agent : "opencode/<channel>/<version>/<client>"
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from curl_cffi import requests

from tls import CURL_OPTIONS, EXTRA_FP, JA3

URL_ENDPOINT = "https://opencode.ai/inference/openai/v1/chat/completions"
RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")

VERSION = "2.2.5"
CHANNEL = "latest"
CLIENT_NAME = "cli"

ALPHABET_62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

_last_ms = 0
_counter = 0


def _hex8() -> str:
    return format(secrets.randbits(32), "08x")


def trace_id() -> str:
    return _hex8() + _hex8() + _hex8() + _hex8()


def span_id() -> str:
    return _hex8() + _hex8()


def session_id(now: Optional[int] = None) -> str:
    """opencode's ascending ID: monotonic, timestamp-prefixed, local."""
    global _last_ms, _counter
    if now is None:
        now = int(time.time() * 1000)
    if now != _last_ms:
        _last_ms = now
        _counter = 0
    _counter += 1
    r = now * 4096 + _counter
    low = (~r) & 0xFFFFFFFFFFFF
    ts_hex = low.to_bytes(6, "big").hex()
    rand = "".join(ALPHABET_62[b % 62] for b in secrets.token_bytes(14))
    return f"ses_{ts_hex}{rand}"


def project_id(directory: Optional[str] = None) -> str:
    directory = directory or os.getcwd()
    try:
        if os.path.exists(directory):
            directory = os.path.realpath(directory)
    except OSError:
        pass
    return hashlib.sha1(f"directory:{directory}".encode("utf-8")).hexdigest()


def request_headers(session_id: str, project_id: str) -> Dict[str, str]:
    trace = trace_id()
    span = span_id()
    parent = span_id()

    return {
        "authorization": f"Bearer {os.environ.get('OPENCODE_API_KEY', 'public')}",
        "content-type": "application/json",
        "user-agent": f"opencode/{CHANNEL}/{VERSION}/{CLIENT_NAME}",
        "b3": f"{trace}-{span}-1-{parent}",
        "traceparent": f"00-{trace}-{span}-01",
        "x-opencode-client": CLIENT_NAME,
        "x-opencode-project": project_id,
        "x-opencode-session": session_id,
        "x-opencode-session-id": session_id,
        "x-session-affinity": session_id,
        "x-session-id": session_id,
    }


def parse_api_error(raw: str) -> Optional[Dict[str, str]]:
    try:
        parsed = json.loads(raw)
        error = parsed.get("error") if isinstance(parsed, dict) else None
        if isinstance(error, dict) and isinstance(error.get("type"), str):
            return {"type": error["type"], "message": str(error.get("message", ""))}
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def format_duration(seconds: float) -> str:
    s = max(0, int(seconds))
    h = s // 3600
    m = (s % 3600) // 60
    if h > 0:
        return f"{h}h {m}m"
    if m > 0:
        return f"{m}m"
    return f"{s}s"


def quota_reset(headers: Dict[str, str]) -> Optional[str]:
    try:
        seconds = float(headers.get("retry-after"))
    except (TypeError, ValueError):
        return None
    if not math.isfinite(seconds) or seconds <= 0:
        return None
    at = datetime.now().astimezone() + timedelta(seconds=seconds)
    clock = at.strftime("%a, %H:%M")
    return f"{format_duration(seconds)} (around {clock})"


def post_stream(body: str, headers: Dict[str, str]) -> Dict[str, Any]:
    response = requests.post(
        URL_ENDPOINT,
        headers=headers,
        data=body.encode("utf-8"),
        ja3=JA3,
        extra_fp=EXTRA_FP,
        http_version="v1",
        default_headers=False,
        timeout=300,
        curl_options=CURL_OPTIONS,
    )
    raw = response.content.decode("utf-8", "replace")

    text = ""
    reasoning = ""
    finish_reason = ""
    usage: Any = None

    for line in raw.split("\n"):
        if not line.startswith("data: "):
            continue
        data = line[6:]
        if data == "[DONE]":
            break
        try:
            chunk = json.loads(data)
        except json.JSONDecodeError:
            continue
        choices = chunk.get("choices") or []
        choice = choices[0] if choices else None
        if chunk.get("usage"):
            usage = chunk["usage"]
        if not choice:
            continue
        delta = choice.get("delta") or {}
        reasoning += delta.get("reasoning_content") or ""
        text += delta.get("content") or ""
        if choice.get("finish_reason"):
            finish_reason = choice["finish_reason"]

    result: Dict[str, Any] = {
        "status": response.status_code,
        "statusText": getattr(response, "reason", ""),
        "headers": {k.lower(): v for k, v in response.headers.items()},
        "text": text,
        "reasoning": reasoning,
        "finishReason": finish_reason,
        "usage": usage,
        "rawBytes": len(raw),
    }
    if response.status_code != 200:
        result["raw"] = raw
        result["error"] = parse_api_error(raw)
    return result


def _iso_stamp() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def save_result(
    kind: str,
    request: Dict[str, Any],
    result: Dict[str, Any],
) -> str:
    os.makedirs(RESULTS_DIR, exist_ok=True)
    stamp = _iso_stamp().replace(":", "-").replace(".", "-")
    base = os.path.join(RESULTS_DIR, f"{stamp}-{kind}")

    with open(f"{base}.request.json", "w", encoding="utf-8") as handle:
        json.dump(request, handle, indent=2, ensure_ascii=False)
    with open(f"{base}.result.json", "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, ensure_ascii=False)

    return base
