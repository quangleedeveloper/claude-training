import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Pencil } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { ExtractedMemoriesService, type ExtractedMemoryPublic } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import { Textarea } from "@/components/ui/textarea"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

const formSchema = z.object({
  content: z
    .string()
    .min(1, { message: "Content is required" })
    .max(2000, { message: "Content must be at most 2000 characters" }),
  people: z.string(),
  event_date_text: z
    .string()
    .max(100, { message: "When must be at most 100 characters" }),
  location: z
    .string()
    .max(255, { message: "Where must be at most 255 characters" }),
})

type FormData = z.infer<typeof formSchema>

interface EditExtractedMemoryProps {
  memoryId: string
  extracted: ExtractedMemoryPublic
}

const EditExtractedMemory = ({
  memoryId,
  extracted,
}: EditExtractedMemoryProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    defaultValues: {
      content: extracted.content,
      people: extracted.people.join(", "),
      event_date_text: extracted.event_date_text ?? "",
      location: extracted.location ?? "",
    },
  })

  const mutation = useMutation({
    mutationFn: (data: FormData) =>
      ExtractedMemoriesService.updateExtractedMemory({
        path: { memory_id: memoryId, extracted_id: extracted.id },
        body: {
          content: data.content,
          people: data.people
            .split(",")
            .map((name) => name.trim())
            .filter(Boolean),
          event_date_text: data.event_date_text.trim() || null,
          location: data.location.trim() || null,
        },
      }),
    onSuccess: () => {
      showSuccessToast("Extracted memory updated")
      setIsOpen(false)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({
        queryKey: ["memories", memoryId, "extracted"],
      })
    },
  })

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="icon">
          <Pencil />
          <span className="sr-only">Edit extracted memory</span>
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <Form {...form}>
          <form onSubmit={form.handleSubmit((data) => mutation.mutate(data))}>
            <DialogHeader>
              <DialogTitle>Edit extracted memory</DialogTitle>
              <DialogDescription>
                Correct what the AI found. Search will use your wording.
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <FormField
                control={form.control}
                name="content"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Memory</FormLabel>
                    <FormControl>
                      <Textarea {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="people"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>People</FormLabel>
                    <FormControl>
                      <Input placeholder="Mum, Uncle Joe" {...field} />
                    </FormControl>
                    <FormDescription>
                      Separate names with commas.
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="event_date_text"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>When</FormLabel>
                    <FormControl>
                      <Input placeholder="Summer 1998" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="location"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Where</FormLabel>
                    <FormControl>
                      <Input placeholder="Lake Erie" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <DialogFooter>
              <DialogClose asChild>
                <Button variant="outline" disabled={mutation.isPending}>
                  Cancel
                </Button>
              </DialogClose>
              <LoadingButton type="submit" loading={mutation.isPending}>
                Save
              </LoadingButton>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default EditExtractedMemory
