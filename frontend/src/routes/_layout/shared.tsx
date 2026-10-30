import { createFileRoute } from "@tanstack/react-router"

import SharedWithMe from "@/components/Sharing/SharedWithMe"
import { APP_NAME } from "@/lib/brand"

export const Route = createFileRoute("/_layout/shared")({
  component: Shared,
  head: () => ({
    meta: [
      {
        title: `Shared with me - ${APP_NAME}`,
      },
    ],
  }),
})

function Shared() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Shared with me</h1>
        <p className="text-muted-foreground">
          Personas other families invited you to talk with
        </p>
      </div>
      <SharedWithMe />
    </div>
  )
}
