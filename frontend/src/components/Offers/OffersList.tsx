import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import { Inbox } from "lucide-react"
import { useState } from "react"

import { PersonsService } from "@/client"
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
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

interface OffersListProps {
  personId: string
  personName: string
}

// Owner only: it is mounted from the owner's people menu, and the API refuses anyone
// else. Offer text is private family data: shown here, never logged or stored.
const OffersList = ({ personId, personName }: OffersListProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const [declining, setDeclining] = useState<string | null>(null)
  const [accepted, setAccepted] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const queryKey = ["offers", personId]

  const offers = useQuery({
    queryKey,
    queryFn: async () =>
      (await PersonsService.readOffers({ path: { id: personId } })).data,
    enabled: isOpen,
    retry: false,
    gcTime: 0,
  })

  const accept = useMutation({
    mutationFn: (offerId: string) =>
      PersonsService.acceptOffer({
        path: { id: personId, offer_id: offerId },
      }),
    onSuccess: () => setAccepted(true),
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey })
      queryClient.invalidateQueries({ queryKey: ["memories"] })
    },
  })

  const decline = useMutation({
    mutationFn: (offerId: string) =>
      PersonsService.declineOffer({
        path: { id: personId, offer_id: offerId },
      }),
    onSuccess: () => {
      showSuccessToast("The offer was declined")
      setDeclining(null)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => queryClient.invalidateQueries({ queryKey }),
  })

  const open = (value: boolean) => {
    setIsOpen(value)
    if (!value) {
      setAccepted(false)
      setDeclining(null)
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={open}>
      <DropdownMenuItem
        onSelect={(e) => e.preventDefault()}
        onClick={() => setIsOpen(true)}
      >
        <Inbox />
        Offers
      </DropdownMenuItem>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Offered memories</DialogTitle>
          <DialogDescription>
            Memories others offered about {personName}. Accept one to add it to
            your memories; the persona uses it only after you confirm it.
          </DialogDescription>
        </DialogHeader>

        {accepted && (
          <p role="status" className="rounded-lg border p-3 text-sm">
            A new memory was created and is not yet confirmed.{" "}
            <Link to="/memories" className="underline">
              Open memories
            </Link>
          </p>
        )}
        {offers.isPending && (
          <p className="text-sm text-muted-foreground">Loading…</p>
        )}
        {offers.isError && (
          <p role="alert" className="text-sm text-destructive">
            Something went wrong. Please try again.
          </p>
        )}
        {offers.data && offers.data.data.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No offers are waiting.
          </p>
        )}
        {offers.data && offers.data.data.length > 0 && (
          <ul aria-label="Offers" className="flex flex-col gap-3">
            {offers.data.data.map((offer) => (
              <li key={offer.id} className="rounded-lg border p-3">
                <p className="whitespace-pre-wrap text-sm">{offer.content}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  From {offer.from_name}
                </p>
                {declining === offer.id ? (
                  <div className="mt-3 flex items-center justify-end gap-2">
                    <span className="mr-auto text-sm">Decline this offer?</span>
                    <Button
                      variant="outline"
                      disabled={decline.isPending}
                      onClick={() => setDeclining(null)}
                    >
                      Keep
                    </Button>
                    <LoadingButton
                      variant="destructive"
                      loading={decline.isPending}
                      onClick={() => decline.mutate(offer.id)}
                    >
                      Confirm decline
                    </LoadingButton>
                  </div>
                ) : (
                  <div className="mt-3 flex justify-end gap-2">
                    <Button
                      variant="outline"
                      disabled={accept.isPending}
                      onClick={() => setDeclining(offer.id)}
                    >
                      Decline
                    </Button>
                    <LoadingButton
                      loading={accept.isPending}
                      onClick={() => accept.mutate(offer.id)}
                    >
                      Accept
                    </LoadingButton>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline">Close</Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default OffersList
