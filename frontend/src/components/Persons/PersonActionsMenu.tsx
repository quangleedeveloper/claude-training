import { Link } from "@tanstack/react-router"
import { EllipsisVertical, MessageCircle } from "lucide-react"
import { useState } from "react"

import type { PersonPublic } from "@/client"
import OffersList from "@/components/Offers/OffersList"
import ShareDialog from "@/components/Sharing/ShareDialog"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import DeletePerson from "./DeletePerson"
import EditPerson from "./EditPerson"
import PersonMemories from "./PersonMemories"

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
        <DropdownMenuItem asChild>
          <Link to="/chat/$personId" params={{ personId: person.id }}>
            <MessageCircle />
            Talk
          </Link>
        </DropdownMenuItem>
        <PersonMemories personId={person.id} personName={person.name} />
        <OffersList personId={person.id} personName={person.name} />
        <ShareDialog personId={person.id} personName={person.name} />
        <EditPerson person={person} onSuccess={() => setOpen(false)} />
        <DeletePerson id={person.id} onSuccess={() => setOpen(false)} />
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
