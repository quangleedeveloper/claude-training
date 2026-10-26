import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Paperclip, RotateCw } from "lucide-react"
import { type ChangeEvent, useState } from "react"

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
import { DropdownMenuItem } from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
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
  ACCEPTED_EXTENSIONS,
  formatBytes,
  MAX_FILES_PER_UPLOAD,
  validateMediaFile,
} from "@/lib/mediaLimits"
import { handleError } from "@/utils"
import DeleteMemoryFile from "./DeleteMemoryFile"

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
  onClose: () => void
}

const MemoryFiles = ({ memory, onClose }: MemoryFilesProps) => {
  const [isOpen, setIsOpen] = useState(false)
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

  const onFilesChosen = (event: ChangeEvent<HTMLInputElement>) => {
    const valid: File[] = []
    const invalid: RejectedMemoryFile[] = []
    for (const file of Array.from(event.target.files ?? [])) {
      const reason =
        valid.length >= MAX_FILES_PER_UPLOAD
          ? `At most ${MAX_FILES_PER_UPLOAD} files per upload`
          : validateMediaFile(file)
      if (reason) {
        invalid.push({ filename: file.name, reason })
      } else {
        valid.push(file)
      }
    }
    setSelected(valid)
    setRejected(invalid)
  }

  const onOpenChange = (open: boolean) => {
    setIsOpen(open)
    if (!open) {
      setSelected([])
      setRejected([])
      onClose()
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DropdownMenuItem
        onSelect={(e) => e.preventDefault()}
        onClick={() => setIsOpen(true)}
      >
        <Paperclip />
        Manage Files
      </DropdownMenuItem>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Files for {memory.title}</DialogTitle>
          <DialogDescription>
            Upload photos, videos and audio recordings of {memory.person_name}.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-3">
          <Label htmlFor={`memory-files-${memory.id}`}>
            Photos, videos and audio
          </Label>
          <Input
            key={inputKey}
            id={`memory-files-${memory.id}`}
            type="file"
            multiple
            accept={ACCEPTED_EXTENSIONS}
            onChange={onFilesChosen}
            disabled={uploadMutation.isPending}
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
