import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { AxiosError } from "axios"
import { useState } from "react"

import { ConversationsService } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

interface RecallPanelProps {
  personId: string
}

// The caller's own summary only: the API names it by person and caller, so there is
// no way to ask for anyone else's. Its text is never logged or kept outside the cache.
const RecallPanel = ({ personId }: RecallPanelProps) => {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [isOpen, setIsOpen] = useState(false)
  const queryKey = ["summary", personId]

  // A 404 is the normal "nothing kept yet" answer, so it becomes data, not an error
  const summary = useQuery({
    queryKey,
    queryFn: async () => {
      try {
        return (
          await ConversationsService.readSummary({
            path: { person_id: personId },
          })
        ).data
      } catch (error) {
        if (error instanceof AxiosError && error.response?.status === 404) {
          return null
        }
        throw error
      }
    },
    retry: false,
    gcTime: 0,
  })

  const mutation = useMutation({
    mutationFn: async () => {
      await ConversationsService.deleteSummary({
        path: { person_id: personId },
      })
    },
    onSuccess: () => {
      showSuccessToast("The note was deleted")
      setIsOpen(false)
      // Drop the text from the cache at once rather than waiting for a refetch
      queryClient.setQueryData(queryKey, null)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => queryClient.invalidateQueries({ queryKey }),
  })

  return (
    <section
      aria-label="What we talked about"
      className="flex flex-col gap-2 rounded-lg border p-4"
    >
      <div className="flex items-center justify-between gap-4">
        <h2 className="text-lg font-semibold">What we talked about</h2>
        {summary.data && (
          <Button variant="outline" onClick={() => setIsOpen(true)}>
            Delete note
          </Button>
        )}
      </div>

      {summary.isPending && (
        <p className="text-sm text-muted-foreground">Loading…</p>
      )}
      {summary.isError && (
        <p role="alert" className="text-sm text-destructive">
          Something went wrong. Please try again.
        </p>
      )}
      {summary.data === null && (
        <p className="text-sm text-muted-foreground">
          Nothing is kept yet. When you end a conversation, a short note of what
          you talked about is kept here for next time.
        </p>
      )}
      {summary.data && (
        <p className="whitespace-pre-wrap text-sm">{summary.data.content}</p>
      )}

      <Dialog open={isOpen} onOpenChange={setIsOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Delete this note?</DialogTitle>
            <DialogDescription>
              The persona will no longer remember what you talked about before.
              This cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="mt-4">
            <DialogClose asChild>
              <Button variant="outline" disabled={mutation.isPending}>
                Cancel
              </Button>
            </DialogClose>
            <LoadingButton
              variant="destructive"
              loading={mutation.isPending}
              onClick={() => mutation.mutate()}
            >
              Delete
            </LoadingButton>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  )
}

export default RecallPanel
