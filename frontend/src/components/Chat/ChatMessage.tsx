import type { ReactNode } from "react"

import type { SearchHit } from "@/client"
import { cn } from "@/lib/utils"

export type ChatLine = {
  id: string
  role: "user" | "persona"
  text: string
  // Set when the reply is complete
  sources?: SearchHit[]
  uncited?: boolean
  // The user's message got no reply
  unanswered?: boolean
}

interface ChatMessageProps {
  line: ChatLine
}

const CITATION = /\[(\d+)\]/g

// A citation points at a source only if the server sent that source. Anything else
// ("[9]" with three sources) stays plain text, as the server reports it as invalid.
function withCitations(line: ChatLine): ReactNode[] {
  const sourceCount = line.sources?.length ?? 0
  const parts: ReactNode[] = []
  let last = 0
  for (const match of line.text.matchAll(CITATION)) {
    const number = Number(match[1])
    const start = match.index ?? 0
    parts.push(line.text.slice(last, start))
    if (number >= 1 && number <= sourceCount) {
      const targetId = `${line.id}-source-${number}`
      parts.push(
        <a
          key={`${start}-${number}`}
          href={`#${targetId}`}
          className="text-primary underline underline-offset-2"
          onClick={(event) => {
            event.preventDefault()
            const target = document.getElementById(targetId)
            target?.focus()
            target?.scrollIntoView({ block: "nearest" })
          }}
        >
          [{number}]
        </a>,
      )
    } else {
      parts.push(match[0])
    }
    last = start + match[0].length
  }
  parts.push(line.text.slice(last))
  return parts
}

const ChatMessage = ({ line }: ChatMessageProps) => {
  const isUser = line.role === "user"

  return (
    <div
      className={cn(
        "flex flex-col gap-1",
        isUser ? "items-end" : "items-start",
      )}
    >
      <div
        className={cn(
          "max-w-[85%] whitespace-pre-wrap rounded-lg px-3 py-2 text-sm",
          isUser ? "bg-primary text-primary-foreground" : "bg-muted",
        )}
      >
        {isUser ? line.text : withCitations(line)}
      </div>
      {line.unanswered && (
        <p className="text-xs text-muted-foreground">Not answered</p>
      )}
      {line.uncited && (
        <p className="text-xs text-muted-foreground">
          This reply is not backed by a memory.
        </p>
      )}
      {line.sources && line.sources.length > 0 && (
        <ol
          aria-label="Sources"
          className="max-w-[85%] list-decimal space-y-1 pl-5 text-xs text-muted-foreground"
        >
          {line.sources.map((source, index) => (
            <li
              key={source.item.id}
              id={`${line.id}-source-${index + 1}`}
              tabIndex={-1}
              className="rounded outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {source.item.content}
              <span className="block italic">From: {source.memory_title}</span>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}

export default ChatMessage
