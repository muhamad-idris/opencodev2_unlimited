"""Replays a captured request body with freshly generated headers.

Usage: python replay.py [body.json] [directory]
"""

from __future__ import annotations

import argparse
import os
import sys

from lib import (
    URL_ENDPOINT,
    post_stream,
    project_id,
    request_headers,
    save_result,
    session_id,
)


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(prog="replay.py")
    parser.add_argument("body", nargs="?", default=os.path.join(here, "captured-request.json"))
    parser.add_argument("directory", nargs="?", default=os.getcwd())
    args = parser.parse_args()

    with open(args.body, "r", encoding="utf-8") as handle:
        body = handle.read()

    session = session_id()
    headers = request_headers(session_id=session, project_id=project_id(args.directory))

    result = post_stream(body, headers)
    base = save_result(
        "replay",
        {"url": URL_ENDPOINT, "headers": headers, "body": body},
        result,
    )

    print(f"session: {session}", file=sys.stderr)
    print(f"status:  {result['status']} {result['statusText']}", file=sys.stderr)
    if result["status"] == 200:
        if result["text"]:
            print(result["text"])
        print(f"\nfinish_reason: {result['finishReason'] or '(none)'}", file=sys.stderr)
    else:
        print(result["text"], file=sys.stderr)
    print(f"saved: {base}.result.json", file=sys.stderr)

    return 0 if result["status"] == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
