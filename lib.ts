// Header generation mirrored from the opencode binary (Bun 1.4.4 build).
//
// Project ID : sha1("directory:" + canonicalDirectory)      chunk-df6t5644.js
// Session ID : "ses_" + Kj(true)                            chunk-6hrh8k09/chunk_Kj.js
//              Kj: 12 hex from two's-complement(~((now * 4096) + counter))
//                  followed by 14 chars from a 62-char alphabet
// Trace IDs  : 32/16 hex chars built from Math.random() draws   chunk-frb7cpd2.js
// b3         : "<traceId>-<spanId>-<sampled>-<parentSpanId>"     chunk-gyfgy5hz.js
// traceparent: "00-<traceId>-<spanId>-01"                      chunk-gyfgy5hz.js
// API key    : "public" unless OPENCODE_API_KEY / config overrides  chunk___.js
// User-Agent : "opencode/<channel>/<version>/<client>"          chunk-jzwck6cd.js

import { createHash } from "node:crypto"
import { realpathSync } from "node:fs"
import { mkdir } from "node:fs/promises"

export const URL_ENDPOINT = "https://opencode.ai/inference/openai/v1/chat/completions"
export const RESULTS_DIR = `${import.meta.dir}/results`

export const VERSION = "2.2.5"
export const CHANNEL = "latest"
export const CLIENT_NAME = "cli"

const HEX = "0123456789abcdef"
const ALPHABET_62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

// Effect's ID generator: one 32-bit Math.random draw -> 8 hex chars.
const nextWord = () => (Math.random() * 4294967296) >>> 0
function hex8() {
  const word = nextWord()
  let out = ""
  for (let shift = 28; shift >= 0; shift -= 4) out += HEX[(word >>> shift) & 15]
  return out
}

export const traceID = () => hex8() + hex8() + hex8() + hex8()
export const spanID = () => hex8() + hex8()

let lastMs = 0
let counter = 0

// opencode's Kj(true): monotonic, timestamp-prefixed, locally generated.
export function sessionID(now = Date.now()) {
  if (now !== lastMs) {
    lastMs = now
    counter = 0
  }
  counter++
  const r = BigInt(now) * 4096n + BigInt(counter)
  const a = ~r // BigInt bitwise NOT
  let tsHex = ""
  for (let i = 0; i < 6; i++) {
    tsHex += Number((a >> BigInt(40 - 8 * i)) & 0xffn)
      .toString(16)
      .padStart(2, "0")
  }
  const bytes = crypto.getRandomValues(new Uint8Array(14))
  const rand = Array.from(bytes, (b) => ALPHABET_62[b % 62]).join("")
  return `ses_${tsHex}${rand}`
}

export function projectID(directory = process.cwd()) {
  let dir = directory
  try {
    dir = realpathSync(directory)
  } catch {
    // keep the given path when it cannot be resolved
  }
  return createHash("sha1").update(`directory:${dir}`).digest("hex")
}

export type HeaderOptions = {
  sessionID: string
  projectID: string
}

export function requestHeaders({ sessionID, projectID }: HeaderOptions): Record<string, string> {
  const trace = traceID()
  const span = spanID()
  const parent = spanID()

  return {
    authorization: `Bearer ${process.env.OPENCODE_API_KEY ?? "public"}`,
    "content-type": "application/json",
    "user-agent": `opencode/${CHANNEL}/${VERSION}/${CLIENT_NAME}`,
    b3: `${trace}-${span}-1-${parent}`,
    traceparent: `00-${trace}-${span}-01`,
    "x-opencode-client": CLIENT_NAME,
    "x-opencode-project": projectID,
    "x-opencode-session": sessionID,
    "x-opencode-session-id": sessionID,
    "x-session-affinity": sessionID,
    "x-session-id": sessionID,
  }
}

export type ApiError = {
  type: string
  message: string
}

export type StreamResult = {
  status: number
  statusText: string
  headers: Record<string, string>
  text: string
  reasoning: string
  finishReason: string
  usage: unknown
  rawBytes: number
  raw?: string
  error?: ApiError
}

function parseApiError(raw: string): ApiError | undefined {
  try {
    const parsed = JSON.parse(raw)
    const error = parsed?.error
    if (error && typeof error.type === "string") {
      return { type: error.type, message: String(error.message ?? "") }
    }
  } catch {
    // not a JSON error body
  }
  return undefined
}

// "17h 11m", "3m", "45s"
export function formatDuration(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  if (h > 0) return `${h}h ${m}m`
  if (m > 0) return `${m}m`
  return `${s}s`
}

// Human reminder for a retry-after header, in local time.
export function quotaReset(headers: Record<string, string>): string | undefined {
  const seconds = Number(headers["retry-after"])
  if (!Number.isFinite(seconds) || seconds <= 0) return undefined
  const at = new Date(Date.now() + seconds * 1000)
  const clock = at.toLocaleString(undefined, {
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
  })
  return `${formatDuration(seconds)} (around ${clock})`
}

export async function postStream(
  body: string,
  headers: Record<string, string>,
): Promise<StreamResult> {
  const res = await fetch(URL_ENDPOINT, { method: "POST", headers, body })
  const raw = await res.text()

  let text = ""
  let reasoning = ""
  let finishReason = ""
  let usage: unknown = null

  for (const line of raw.split("\n")) {
    if (!line.startsWith("data: ")) continue
    const data = line.slice(6)
    if (data === "[DONE]") break
    try {
      const chunk = JSON.parse(data)
      const choice = chunk.choices?.[0]
      if (chunk.usage) usage = chunk.usage
      if (!choice) continue
      reasoning += choice.delta?.reasoning_content ?? ""
      text += choice.delta?.content ?? ""
      if (choice.finish_reason) finishReason = choice.finish_reason
    } catch {
      // keep the raw stream for inspection
    }
  }

  return {
    status: res.status,
    statusText: res.statusText,
    headers: Object.fromEntries(res.headers.entries()),
    text,
    reasoning,
    finishReason,
    usage,
    rawBytes: raw.length,
    ...(res.status === 200 ? {} : { raw, error: parseApiError(raw) }),
  }
}

export async function saveResult(
  kind: string,
  request: { url: string; headers: Record<string, string>; body: string },
  result: StreamResult,
) {
  await mkdir(RESULTS_DIR, { recursive: true })
  const stamp = new Date().toISOString().replace(/[:.]/g, "-")
  const base = `${RESULTS_DIR}/${stamp}-${kind}`

  await Bun.write(`${base}.request.json`, JSON.stringify(request, null, 2))
  await Bun.write(`${base}.result.json`, JSON.stringify(result, null, 2))

  return base
}
