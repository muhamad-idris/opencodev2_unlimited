// Prints the headers this client would send, decoded back to their inputs.
// Usage: bun run headers.ts [directory]

import { projectID, requestHeaders, sessionID } from "./lib"

const dir = Bun.argv[2] ?? process.cwd()
const session = sessionID()
const project = projectID(dir)
const headers = requestHeaders({ sessionID: session, projectID: project })

console.log(`directory: ${dir}`)
console.log(`projectID: ${project}  (sha1("directory:${dir}"))`)
console.log(`sessionID: ${session}`)

// decode: low 48 bits are the two's complement of (ms * 4096 + counter)
const tsHex = session.slice(4, 16)
const M = BigInt(1) << 48n
const low = (M - BigInt(`0x${tsHex}`) - 1n) % M
const k = (BigInt(Date.now()) * 4096n - low) / M
const r = low + k * M
const createdAt = new Date(Number(r / 4096n)).toISOString()
console.log(`session created (decoded): ${createdAt}`)
console.log()
for (const [k, v] of Object.entries(headers)) console.log(`${k}: ${v}`)
