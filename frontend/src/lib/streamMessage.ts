import type { SearchHit } from "@/client"
import { client } from "@/client/client.gen"

// What the server sends when a reply is complete (see `stream_turn` in the backend)
export type ChatDone = {
  sources: SearchHit[]
  fallback: boolean
  notice: string
  cited_ids: string[]
  invalid_citations: number[]
  uncited: boolean
}

export type ChatEvent =
  | { type: "token"; text: string }
  | { type: "done"; done: ChatDone }
  | { type: "error" }

// Thrown when the server refuses the request itself (403, 404, 409, 422...) or the
// network fails (status 0). The text of a server error is deliberately not kept: the
// screen shows its own messages.
export class ChatStreamError extends Error {
  status: number

  constructor(status: number) {
    super(`The reply could not be read (status ${status})`)
    this.name = "ChatStreamError"
    this.status = status
  }
}

// Splits "event: x\ndata: {...}" blocks. A block that is not a known event, or whose
// data is not valid JSON, is ignored instead of failing the whole reply.
export function parseBlock(block: string): ChatEvent | null {
  let name = ""
  const data: string[] = []
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) name = line.slice(6).trim()
    else if (line.startsWith("data:")) data.push(line.slice(5).trimStart())
  }
  if (!name) return null
  try {
    const payload = JSON.parse(data.join("\n") || "{}")
    if (name === "token" && typeof payload.text === "string") {
      return { type: "token", text: payload.text }
    }
    if (name === "done") return { type: "done", done: payload as ChatDone }
    if (name === "error") return { type: "error" }
  } catch {
    return null
  }
  return null
}

// The generated client cannot read a `text/event-stream` body and `EventSource` cannot
// POST, so the reply is read with `fetch`. This goes around axios on purpose: the app's
// global error handler would log the user out on a 403, which here only means "your
// access to this conversation was taken away".
export async function streamMessage(
  conversationId: string,
  text: string,
  onEvent: (event: ChatEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  let response: Response
  try {
    response = await fetch(
      `${client.getConfig().baseURL ?? ""}/api/v1/conversations/${conversationId}/messages`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("access_token") ?? ""}`,
        },
        body: JSON.stringify({ text }),
        signal,
      },
    )
  } catch {
    throw new ChatStreamError(0)
  }
  if (!response.ok || !response.body) {
    throw new ChatStreamError(response.status)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n")
      let boundary = buffer.indexOf("\n\n")
      while (boundary !== -1) {
        const event = parseBlock(buffer.slice(0, boundary))
        buffer = buffer.slice(boundary + 2)
        if (event) onEvent(event)
        boundary = buffer.indexOf("\n\n")
      }
    }
  } catch {
    throw new ChatStreamError(0)
  }
}
