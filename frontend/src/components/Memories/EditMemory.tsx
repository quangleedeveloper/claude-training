import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Pencil } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { MemoriesService, type MemoryPublic } from "@/client"
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
import MemoryEditor from "./MemoryEditor"
import PersonSelect, { NO_PERSON } from "./PersonSelect"

const formSchema = z.object({
  person_id: z.string(),
  title: z.string().min(1, { message: "Title is required" }),
  content: z
    .string()
    .min(1, { message: "Memory is required" })
    .max(5000, { message: "Memory must be at most 5000 characters" }),
})

type FormData = z.infer<typeof formSchema>

interface EditMemoryProps {
  memory: MemoryPublic
  onSuccess: () => void
}

const EditMemory = ({ memory, onSuccess }: EditMemoryProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      person_id: memory.person_id ?? NO_PERSON,
      title: memory.title,
      content: memory.content,
    },
  })

  const mutation = useMutation({
    mutationFn: async ({ person_id, ...changes }: FormData) => {
      await MemoriesService.updateMemory({
        path: { id: memory.id },
        body: changes,
      })
      // Linked after the edit, so the story is saved even if linking fails
      if (person_id === (memory.person_id ?? NO_PERSON)) {
        return { linkError: null }
      }
      try {
        await MemoriesService.linkMemoryPerson({
          path: { id: memory.id },
          body: { person_id: person_id === NO_PERSON ? null : person_id },
        })
        return { linkError: null }
      } catch (error) {
        return { linkError: error }
      }
    },
    onSuccess: ({ linkError }) => {
      showSuccessToast("Memory updated successfully")
      if (linkError) {
        showErrorToast(
          "Memory saved, but the person could not be changed. Use Link Person.",
        )
      }
      setIsOpen(false)
      onSuccess()
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["memories"] })
    },
  })

  const onSubmit = (data: FormData) => {
    mutation.mutate(data)
  }

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenuItem
        onSelect={(e) => e.preventDefault()}
        onClick={() => setIsOpen(true)}
      >
        <Pencil />
        Edit Memory
      </DropdownMenuItem>
      <DialogContent className="sm:max-w-md">
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)}>
            <DialogHeader>
              <DialogTitle>Edit Memory</DialogTitle>
              <DialogDescription>
                Update the memory details below.
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <FormField
                control={form.control}
                name="title"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      Title <span className="text-destructive">*</span>
                    </FormLabel>
                    <FormControl>
                      <Input placeholder="Title" type="text" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="person_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel htmlFor={`edit-memory-person-${memory.id}`}>
                      Person
                    </FormLabel>
                    <PersonSelect
                      id={`edit-memory-person-${memory.id}`}
                      value={field.value}
                      onChange={field.onChange}
                      disabled={mutation.isPending}
                    />
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="content"
                render={({ field, fieldState }) => (
                  <FormItem>
                    <FormLabel>
                      Memory <span className="text-destructive">*</span>
                    </FormLabel>
                    <MemoryEditor
                      label="Memory"
                      value={field.value}
                      onChange={field.onChange}
                      onBlur={field.onBlur}
                      disabled={mutation.isPending}
                      invalid={fieldState.invalid}
                    />
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

export default EditMemory
