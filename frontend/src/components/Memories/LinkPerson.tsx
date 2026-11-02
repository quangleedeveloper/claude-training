import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { UserRound } from "lucide-react"
import { useState } from "react"

import { MemoriesService, type MemoryPublic, PersonsService } from "@/client"
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
import { Label } from "@/components/ui/label"
import { LoadingButton } from "@/components/ui/loading-button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
import { NO_PERSON } from "./PersonSelect"

interface LinkPersonProps {
  memory: MemoryPublic
  onSuccess: () => void
}

const LinkPerson = ({ memory, onSuccess }: LinkPersonProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const [selected, setSelected] = useState(memory.person_id ?? NO_PERSON)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const { data: persons } = useQuery({
    queryKey: ["persons"],
    queryFn: async () =>
      (await PersonsService.readPersons({ query: { skip: 0, limit: 100 } }))
        .data,
    enabled: isOpen,
  })

  const mutation = useMutation({
    mutationFn: (personId: string) =>
      MemoriesService.linkMemoryPerson({
        path: { id: memory.id },
        body: { person_id: personId === NO_PERSON ? null : personId },
      }),
    onSuccess: () => {
      showSuccessToast(
        selected === NO_PERSON
          ? "Memory unlinked from person"
          : "Memory linked to person",
      )
      setIsOpen(false)
      onSuccess()
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["memories"] })
    },
  })

  const onOpenChange = (open: boolean) => {
    setIsOpen(open)
    if (open) setSelected(memory.person_id ?? NO_PERSON)
  }

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DropdownMenuItem
        onSelect={(e) => e.preventDefault()}
        onClick={() => onOpenChange(true)}
      >
        <UserRound />
        Link Person
      </DropdownMenuItem>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Link Person</DialogTitle>
          <DialogDescription>
            Choose the person this memory is about. Add people from the People
            page.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-2 py-4">
          <Label htmlFor={`link-person-${memory.id}`}>Person</Label>
          <Select value={selected} onValueChange={setSelected}>
            <SelectTrigger id={`link-person-${memory.id}`}>
              <SelectValue placeholder="Choose a person" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NO_PERSON}>No person</SelectItem>
              {persons?.data.map((person) => (
                <SelectItem key={person.id} value={person.id}>
                  {person.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline" disabled={mutation.isPending}>
              Cancel
            </Button>
          </DialogClose>
          <LoadingButton
            type="button"
            loading={mutation.isPending}
            onClick={() => mutation.mutate(selected)}
          >
            Save
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default LinkPerson
