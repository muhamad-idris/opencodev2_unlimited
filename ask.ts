// Send a prompt with Bun 1.4.4 (same TLS stack as the opencode CLI).
// Headers and payload are generated locally. Results go to ./results.
//
// Usage: bun run ask.ts "your prompt" [model] [directory] [--verbose]
//
// When the shared free-tier limit is exhausted, this prints a short notice
// instead of the raw gateway error. Pass --verbose to see the full response.

import { postStream, projectID, quotaReset, requestHeaders, saveResult, sessionID, URL_ENDPOINT } from "./lib"
import { chatPayload } from "./payload"

const argv = Bun.argv.slice(2)
const verbose = argv.includes("--verbose") || argv.includes("-v")
const positional = argv.filter((arg) => !arg.startsWith("-"))

const prompt = positional[0]
const model = positional[1] ?? "big-pickle"
const directory = positional[2] ?? process.cwd()

if (!prompt || argv.includes("--help") || argv.includes("-h")) {
  console.error('usage: bun run ask.ts "your prompt" [model] [directory] [--verbose]')
  process.exit(prompt ? 0 : 2)
}

const body = JSON.stringify(chatPayload({ model, prompt, directory }))
const session = sessionID()
const headers = requestHeaders({ sessionID: session, projectID: projectID(directory) })

const result = await postStream(body, headers)
const base = await saveResult("ask", { url: URL_ENDPOINT, headers, body }, result)

console.error(`model:   ${model}`)
console.error(`session: ${session}`)
console.error(`status:  ${result.status} ${result.statusText}`)

if (result.status === 200) {
  if (result.text) console.log(result.text)
  console.error(`\nfinish_reason: ${result.finishReason || "(none)"}`)
} else if (result.error?.type === "FreeUsageLimitError") {
  const reset = quotaReset(result.headers)
  console.error("")
  console.error(
    reset
      ? `free tier limit reached; it resets in ${reset}.`
      : "free tier limit reached.",
  )
  console.error(
    "further free requests only extend that window. Wait it out, set OPENCODE_API_KEY, or see https://opencode.ai/go",
  )
  if (verbose && result.raw) console.error(`\nraw: ${result.raw}`)
} else {
  const detail = result.error ? `${result.error.type}: ${result.error.message}` : result.text
  console.error("")
  console.error(`request failed${detail ? `: ${detail}` : ""}`)
  if (verbose && result.raw) console.error(`\nraw: ${result.raw}`)
}

console.error(`saved: ${base}.result.json`)

if (result.status !== 200) process.exit(1)
