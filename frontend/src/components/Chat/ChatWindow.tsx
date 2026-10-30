import { zodResolver } from "@hookform/resolvers/zod"
import { useQuery } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import { AxiosError } from "axios"
import { useEffect, useRef, useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { ConversationsService, PersonsService } from "@/client"
import OfferMemory from "@/components/Offers/OfferMemory"
import { Alert, AlertDescription } from "@/components/ui/alert"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { LoadingButton } from "@/components/ui/loading-button"
import { Textarea } from "@/components/ui/textarea"
import { ChatStreamError, streamMessage } from "@/lib/streamMessage"
import ChatMessage, { type ChatLine } from "./ChatMessage"
import EndChat from "./EndChat"
import RecallPanel from "./RecallPanel"

const formSchema = z.object({
  text: z
    .string()
    .trim()
    .min(1, { message: "Write a message first" })
    .max(2000, { message: "A message can have at most 2000 characters" }),
})

type FormData = z.infer<typeof formSchema>

type Opened =
  | { kind: "opened"; conversationId: string; notice: string }
  | { kind: "denied" }
  | { kind: "notFound" }

// Why sending stopped for good
type Blocked = "denied" | "ended" | "notFound"

const BLOCKED_MESSAGES: Record<Blocked, string> = {
  denied: "You no longer have access to this conversation.",
  ended: "This conversation has ended.",
  notFound: "This conversation could not be found.",
}

const GENERIC_ERROR = "Something went wrong. Please try again."

interface ChatWindowProps {
  personId: string
}

const ChatWindow = ({ personId }: ChatWindowProps) => {
  const navigate = useNavigate()
  const [lines, setLines] = useState<ChatLine[]>([])
  const [sending, setSending] = useState(false)
  const [blocked, setBlocked] = useState<Blocked | null>(null)
  const [failure, setFailure] = useState<string | null>(null)
  const counter = useRef(0)
  const abort = useRef<AbortController | null>(null)
  // A ref, not the state: two quick submits can both read the same stale `sending`
  const inFlight = useRef(false)
  const logEnd = useRef<HTMLDivElement | null>(null)

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: { text: "" },
  })

  // One conversation per visit: StrictMode mounts twice, but equal query keys share
  // one request. A 403 or 404 becomes data because the app's global handler logs the
  // user out on any 403 from the generated client, and "no access" is not that.
  const opened = useQuery({
    queryKey: ["conversation", personId],
    queryFn: async (): Promise<Opened> => {
      try {
        const response = await ConversationsService.openConversation({
          path: { person_id: personId },
        })
        return {
          kind: "opened",
          conversationId: response.data.conversation_id,
          notice: response.data.notice,
        }
      } catch (error) {
        const status = error instanceof AxiosError ? error.response?.status : 0
        if (status === 403) return { kind: "denied" }
        if (status === 404) return { kind: "notFound" }
        throw error
      }
    },
    staleTime: Number.POSITIVE_INFINITY,
    gcTime: 0,
    retry: false,
    refetchOnMount: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })

  // Only the owner can read the person; anyone else just sees a general title
  const person = useQuery({
    queryKey: ["persons", personId],
    queryFn: async () => {
      try {
        return (await PersonsService.readPerson({ path: { id: personId } }))
          .data
      } catch {
        return null
      }
    },
    retry: false,
  })

  useEffect(() => {
    return () => abort.current?.abort()
  }, [])

  // biome-ignore lint/correctness/useExhaustiveDependencies: scroll whenever a line changes
  useEffect(() => {
    logEnd.current?.scrollIntoView?.({ block: "end" })
  }, [lines])

  const conversation = opened.data?.kind === "opened" ? opened.data : null
  const stopped = blocked !== null

  const send = async ({ text }: FormData) => {
    if (!conversation || inFlight.current || stopped) return
    inFlight.current = true
    const userId = `message-${++counter.current}`
    const replyId = `message-${++counter.current}`
    form.reset({ text: "" })
    setFailure(null)
    setLines((previous) => [
      ...previous,
      { id: userId, role: "user", text },
      { id: replyId, role: "persona", text: "" },
    ])
    setSending(true)

    const update = (id: string, change: (line: ChatLine) => ChatLine) =>
      setLines((previous) =>
        previous.map((line) => (line.id === id ? change(line) : line)),
      )

    let finished = false
    let failed = false
    abort.current = new AbortController()
    try {
      await streamMessage(
        conversation.conversationId,
        text,
        (event) => {
          if (event.type === "token") {
            update(replyId, (line) => ({
              ...line,
              text: line.text + event.text,
            }))
          } else if (event.type === "done") {
            finished = true
            update(replyId, (line) => ({
              ...line,
              sources: event.done.fallback ? undefined : event.done.sources,
              uncited: event.done.uncited && !event.done.fallback,
            }))
          } else {
            failed = true
          }
        },
        abort.current.signal,
      )
    } catch (error) {
      // Leaving the page aborts the request; there is nobody left to tell
      if (abort.current?.signal.aborted) return
      failed = true
      if (error instanceof ChatStreamError) {
        if (error.status === 403) setBlocked("denied")
        else if (error.status === 409) setBlocked("ended")
        else if (error.status === 404) setBlocked("notFound")
      }
    }

    if (failed || !finished) {
      // Drop the unfinished reply, keep the question and give the text back
      setLines((previous) =>
        previous
          .filter((line) => line.id !== replyId)
          .map((line) =>
            line.id === userId ? { ...line, unanswered: true } : line,
          ),
      )
      form.setValue("text", text)
      setFailure(GENERIC_ERROR)
    }
    inFlight.current = false
    setSending(false)
  }

  // Back to the input once it is enabled again: focusing it inside `send` would run
  // while the textarea is still disabled, and a keyboard user would lose their place
  const { setFocus } = form
  useEffect(() => {
    if (!sending && blocked === null) setFocus("text")
  }, [sending, blocked, setFocus])

  const heading = person.data
    ? `Talk with ${person.data.name}`
    : "Talk with the persona"

  if (opened.isPending) {
    return <p className="text-muted-foreground">Opening the conversation…</p>
  }

  if (opened.isError) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{GENERIC_ERROR}</AlertDescription>
      </Alert>
    )
  }

  if (!conversation) {
    return (
      <Alert variant="destructive">
        <AlertDescription>
          {opened.data?.kind === "notFound"
            ? "This person could not be found."
            : "You don't have access to talk with this person."}
        </AlertDescription>
      </Alert>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{heading}</h1>
          <p className="text-muted-foreground">
            Ask about what the family remembers
          </p>
        </div>
        <div className="flex items-center gap-2">
          {blocked !== "denied" && blocked !== "notFound" && (
            <OfferMemory personId={personId} />
          )}
          {blocked !== "ended" && blocked !== "notFound" && (
            <EndChat
              conversationId={conversation.conversationId}
              disabled={sending || stopped}
              onEnded={() => navigate({ to: "/persons" })}
            />
          )}
        </div>
      </div>

      <div
        role="note"
        className="rounded-lg border bg-card px-4 py-3 text-sm text-card-foreground"
      >
        {conversation.notice}
      </div>

      <div
        role="log"
        aria-live="polite"
        aria-label="Conversation"
        className="flex h-[50vh] flex-col gap-4 overflow-y-auto rounded-lg border p-4"
      >
        {lines.map((line) => (
          <ChatMessage key={line.id} line={line} />
        ))}
        <div ref={logEnd} />
      </div>

      {(failure || blocked) && (
        <Alert variant="destructive">
          <AlertDescription>
            {blocked ? BLOCKED_MESSAGES[blocked] : failure}
          </AlertDescription>
        </Alert>
      )}

      <Form {...form}>
        <form
          className="flex items-start gap-2"
          onSubmit={form.handleSubmit(send)}
        >
          <FormField
            control={form.control}
            name="text"
            render={({ field }) => (
              <FormItem className="flex-1">
                <FormLabel className="sr-only">Your message</FormLabel>
                <FormControl>
                  <Textarea
                    placeholder="Write a message"
                    className="min-h-12"
                    disabled={sending || stopped}
                    onKeyDown={(event) => {
                      // Enter while an input method is composing picks a candidate
                      if (
                        event.key === "Enter" &&
                        !event.shiftKey &&
                        !event.nativeEvent.isComposing
                      ) {
                        event.preventDefault()
                        form.handleSubmit(send)()
                      }
                    }}
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <LoadingButton type="submit" loading={sending} disabled={stopped}>
            Send
          </LoadingButton>
        </form>
      </Form>

      <RecallPanel personId={personId} />
    </div>
  )
}

export default ChatWindow
