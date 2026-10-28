import { EllipsisVertical } from "lucide-react"
import { useState } from "react"

import type { PersonPublic } from "@/client"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import DeletePerson from "./DeletePerson"
import EditPerson from "./EditPerson"

interface PersonActionsMenuProps {
  person: PersonPublic
}

export const PersonActionsMenu = ({ person }: PersonActionsMenuProps) => {
  const [open, setOpen] = useState(false)

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon">
          <EllipsisVertical />
          <span className="sr-only">Person actions</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <EditPerson person={person} onSuccess={() => setOpen(false)} />
        <DeletePerson id={person.id} onSuccess={() => setOpen(false)} />
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
