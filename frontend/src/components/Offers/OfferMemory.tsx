import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation } from "@tanstack/react-query"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { PersonsService } from "@/client"
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
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

const MAX_OFFER_CHARS = 5000

const formSchema = z.object({
  content: z
    .string()
    .trim()
    .min(1, { message: "Write the memory first" })
    .max(MAX_OFFER_CHARS, {
      message: `A memory can have at most ${MAX_OFFER_CHARS} characters`,
    }),
})

type FormData = z.infer<typeof formSchema>

interface OfferMemoryProps {
  personId: string
}

// What is typed here goes to the family only; it is never logged or kept in the
// browser, and it is a memory only if the family accepts it (AC-11.4)
const OfferMemory = ({ personId }: OfferMemoryProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const [sent, setSent] = useState<string | null>(null)
  const { showErrorToast } = useCustomToast()

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: { content: "" },
  })

  const mutation = useMutation({
    mutationFn: async (data: FormData) =>
      (
        await PersonsService.createOffer({
          path: { id: personId },
          body: { content: data.content },
        })
      ).data,
    onSuccess: (response) => {
      form.reset({ content: "" })
      setSent(response.message ?? "Your offer was sent to the family.")
    },
    onError: handleError.bind(showErrorToast),
  })

  const close = (open: boolean) => {
    setIsOpen(open)
    if (!open) {
      setSent(null)
      form.reset({ content: "" })
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={close}>
      <Button variant="outline" onClick={() => setIsOpen(true)}>
        Offer a memory
      </Button>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Offer a memory</DialogTitle>
          <DialogDescription>
            Share something you remember. The family decides whether it becomes
            a memory; nothing you write here is added on its own.
          </DialogDescription>
        </DialogHeader>
        {sent ? (
          <>
            <p role="status" className="text-sm">
              {sent}
            </p>
            <DialogFooter>
              <DialogClose asChild>
                <Button>Close</Button>
              </DialogClose>
            </DialogFooter>
          </>
        ) : (
          <Form {...form}>
            <form onSubmit={form.handleSubmit((data) => mutation.mutate(data))}>
              <FormField
                control={form.control}
                name="content"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Your memory</FormLabel>
                    <FormControl>
                      <Textarea
                        className="min-h-32"
                        placeholder="She sang while she cooked…"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <DialogFooter className="mt-4">
                <DialogClose asChild>
                  <Button variant="outline" disabled={mutation.isPending}>
                    Cancel
                  </Button>
                </DialogClose>
                <LoadingButton type="submit" loading={mutation.isPending}>
                  Send
                </LoadingButton>
              </DialogFooter>
            </form>
          </Form>
        )}
      </DialogContent>
    </Dialog>
  )
}

export default OfferMemory
