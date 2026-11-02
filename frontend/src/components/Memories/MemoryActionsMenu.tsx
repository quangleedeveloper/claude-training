import { EllipsisVertical, Paperclip } from "lucide-react"
import { useState } from "react"

import type { MemoryPublic } from "@/client"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import DeleteMemory from "./DeleteMemory"
import EditMemory from "./EditMemory"
import LinkPerson from "./LinkPerson"
import MemoryFiles from "./MemoryFiles"

interface MemoryActionsMenuProps {
  memory: MemoryPublic
}

export const MemoryActionsMenu = ({ memory }: MemoryActionsMenuProps) => {
  const [open, setOpen] = useState(false)
  const [filesOpen, setFilesOpen] = useState(false)

  return (
    <>
      <DropdownMenu open={open} onOpenChange={setOpen}>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon">
            <EllipsisVertical />
            <span className="sr-only">Memory actions</span>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <EditMemory memory={memory} onSuccess={() => setOpen(false)} />
          <LinkPerson memory={memory} onSuccess={() => setOpen(false)} />
          <DropdownMenuItem onSelect={() => setFilesOpen(true)}>
            <Paperclip />
            Manage Files
          </DropdownMenuItem>
          <DeleteMemory id={memory.id} onSuccess={() => setOpen(false)} />
        </DropdownMenuContent>
      </DropdownMenu>
      <MemoryFiles
        memory={memory}
        isOpen={filesOpen}
        onOpenChange={setFilesOpen}
      />
    </>
  )
}
