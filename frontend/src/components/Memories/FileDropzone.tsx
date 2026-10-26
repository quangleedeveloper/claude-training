import { UploadCloud } from "lucide-react"
import { type ChangeEvent, type DragEvent, useState } from "react"

import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ACCEPTED_EXTENSIONS } from "@/lib/mediaLimits"
import { cn } from "@/lib/utils"

interface FileDropzoneProps {
  id: string
  selected: File[]
  onFilesChosen: (files: File[]) => void
  disabled?: boolean
  // Changing the key resets the native input so the same file can be re-picked
  inputKey?: number
}

const FileDropzone = ({
  id,
  selected,
  onFilesChosen,
  disabled = false,
  inputKey = 0,
}: FileDropzoneProps) => {
  const [isDragging, setIsDragging] = useState(false)

  const onChange = (event: ChangeEvent<HTMLInputElement>) => {
    onFilesChosen(Array.from(event.target.files ?? []))
  }

  const onDragOver = (event: DragEvent<HTMLLabelElement>) => {
    // Without preventDefault the browser opens the dropped file instead
    event.preventDefault()
    if (!disabled) setIsDragging(true)
  }

  const onDrop = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault()
    setIsDragging(false)
    if (disabled) return
    onFilesChosen(Array.from(event.dataTransfer.files))
  }

  return (
    <Label
      htmlFor={id}
      onDragOver={onDragOver}
      onDragLeave={() => setIsDragging(false)}
      onDrop={onDrop}
      className={cn(
        "flex cursor-pointer flex-col items-center gap-2 rounded-md border-2 border-dashed p-8 text-center text-muted-foreground transition-colors hover:bg-muted/50 has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring",
        isDragging && "border-primary bg-muted/50 text-foreground",
        disabled && "pointer-events-none opacity-50",
      )}
    >
      <UploadCloud className="size-8" />
      <span>Drag and drop photos, videos and audio here</span>
      <span className="text-xs">or click to browse</span>
      {selected.length > 0 && (
        <span className="text-sm font-medium text-foreground">
          {`${selected.length} file${selected.length === 1 ? "" : "s"} selected: ${selected.map((file) => file.name).join(", ")}`}
        </span>
      )}
      <Input
        key={inputKey}
        id={id}
        className="sr-only"
        type="file"
        multiple
        accept={ACCEPTED_EXTENSIONS}
        onChange={onChange}
        disabled={disabled}
      />
    </Label>
  )
}

export default FileDropzone
