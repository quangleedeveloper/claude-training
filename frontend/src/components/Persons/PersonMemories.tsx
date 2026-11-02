import { useQuery } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import { BookHeart } from "lucide-react"
import { useState } from "react"

import { MemoriesService } from "@/client"
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

const PAGE_SIZE = 100

interface PersonMemoriesProps {
  personId: string
  personName: string
}

// The memories linked to this person, which are the ones its persona draws on. Only
// titles are shown here: the stories themselves stay on the Memories page.
const PersonMemories = ({ personId, personName }: PersonMemoriesProps) => {
  const [isOpen, setIsOpen] = useState(false)

  const memories = useQuery({
    queryKey: ["memories", "person", personId],
    queryFn: async () =>
      (
        await MemoriesService.readMemories({
          query: { person_id: personId, skip: 0, limit: PAGE_SIZE },
        })
      ).data,
    enabled: isOpen,
    retry: false,
    gcTime: 0,
  })

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenuItem
        onSelect={(e) => e.preventDefault()}
        onClick={() => setIsOpen(true)}
      >
        <BookHeart />
        Memories
      </DropdownMenuItem>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Memories of {personName}</DialogTitle>
          <DialogDescription>
            The memories linked to this person. The persona only uses the ones
            you have confirmed.
          </DialogDescription>
        </DialogHeader>

        {memories.isPending && (
          <p className="text-sm text-muted-foreground">Loading…</p>
        )}
        {memories.isError && (
          <p role="alert" className="text-sm text-destructive">
            Something went wrong. Please try again.
          </p>
        )}
        {memories.data && memories.data.data.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No memories are linked to this person yet. Link one from the
            Memories page.
          </p>
        )}
        {memories.data && memories.data.data.length > 0 && (
          <>
            <p className="text-sm text-muted-foreground">
              {memories.data.count}{" "}
              {memories.data.count === 1 ? "memory" : "memories"}
            </p>
            <ul aria-label="Linked memories" className="flex flex-col gap-2">
              {memories.data.data.map((memory) => (
                <li key={memory.id} className="rounded-lg border p-3 text-sm">
                  <span className="font-medium">{memory.title}</span>
                </li>
              ))}
            </ul>
            {memories.data.count > memories.data.data.length && (
              <p className="text-sm text-muted-foreground">
                Showing the latest {memories.data.data.length}. See all on the
                Memories page.
              </p>
            )}
          </>
        )}

        <DialogFooter>
          <Button variant="outline" asChild>
            <Link to="/memories">Open memories</Link>
          </Button>
          <DialogClose asChild>
            <Button variant="outline">Close</Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default PersonMemories
