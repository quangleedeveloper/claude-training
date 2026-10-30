import { useQuery } from "@tanstack/react-query"

import { PersonsService } from "@/client"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

// Select has no empty value, so "no person" gets a sentinel
export const NO_PERSON = "none"

interface PersonSelectProps {
  id: string
  value: string
  onChange: (value: string) => void
  disabled?: boolean
}

// Same key and shape as the People page, so the list is fetched once and shared
const PersonSelect = ({ id, value, onChange, disabled }: PersonSelectProps) => {
  const persons = useQuery({
    queryKey: ["persons"],
    queryFn: async () =>
      (await PersonsService.readPersons({ query: { skip: 0, limit: 100 } }))
        .data,
  })

  return (
    <Select value={value} onValueChange={onChange} disabled={disabled}>
      <SelectTrigger id={id}>
        <SelectValue placeholder="Choose a person" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={NO_PERSON}>No person</SelectItem>
        {persons.data?.data.map((person) => (
          <SelectItem key={person.id} value={person.id}>
            {person.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

export default PersonSelect
