import { useQuery } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import { MessageCircle } from "lucide-react"

import { PersonsService } from "@/client"
import { Button } from "@/components/ui/button"

// Name only: a member may talk with the persona but never sees the person record,
// its owner or any memory (memorial-privacy rule 2)
const SharedWithMe = () => {
  const shared = useQuery({
    queryKey: ["persons", "shared"],
    queryFn: async () => (await PersonsService.readSharedPersons()).data,
    retry: false,
    // Always ask again, so a revoked person is gone on the next visit
    gcTime: 0,
  })

  if (shared.isPending) {
    return <p className="text-muted-foreground">Loading…</p>
  }
  if (shared.isError) {
    return (
      <p role="alert" className="text-destructive">
        Something went wrong. Please try again.
      </p>
    )
  }
  if (shared.data.data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <h3 className="text-lg font-semibold">
          Nothing is shared with you yet
        </h3>
        <p className="text-muted-foreground">
          When a family invites you, their persona appears here.
        </p>
      </div>
    )
  }

  return (
    <ul aria-label="Shared with me" className="flex flex-col gap-3">
      {shared.data.data.map((person) => (
        <li
          key={person.id}
          className="flex items-center justify-between gap-4 rounded-lg border p-4"
        >
          <span className="font-medium">{person.name}</span>
          <Button asChild variant="outline">
            <Link to="/chat/$personId" params={{ personId: person.id }}>
              <MessageCircle />
              Talk
            </Link>
          </Button>
        </li>
      ))}
    </ul>
  )
}

export default SharedWithMe
