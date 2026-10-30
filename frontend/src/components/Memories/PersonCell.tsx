import { useQuery } from "@tanstack/react-query"

import { PersonsService } from "@/client"

interface PersonCellProps {
  personId: string | null | undefined
}

// Same key and shape as the People page, so the list is fetched once and shared.
// The name comes from the person record, so renaming a person shows here at once.
const PersonCell = ({ personId }: PersonCellProps) => {
  const persons = useQuery({
    queryKey: ["persons"],
    queryFn: async () =>
      (await PersonsService.readPersons({ query: { skip: 0, limit: 100 } }))
        .data,
    enabled: Boolean(personId),
  })

  if (!personId) {
    return <span className="text-muted-foreground">Not linked</span>
  }
  const person = persons.data?.data.find(
    (candidate) => candidate.id === personId,
  )
  return <span>{person?.name ?? "…"}</span>
}

export default PersonCell
