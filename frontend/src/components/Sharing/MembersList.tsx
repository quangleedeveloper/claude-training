import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"

import { PersonsService } from "@/client"
import { Button } from "@/components/ui/button"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

interface MembersListProps {
  personId: string
}

// Owner only. The list shows the people the owner chose, by name and email.
const MembersList = ({ personId }: MembersListProps) => {
  const [revoking, setRevoking] = useState<string | null>(null)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const queryKey = ["members", personId]

  const members = useQuery({
    queryKey,
    queryFn: async () =>
      (await PersonsService.readMembers({ path: { id: personId } })).data,
    retry: false,
    gcTime: 0,
  })

  const revoke = useMutation({
    mutationFn: (userId: string) =>
      PersonsService.revokeMember({
        path: { id: personId, user_id: userId },
      }),
    onSuccess: () => {
      showSuccessToast("Access was removed")
      setRevoking(null)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => queryClient.invalidateQueries({ queryKey }),
  })

  if (members.isPending) {
    return <p className="text-sm text-muted-foreground">Loading…</p>
  }
  if (members.isError) {
    return (
      <p role="alert" className="text-sm text-destructive">
        Something went wrong. Please try again.
      </p>
    )
  }
  if (members.data.data.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Nobody else can talk with this persona yet.
      </p>
    )
  }

  return (
    <ul aria-label="Members" className="flex flex-col gap-3">
      {members.data.data.map((member) => (
        <li key={member.user_id} className="rounded-lg border p-3">
          <p className="text-sm font-medium">
            {member.full_name || member.email}
          </p>
          {member.full_name && (
            <p className="text-xs text-muted-foreground">{member.email}</p>
          )}
          {revoking === member.user_id ? (
            <div className="mt-3 flex flex-col gap-2">
              <p className="text-sm">
                Their open chat ends and the note we kept of what they talked
                about is deleted. Revoke access?
              </p>
              <div className="flex justify-end gap-2">
                <Button
                  variant="outline"
                  disabled={revoke.isPending}
                  onClick={() => setRevoking(null)}
                >
                  Keep access
                </Button>
                <LoadingButton
                  variant="destructive"
                  loading={revoke.isPending}
                  onClick={() => revoke.mutate(member.user_id)}
                >
                  Confirm revoke
                </LoadingButton>
              </div>
            </div>
          ) : (
            <div className="mt-3 flex justify-end">
              <Button
                variant="outline"
                onClick={() => setRevoking(member.user_id)}
              >
                Revoke
              </Button>
            </div>
          )}
        </li>
      ))}
    </ul>
  )
}

export default MembersList
