import { existsSync } from "node:fs"
import { join } from "node:path"

export type ChatOptions = {
  model: string
  prompt: string
  directory: string
  maxTokens?: number
  reasoningEffort?: "low" | "medium" | "high"
}

// The endpoint rejects requests without a system message that carries an
// environment block, so this small one is always included.
export function systemPrompt(directory: string): string {
  const repo = existsSync(join(directory, ".git"))
  return `You are an AI agent running in OpenCode, a coding agent harness. Help the user accomplish their goals using the tools you have available.

Here is some useful information about the environment you are running in:
<env>
  Working directory: ${directory}
  Workspace root folder: ${directory}
  Is directory a git repo: ${repo ? "yes" : "no"}
  Platform: ${process.platform}
</env>`
}

export function chatPayload({ model, prompt, directory, maxTokens = 32000, reasoningEffort = "high" }: ChatOptions) {
  return {
    model,
    max_tokens: maxTokens,
    reasoning_effort: reasoningEffort,
    messages: [
      { role: "system", content: systemPrompt(directory) },
      { role: "user", content: prompt },
    ],
    tools: [{ type: "function", function: { name: "read" } }],
    tool_choice: "auto",
    stream: true,
    stream_options: { include_usage: true },
  }
}
