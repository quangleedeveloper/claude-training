import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Plus } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import {
  MemoriesService,
  type MemoryCreate,
  MemoryFilesService,
} from "@/client"
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
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { MAX_FILES_PER_UPLOAD, partitionMediaFiles } from "@/lib/mediaLimits"
import { handleError } from "@/utils"
import FileDropzone from "./FileDropzone"
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

const AddMemory = () => {
  const [isOpen, setIsOpen] = useState(false)
  const [selected, setSelected] = useState<File[]>([])
  const [rejected, setRejected] = useState<
    { filename: string; reason: string }[]
  >([])
  const [inputKey, setInputKey] = useState(0)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      person_id: NO_PERSON,
      title: "",
      content: "",
    },
  })

  const resetFiles = () => {
    setSelected([])
    setRejected([])
    setInputKey((key) => key + 1)
  }

  const mutation = useMutation({
    mutationFn: async ({
      memory,
      personId,
      files,
    }: {
      memory: MemoryCreate
      personId: string
      files: File[]
    }) => {
      const { data: created } = await MemoriesService.createMemory({
        body: memory,
      })
      // The memory already exists, so a failed link must not fail the whole save
      let linkError: unknown = null
      if (personId !== NO_PERSON) {
        try {
          await MemoriesService.linkMemoryPerson({
            path: { id: created.id },
            body: { person_id: personId },
          })
        } catch (error) {
          linkError = error
        }
      }
      if (files.length === 0) return { uploadError: null, linkError }
      // The memory already exists at this point, so a failed upload must not
      // fail the whole save; the user can retry from Manage Files.
      try {
        await MemoryFilesService.uploadMemoryFiles({
          path: { memory_id: created.id },
          body: { files },
        })
        return { uploadError: null, linkError }
      } catch (error) {
        return { uploadError: error, linkError }
      }
    },
    onSuccess: ({ uploadError, linkError }) => {
      showSuccessToast("Memory created successfully")
      if (linkError) {
        showErrorToast(
          "Memory saved, but it could not be linked to the person. Use Link Person.",
        )
      }
      if (uploadError) {
        showErrorToast(
          "Memory saved, but its files failed to upload. Add them from Manage Files.",
        )
      }
      form.reset()
      resetFiles()
      setIsOpen(false)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["memories"] })
    },
  })

  const chooseFiles = (chosen: File[]) => {
    const { valid, rejected: invalid } = partitionMediaFiles(chosen)
    setSelected(valid)
    setRejected(invalid)
  }

  const onSubmit = ({ person_id, ...memory }: FormData) => {
    mutation.mutate({ memory, personId: person_id, files: selected })
  }

  const onOpenChange = (open: boolean) => {
    setIsOpen(open)
    if (!open) resetFiles()
  }

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogTrigger asChild>
        <Button className="my-4">
          <Plus className="mr-2" />
          Add Memory
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Add Memory</DialogTitle>
          <DialogDescription>
            Write down a story you want to keep about someone.
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)}>
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
                      <Input
                        placeholder="Title"
                        type="text"
                        {...field}
                        required
                      />
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
                    <FormLabel htmlFor="add-memory-person">Person</FormLabel>
                    <PersonSelect
                      id="add-memory-person"
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

              <div className="grid gap-2">
                <FileDropzone
                  id="add-memory-files"
                  selected={selected}
                  onFilesChosen={chooseFiles}
                  disabled={mutation.isPending}
                  inputKey={inputKey}
                />
                <p className="text-xs text-muted-foreground">
                  Optional. Images up to 10 MB, audio up to 50 MB, video up to
                  200 MB, at most {MAX_FILES_PER_UPLOAD} files.
                </p>
                {rejected.length > 0 && (
                  <ul
                    className="rounded-md border border-destructive/50 p-3 text-sm text-destructive"
                    aria-label="Files not selected"
                  >
                    {rejected.map((file, index) => (
                      <li key={`${file.filename}-${index}`}>
                        <span className="font-medium">{file.filename}</span>:{" "}
                        {file.reason}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
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

export default AddMemory
