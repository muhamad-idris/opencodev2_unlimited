"""Send a prompt with the Bun-compatible TLS fingerprint.

Usage: python ask.py "your prompt" [model] [directory] [--verbose]

When the shared free-tier limit is exhausted, this prints a short notice
instead of the raw gateway error. Pass --verbose to see the full response.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from lib import (
    URL_ENDPOINT,
    post_stream,
    project_id,
    quota_reset,
    request_headers,
    save_result,
    session_id,
)
from payload import chat_payload


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="ask.py",
        description="Send a prompt to opencode.ai with Bun's TLS fingerprint.",
    )
    parser.add_argument("prompt", nargs="?")
    parser.add_argument("model", nargs="?", default="big-pickle")
    parser.add_argument("directory", nargs="?", default=os.getcwd())
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    if not args.prompt:
        print(
            'usage: python ask.py "your prompt" [model] [directory] [--verbose]',
            file=sys.stderr,
        )
        return 2

    body = json.dumps(chat_payload(model=args.model, prompt=args.prompt, directory=args.directory))
    session = session_id()
    headers = request_headers(session_id=session, project_id=project_id(args.directory))

    result = post_stream(body, headers)
    base = save_result(
        "ask",
        {"url": URL_ENDPOINT, "headers": headers, "body": body},
        result,
    )

    print(f"model:   {args.model}", file=sys.stderr)
    print(f"session: {session}", file=sys.stderr)
    print(f"status:  {result['status']} {result['statusText']}", file=sys.stderr)

    if result["status"] == 200:
        if result["text"]:
            print(result["text"])
        print(f"\nfinish_reason: {result['finishReason'] or '(none)'}", file=sys.stderr)
    elif (result.get("error") or {}).get("type") == "FreeUsageLimitError":
        reset = quota_reset(result["headers"])
        print("", file=sys.stderr)
        if reset:
            print(f"free tier limit reached; it resets in {reset}.", file=sys.stderr)
        else:
            print("free tier limit reached.", file=sys.stderr)
        print(
            "further free requests only extend that window. Wait it out, set OPENCODE_API_KEY, or see https://opencode.ai/go",
            file=sys.stderr,
        )
        if args.verbose and result.get("raw"):
            print(f"\nraw: {result['raw']}", file=sys.stderr)
    else:
        error = result.get("error")
        detail = f"{error['type']}: {error['message']}" if error else result["text"]
        print("", file=sys.stderr)
        print(f"request failed{': ' + detail if detail else ''}", file=sys.stderr)
        if args.verbose and result.get("raw"):
            print(f"\nraw: {result['raw']}", file=sys.stderr)

    print(f"saved: {base}.result.json", file=sys.stderr)
    return 0 if result["status"] == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
