import { useMutation } from "@tanstack/react-query"
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

interface EndChatProps {
  conversationId: string
  disabled?: boolean
  onEnded: () => void
}

const EndChat = ({ conversationId, disabled, onEnded }: EndChatProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const mutation = useMutation({
    mutationFn: async () => {
      await ConversationsService.endConversation({
        path: { conversation_id: conversationId },
      })
    },
    onSuccess: () => {
      showSuccessToast("The conversation has ended")
      setIsOpen(false)
      onEnded()
    },
    onError: handleError.bind(showErrorToast),
  })

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <Button
        variant="outline"
        disabled={disabled}
        onClick={() => setIsOpen(true)}
      >
        End conversation
      </Button>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>End this conversation?</DialogTitle>
          <DialogDescription>
            The messages of this conversation will be deleted. A short note of
            what you talked about is kept for your next conversation, and you
            can delete it any time.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="mt-4">
          <DialogClose asChild>
            <Button variant="outline" disabled={mutation.isPending}>
              Cancel
            </Button>
          </DialogClose>
          <LoadingButton
            loading={mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            End conversation
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default EndChat
