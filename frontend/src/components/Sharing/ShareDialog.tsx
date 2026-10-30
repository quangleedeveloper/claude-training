import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Share2 } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { PersonsService } from "@/client"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { DropdownMenuItem } from "@/components/ui/dropdown-menu"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
import MembersList from "./MembersList"

// The tick mirrors the API's `Literal[True]`: no tick, no request
const formSchema = z.object({
  email: z.email({ message: "Enter a valid email address" }),
  adult_confirmed: z.literal(true, {
    message: "Confirm that this person is 18 or older",
  }),
})

type FormData = z.infer<typeof formSchema>

// The form starts unticked; the schema only accepts `true`, so this is the one cast
const EMPTY = { email: "", adult_confirmed: false as unknown as true }

interface ShareDialogProps {
  personId: string
  personName: string
}

const ShareDialog = ({ personId, personName }: ShareDialogProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const [answer, setAnswer] = useState<string | null>(null)
  const queryClient = useQueryClient()
  const { showErrorToast } = useCustomToast()

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: EMPTY,
  })
  const confirmed = form.watch("adult_confirmed") as boolean

  const invite = useMutation({
    mutationFn: async (data: FormData) =>
      (
        await PersonsService.inviteMember({
          path: { id: personId },
          body: data,
        })
      ).data,
    onSuccess: (response) => {
      // The API's one answer, whether or not the address has an account
      setAnswer(response.message)
      form.reset(EMPTY)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () =>
      queryClient.invalidateQueries({ queryKey: ["members", personId] }),
  })

  const open = (value: boolean) => {
    setIsOpen(value)
    if (!value) {
      setAnswer(null)
      form.reset(EMPTY)
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={open}>
      <DropdownMenuItem
        onSelect={(e) => e.preventDefault()}
        onClick={() => setIsOpen(true)}
      >
        <Share2 />
        Share
      </DropdownMenuItem>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Share {personName}</DialogTitle>
          <DialogDescription>
            Let someone with an account talk with this persona. They can see its
            replies and the memories they cite, nothing else.
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form
            className="grid gap-4"
            onSubmit={form.handleSubmit((data) => invite.mutate(data))}
          >
            <FormField
              control={form.control}
              name="email"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Email</FormLabel>
                  <FormControl>
                    <Input
                      type="email"
                      placeholder="name@example.com"
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="adult_confirmed"
              render={({ field }) => (
                <FormItem className="flex flex-row items-center gap-2">
                  <FormControl>
                    <Checkbox
                      checked={field.value === true}
                      onCheckedChange={(checked) =>
                        field.onChange(checked === true)
                      }
                    />
                  </FormControl>
                  <FormLabel className="font-normal">
                    I confirm this person is 18 or older
                  </FormLabel>
                  <FormMessage />
                </FormItem>
              )}
            />
            {answer && (
              <p role="status" className="text-sm">
                {answer}
              </p>
            )}
            <div className="flex justify-end">
              <LoadingButton
                type="submit"
                loading={invite.isPending}
                disabled={!confirmed}
              >
                Invite
              </LoadingButton>
            </div>
          </form>
        </Form>

        <section
          aria-label="Who can talk with this persona"
          className="grid gap-2"
        >
          <h3 className="text-sm font-semibold">
            Who can talk with this persona
          </h3>
          <MembersList personId={personId} />
        </section>

        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline">Close</Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default ShareDialog
