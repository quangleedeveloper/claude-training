import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Ban, Undo2 } from "lucide-react"

import {
  ExtractedMemoriesService,
  type ExtractedMemoryPublic,
  type MemoryFilePublic,
} from "@/client"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import useCustomToast from "@/hooks/useCustomToast"
import { cn } from "@/lib/utils"
import { handleError } from "@/utils"
import EditExtractedMemory from "./EditExtractedMemory"

// Below these the AI said it was unsure, so ask the reader to double check
const HIGH_CONFIDENCE = 0.75
const MEDIUM_CONFIDENCE = 0.5

const confidenceLabel = (confidence: number) => {
  const percent = `${Math.round(confidence * 100)}%`
  if (confidence >= HIGH_CONFIDENCE) return `High confidence ${percent}`
  if (confidence >= MEDIUM_CONFIDENCE) return `Medium confidence ${percent}`
  return `Low confidence ${percent}`
}

const confidenceVariant = (confidence: number) =>
  confidence >= MEDIUM_CONFIDENCE ? "secondary" : "destructive"

interface ExtractedMemoriesProps {
  memoryId: string
  files: MemoryFilePublic[]
}

const ExtractedMemories = ({ memoryId, files }: ExtractedMemoriesProps) => {
  const queryClient = useQueryClient()
  const { showErrorToast } = useCustomToast()
  const queryKey = ["memories", memoryId, "extracted"]

  const { data } = useQuery({
    queryKey,
    queryFn: async () =>
      (
        await ExtractedMemoriesService.readExtractedMemories({
          path: { memory_id: memoryId },
        })
      ).data,
  })

  const rejectMutation = useMutation({
    mutationFn: ({ id, rejected }: { id: string; rejected: boolean }) =>
      ExtractedMemoriesService.updateExtractedMemory({
        path: { memory_id: memoryId, extracted_id: id },
        body: { rejected },
      }),
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey })
    },
  })

  const sourceLabel = (item: ExtractedMemoryPublic) =>
    item.file_id
      ? (files.find((file) => file.id === item.file_id)?.filename ??
        "A deleted file")
      : "The written story"

  if (!data || data.data.length === 0) {
    return (
      <p className="py-4 text-center text-sm text-muted-foreground">
        Nothing extracted yet. Memories appear here after a story is saved or a
        file finishes processing.
      </p>
    )
  }

  return (
    <ul className="grid gap-2" aria-label="Extracted memories">
      {data.data.map((item) => {
        const rejected = item.status === "rejected"
        return (
          <li key={item.id} className="rounded-md border p-3">
            <div className="flex items-start justify-between gap-3">
              <div className="grid gap-1">
                <p
                  className={cn(
                    "text-sm",
                    rejected && "line-through opacity-60",
                  )}
                >
                  {item.content}
                </p>
                <p className="text-xs text-muted-foreground">
                  {[
                    item.people.length > 0 &&
                      `People: ${item.people.join(", ")}`,
                    item.event_date_text && `When: ${item.event_date_text}`,
                    item.location && `Where: ${item.location}`,
                    `From: ${sourceLabel(item)}`,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
                <div className="flex flex-wrap gap-1">
                  <Badge variant="outline">{item.category}</Badge>
                  <Badge variant={confidenceVariant(item.confidence)}>
                    {confidenceLabel(item.confidence)}
                  </Badge>
                  {item.status === "edited" && (
                    <Badge variant="outline">Edited</Badge>
                  )}
                  {rejected && <Badge variant="destructive">Rejected</Badge>}
                </div>
              </div>
              <div className="flex shrink-0 gap-1">
                {!rejected && (
                  <EditExtractedMemory memoryId={memoryId} extracted={item} />
                )}
                <Button
                  variant="ghost"
                  size="icon"
                  disabled={rejectMutation.isPending}
                  onClick={() =>
                    rejectMutation.mutate({ id: item.id, rejected: !rejected })
                  }
                >
                  {rejected ? <Undo2 /> : <Ban />}
                  <span className="sr-only">
                    {rejected ? "Restore" : "Reject"} extracted memory
                  </span>
                </Button>
              </div>
            </div>
          </li>
        )
      })}
    </ul>
  )
}

export default ExtractedMemories
