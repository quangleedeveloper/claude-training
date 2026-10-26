import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { RotateCw } from "lucide-react"
import { useEffect, useRef, useState } from "react"

import {
  type MemoryFilePublic,
  type MemoryFileStatus,
  MemoryFilesService,
  type MemoryPublic,
  type RejectedMemoryFile,
} from "@/client"
import { Badge } from "@/components/ui/badge"
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
import { Progress } from "@/components/ui/progress"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import useCustomToast from "@/hooks/useCustomToast"
import {
  formatBytes,
  MAX_FILES_PER_UPLOAD,
  partitionMediaFiles,
} from "@/lib/mediaLimits"
import { handleError } from "@/utils"
import DeleteMemoryFile from "./DeleteMemoryFile"
import ExtractedMemories from "./ExtractedMemories"
import FileDropzone from "./FileDropzone"
import PreviewMemoryFile from "./PreviewMemoryFile"

const STATUS_LABELS: Record<MemoryFileStatus, string> = {
  uploaded: "Uploaded",
  processing: "Processing",
  processed: "Processed",
  failed: "Failed",
}

const STATUS_VARIANTS: Record<
  MemoryFileStatus,
  "default" | "secondary" | "destructive"
> = {
  uploaded: "secondary",
  processing: "secondary",
  processed: "default",
  failed: "destructive",
}

// Files are processed in the background, so keep refreshing until they settle
const POLL_INTERVAL_MS = 2000

const isPending = (file: MemoryFilePublic) =>
  file.status === "uploaded" || file.status === "processing"

interface MemoryFilesProps {
  memory: MemoryPublic
  isOpen: boolean
  onOpenChange: (open: boolean) => void
}

// Rendered outside the actions dropdown: the native file picker blurs the window,
// which would dismiss the dropdown and unmount a dialog living inside it.
const MemoryFiles = ({ memory, isOpen, onOpenChange }: MemoryFilesProps) => {
  const [selected, setSelected] = useState<File[]>([])
  const [rejected, setRejected] = useState<RejectedMemoryFile[]>([])
  const [progress, setProgress] = useState(0)
  const [inputKey, setInputKey] = useState(0)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const queryKey = ["memories", memory.id, "files"]

  const { data: files } = useQuery({
    queryKey,
    queryFn: async () =>
      (
        await MemoryFilesService.readMemoryFiles({
          path: { memory_id: memory.id },
        })
      ).data,
    enabled: isOpen,
    refetchInterval: (query) =>
      query.state.data?.data.some(isPending) ? POLL_INTERVAL_MS : false,
  })

  const uploadMutation = useMutation({
    mutationFn: (toUpload: File[]) =>
      MemoryFilesService.uploadMemoryFiles({
        path: { memory_id: memory.id },
        body: { files: toUpload },
        onUploadProgress: (event) => {
          if (event.total) {
            setProgress(Math.round((event.loaded * 100) / event.total))
          }
        },
      }),
    onSuccess: ({ data }) => {
      setRejected(data.rejected)
      setSelected([])
      setInputKey((key) => key + 1)
      if (data.uploaded.length > 0) {
        showSuccessToast(
          `${data.uploaded.length} file${data.uploaded.length === 1 ? "" : "s"} uploaded`,
        )
      }
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      setProgress(0)
      queryClient.invalidateQueries({ queryKey })
    },
  })

  // Extraction runs after a file settles, so refresh what the AI found once the
  // last pending file is done
  const hasPending = files?.data.some(isPending) ?? false
  const wasPending = useRef(false)
  useEffect(() => {
    if (wasPending.current && !hasPending) {
      queryClient.invalidateQueries({
        queryKey: ["memories", memory.id, "extracted"],
      })
    }
    wasPending.current = hasPending
  }, [hasPending, memory.id, queryClient])

  const retryMutation = useMutation({
    mutationFn: (fileId: string) =>
      MemoryFilesService.retryMemoryFile({
        path: { memory_id: memory.id, file_id: fileId },
      }),
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey })
    },
  })

  const chooseFiles = (chosen: File[]) => {
    const { valid, rejected: invalid } = partitionMediaFiles(chosen)
    setSelected(valid)
    setRejected(invalid)
  }

  const handleOpenChange = (open: boolean) => {
    onOpenChange(open)
    if (!open) {
      setSelected([])
      setRejected([])
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={handleOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Files for {memory.title}</DialogTitle>
          <DialogDescription>
            Upload photos, videos and audio recordings of {memory.person_name}.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-3">
          <FileDropzone
            id={`memory-files-${memory.id}`}
            selected={selected}
            onFilesChosen={chooseFiles}
            disabled={uploadMutation.isPending}
            inputKey={inputKey}
          />
          <p className="text-xs text-muted-foreground">
            Images up to 10 MB, audio up to 50 MB, video up to 200 MB, at most{" "}
            {MAX_FILES_PER_UPLOAD} files at a time.
          </p>

          {uploadMutation.isPending && (
            <Progress value={progress} aria-label="Upload progress" />
          )}

          {rejected.length > 0 && (
            <ul
              className="rounded-md border border-destructive/50 p-3 text-sm text-destructive"
              aria-label="Files not uploaded"
            >
              {rejected.map((file, index) => (
                <li key={`${file.filename}-${index}`}>
                  <span className="font-medium">{file.filename}</span>:{" "}
                  {file.reason}
                </li>
              ))}
            </ul>
          )}

          <div className="flex justify-end">
            <LoadingButton
              loading={uploadMutation.isPending}
              disabled={selected.length === 0}
              onClick={() => uploadMutation.mutate(selected)}
            >
              Upload{selected.length > 0 ? ` ${selected.length}` : ""}
            </LoadingButton>
          </div>
        </div>

        {files && files.data.length === 0 ? (
          <p className="py-6 text-center text-muted-foreground">
            No files uploaded yet
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>File</TableHead>
                <TableHead>Size</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>
                  <span className="sr-only">Actions</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {files?.data.map((file) => (
                <TableRow key={file.id}>
                  <TableCell>
                    <span className="font-medium">{file.filename}</span>
                    <span className="block text-xs text-muted-foreground">
                      {file.kind}
                    </span>
                  </TableCell>
                  <TableCell>{formatBytes(file.size_bytes)}</TableCell>
                  <TableCell>
                    <Badge variant={STATUS_VARIANTS[file.status]}>
                      {STATUS_LABELS[file.status]}
                    </Badge>
                    {file.status === "failed" && file.error_message && (
                      <span className="mt-1 block text-xs text-destructive">
                        {file.error_message}
                      </span>
                    )}
                  </TableCell>
                  <TableCell>
                    <div className="flex justify-end gap-1">
                      <PreviewMemoryFile memoryId={memory.id} file={file} />
                      {file.status === "failed" && (
                        <Button
                          variant="ghost"
                          size="icon"
                          disabled={retryMutation.isPending}
                          onClick={() => retryMutation.mutate(file.id)}
                        >
                          <RotateCw />
                          <span className="sr-only">
                            Retry file {file.filename}
                          </span>
                        </Button>
                      )}
                      <DeleteMemoryFile
                        memoryId={memory.id}
                        fileId={file.id}
                        filename={file.filename}
                      />
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}

        <div className="grid gap-2">
          <h3 className="text-sm font-semibold">What the AI found</h3>
          <p className="text-xs text-muted-foreground">
            Review these. Edit anything that is wrong, or reject it to keep it
            out of search and answers.
          </p>
          <ExtractedMemories memoryId={memory.id} files={files?.data ?? []} />
        </div>

        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline">Close</Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default MemoryFiles
