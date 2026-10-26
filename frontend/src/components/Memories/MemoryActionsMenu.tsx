import { EllipsisVertical } from "lucide-react"
import { useState } from "react"

import type { MemoryPublic } from "@/client"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import DeleteMemory from "./DeleteMemory"
import EditMemory from "./EditMemory"

interface MemoryActionsMenuProps {
  memory: MemoryPublic
}

export const MemoryActionsMenu = ({ memory }: MemoryActionsMenuProps) => {
  const [open, setOpen] = useState(false)

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon">
          <EllipsisVertical />
          <span className="sr-only">Memory actions</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <EditMemory memory={memory} onSuccess={() => setOpen(false)} />
        <DeleteMemory id={memory.id} onSuccess={() => setOpen(false)} />
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
