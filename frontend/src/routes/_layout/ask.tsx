import { createFileRoute } from "@tanstack/react-router"

import AskMemories from "@/components/Ask/AskMemories"
import { APP_NAME } from "@/lib/brand"

export const Route = createFileRoute("/_layout/ask")({
  component: Ask,
  head: () => ({
    meta: [
      {
        title: `Ask - ${APP_NAME}`,
      },
    ],
  }),
})

function Ask() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Ask</h1>
        <p className="text-muted-foreground">
          Ask a question and get an answer from your memories
        </p>
      </div>
      <AskMemories />
    </div>
  )
}
