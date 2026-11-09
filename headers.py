"""Prints the headers this client would send, decoded back to their inputs.

Usage: python headers.py [directory]
"""

from __future__ import annotations

import argparse
import os
import time
from datetime import datetime, timezone

from lib import project_id, request_headers, session_id


def _iso_utc(ms: int) -> str:
    dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def main() -> int:
    parser = argparse.ArgumentParser(prog="headers.py")
    parser.add_argument("directory", nargs="?", default=os.getcwd())
    args = parser.parse_args()

    directory = args.directory
    session = session_id()
    project = project_id(directory)
    headers = request_headers(session_id=session, project_id=project)

    print(f"directory: {directory}")
    print(f'projectID: {project}  (sha1("directory:{directory}"))')
    print(f"sessionID: {session}")

    # decode: low 48 bits are the two's complement of (ms * 4096 + counter)
    ts_hex = session[4:16]
    modulus = 1 << 48
    low = (modulus - int(ts_hex, 16) - 1) % modulus
    # Pick the multiple of M closest to now, so a same-millisecond decode does
    # not fall one period behind (the JS version relies on Date.now() moving).
    k = (int(time.time() * 1000) * 4096 - low + modulus // 2) // modulus
    r = low + k * modulus
    print(f"session created (decoded): {_iso_utc(r // 4096)}")
    print()
    for key, value in headers.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
