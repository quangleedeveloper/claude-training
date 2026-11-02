import { createFileRoute } from "@tanstack/react-router"

import ChatWindow from "@/components/Chat/ChatWindow"
import { APP_NAME } from "@/lib/brand"

export const Route = createFileRoute("/_layout/chat/$personId")({
  component: Chat,
  head: () => ({
    meta: [
      {
        title: `Chat - ${APP_NAME}`,
      },
    ],
  }),
})

function Chat() {
  const { personId } = Route.useParams()

  return <ChatWindow personId={personId} />
}
