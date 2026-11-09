# Bun client for opencode.ai inference

Sends OpenCode inference requests without a proxy, using Bun 1.4.4 (the version
embedded in the `opencode` binary). Headers are generated locally; the payload is
short.

## Why Bun

The `opencode` binary embeds Bun 1.4.4 and its TLS stack (BoringSSL). A capture of
a real run (`/tmp/opencode/hello.pcap`) shows the ClientHello for `opencode.ai`:

- 17 cipher suites, 14 extensions, identical order
- groups `0x11ec` (X25519MLKEM768), `0x001d`, `0x0017`, `0x0018`
- ALPN `http/1.1` only
- JA3 hash `ae5f2d34331c18f27df379f7d4b72e35`

Bun 1.4.4 reproduces this handshake. curl (OpenSSL) does not and gets 429.
Reqable also replaces the handshake, which is why proxied runs failed.

## Header generation

| Header | Source |
|---|---|
| `authorization` | `Bearer public` unless `OPENCODE_API_KEY` or config overrides (`chunk___.js`) |
| `content-type` | `application/json` |
| `user-agent` | `opencode/<channel>/<version>/<client>` → `opencode/latest/2.2.5/cli` (`chunk-jzwck6cd.js`) |
| `b3` | `<traceId>-<spanId>-<sampled>-<parentSpanId>` (`chunk-gyfgy5hz.js`) |
| `traceparent` | `00-<traceId>-<spanId>-01` (`chunk-gyfgy5hz.js`) |
| `x-opencode-client` | `cli` |
| `x-opencode-project` | `sha1("directory:" + canonicalDir)` (`chunk-df6t5644.js`) |
| `x-opencode-session`, `x-opencode-session-id`, `x-session-affinity`, `x-session-id` | the session ID |

### Project ID

`sha1("directory:" + canonicalDirectory)`. For
`/home/tamsis/program/opencodev2` this is
`428e8b1e2efa9de2bb5f90823f73be04cd927c79`, matching the captured header.

### Session ID

`ses_` plus 26 characters (`chunk-6hrh8k09/chunk_Kj.js`):

```
r      = BigInt(ms) * 4096n + counter      // counter resets each ms, starts at 1
a      = ~r                                // BigInt bitwise NOT, two's complement
prefix = 12 hex chars of the low 48 bits of a
suffix = 14 chars, each randomByte % 62 over "0-9A-Za-z"
id     = "ses_" + prefix + suffix
```

The 12-hex prefix decodes back to the creation timestamp. IDs with a garbage
prefix are rejected, which is why fully random IDs returned 429.

### Trace IDs

32 hex chars for the trace and 16 for the span, built from `Math.random()`
32-bit draws (8 hex chars per draw) in `chunk-frb7cpd2.js`. They are new for each
request.

## Payload

The short payload works, but the endpoint rejects requests without a usable
system message. A minimal system prompt containing an environment block is
enough:

```
You are an AI agent running in OpenCode, a coding agent harness. ...

Here is some useful information about the environment you are running in:
<env>
  Working directory: <dir>
  Workspace root folder: <dir>
  Is directory a git repo: <yes|no>
  Platform: <platform>
</env>
```

`payload.ts` generates this. A payload without it, or with an empty `<env></env>`,
returns 429 `FreeUsageLimitError`.

Working shape:

```json
{
  "model": "big-pickle",
  "max_tokens": 32000,
  "reasoning_effort": "high",
  "messages": [
    { "role": "system", "content": "<env block>" },
    { "role": "user", "content": "hai opencode" }
  ],
  "tools": [{ "type": "function", "function": { "name": "read" } }],
  "tool_choice": "auto",
  "stream": true,
  "stream_options": { "include_usage": true }
}
```

## Files

- `lib.ts` — header generation and request/response helpers
- `payload.ts` — builds the short chat payload with the generated system prompt
- `ask.ts` — sends a prompt
- `replay.ts` — replays a saved full request body
- `headers.ts` — prints generated headers and decodes the session timestamp
- `captured-request.json` — body from a real OpenCode request (reference)
- `results/` — one `.request.json` and one `.result.json` per run

## Usage

Bun is installed at `~/.local/bin/bun` (version 1.4.4, on `PATH`).

```sh
bun run headers.ts /path/to/project        # inspect generated headers
bun run ask.ts "hai opencode"              # default model big-pickle
bun run ask.ts "hai opencode" nemotron-3.5-super-vl-free
bun run replay.ts                          # replay the captured full body
```

## Python port

`lib.py`, `payload.py`, `ask.py`, `replay.py`, and `headers.py` mirror the
TypeScript files. `tls.py` holds the fingerprint and drives `curl_cffi`
(BoringSSL) with a custom JA3, the exact signature-algorithm order, and two
extension switches, so the ClientHello matches Bun 1.4.4.

```sh
pip install -r requirements.txt   # curl_cffi==0.17.0

python headers.py /path/to/project
python ask.py "hai opencode"
python ask.py "hai opencode" nemotron-3.5-super-vl-free
python replay.py
```

Verified against `opencode.ai` with the same headers and payload: `200 OK`.
`tls.py` targets the fresh-connection JA3 `1523504b38f0fae0d881d4b6554aac1b`;
the capture's `ae5f2d...` additionally contains the `pre_shared_key` extension
from a resumed session.

## Notes

The free tier limit is shared across all free models, not per model. When it is
exhausted, every free model returns `429 FreeUsageLimitError` with the same
`retry-after` (about 17 hours in testing), and each new request nudges that
window forward. The real CLI behaves the same way:

```
$ ~/.opencode/bin/opencode run --model opencode/big-pickle "hi"
Error: Free usage limit reached. Connect a provider or subscribe to OpenCode Go...
```

So this is not a payload or header issue. `ask.ts` prints a short notice (with
the reset time) instead of the raw gateway JSON; pass `--verbose` to see the
raw body. Set `OPENCODE_API_KEY` or use another provider to continue before the
window resets.

Keep `opencode.ai` out of the Reqable proxy. The capture plugin logs requests
from inside OpenCode without one.
