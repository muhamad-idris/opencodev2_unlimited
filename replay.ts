// Replays the captured request body with freshly generated headers.
// Usage: bun run replay.ts [body.json] [directory]

import { postStream, projectID, requestHeaders, saveResult, sessionID, URL_ENDPOINT } from "./lib"

const dir = import.meta.dir
const bodyPath = Bun.argv[2] ?? `${dir}/captured-request.json`
const directory = Bun.argv[3] ?? process.cwd()

const body = await Bun.file(bodyPath).text()
const session = sessionID()
const headers = requestHeaders({ sessionID: session, projectID: projectID(directory) })

const result = await postStream(body, headers)
const base = await saveResult("replay", { url: URL_ENDPOINT, headers, body }, result)

console.error(`session: ${session}`)
console.error(`status:  ${result.status} ${result.statusText}`)
if (result.status === 200) {
  if (result.text) console.log(result.text)
  console.error(`\nfinish_reason: ${result.finishReason || "(none)"}`)
} else {
  console.error(result.text)
}
console.error(`saved: ${base}.result.json`)

if (result.status !== 200) process.exit(1)
