import { useQuery } from "@tanstack/react-query"
import { Eye, Maximize, Minimize } from "lucide-react"
import { useEffect, useRef, useState } from "react"

import { type MemoryFilePublic, MemoryFilesService } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import useCustomToast from "@/hooks/useCustomToast"
import { formatBytes } from "@/lib/mediaLimits"
import { cn } from "@/lib/utils"

interface PreviewMemoryFileProps {
  memoryId: string
  file: MemoryFilePublic
}

const PreviewMemoryFile = ({ memoryId, file }: PreviewMemoryFileProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const [objectUrl, setObjectUrl] = useState<string | null>(null)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const imageFrameRef = useRef<HTMLDivElement>(null)
  const { showErrorToast } = useCustomToast()

  // <img>/<video> tags can't send the bearer token, so fetch the bytes through
  // the authenticated client and hand the browser a blob URL.
  const {
    data: blob,
    isPending,
    isError,
  } = useQuery({
    queryKey: ["memories", memoryId, "files", file.id, "content"],
    queryFn: async () => {
      const { data } = await MemoryFilesService.readMemoryFileContent({
        path: { memory_id: memoryId, file_id: file.id },
        responseType: "blob",
      })
      return data as unknown as Blob
    },
    enabled: isOpen,
    staleTime: Number.POSITIVE_INFINITY,
    gcTime: 0,
  })

  // Track the browser's state so Esc (which exits fullscreen natively) updates the icon
  useEffect(() => {
    const onChange = () => setIsFullscreen(document.fullscreenElement !== null)
    document.addEventListener("fullscreenchange", onChange)
    return () => document.removeEventListener("fullscreenchange", onChange)
  }, [])

  const toggleFullscreen = async () => {
    try {
      if (document.fullscreenElement) {
        await document.exitFullscreen()
      } else {
        await imageFrameRef.current?.requestFullscreen()
      }
    } catch {
      showErrorToast("Full screen is not available in this browser")
    }
  }

  useEffect(() => {
    if (!blob) {
      setObjectUrl(null)
      return
    }
    const url = URL.createObjectURL(blob)
    setObjectUrl(url)
    return () => URL.revokeObjectURL(url)
  }, [blob])

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="icon">
          <Eye />
          <span className="sr-only">Open file {file.filename}</span>
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle className="truncate pr-6">{file.filename}</DialogTitle>
          <DialogDescription>
            {file.kind} · {formatBytes(file.size_bytes)}
          </DialogDescription>
        </DialogHeader>

        <div className="flex min-h-40 items-center justify-center">
          {isPending && (
            <p className="text-muted-foreground">Loading {file.kind}...</p>
          )}
          {isError && (
            <p className="text-destructive">Could not load this file</p>
          )}
          {objectUrl && file.kind === "image" && (
            <div
              ref={imageFrameRef}
              className={cn(
                "relative flex items-center justify-center",
                isFullscreen && "h-screen w-screen bg-black",
              )}
            >
              <img
                src={objectUrl}
                alt={file.filename}
                className={cn(
                  "max-w-full rounded-md object-contain",
                  isFullscreen ? "max-h-screen" : "max-h-[70vh]",
                )}
              />
              <Button
                variant="secondary"
                size="icon"
                className="absolute top-2 right-2 opacity-80 hover:opacity-100"
                onClick={toggleFullscreen}
              >
                {isFullscreen ? <Minimize /> : <Maximize />}
                <span className="sr-only">
                  {isFullscreen ? "Exit full screen" : "View full screen"}
                </span>
              </Button>
            </div>
          )}
          {objectUrl && file.kind === "video" && (
            // biome-ignore lint/a11y/useMediaCaption: user-uploaded recordings have no caption track
            <video
              src={objectUrl}
              controls
              autoPlay
              className="max-h-[70vh] w-full rounded-md"
            />
          )}
          {objectUrl && file.kind === "audio" && (
            // biome-ignore lint/a11y/useMediaCaption: user-uploaded recordings have no caption track
            <audio src={objectUrl} controls autoPlay className="w-full" />
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}

export default PreviewMemoryFile
