import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Search } from "lucide-react"
import { Suspense } from "react"

import { MemoriesService } from "@/client"
import { DataTable } from "@/components/Common/DataTable"
import AddMemory from "@/components/Memories/AddMemory"
import { columns } from "@/components/Memories/columns"
import PendingMemories from "@/components/Pending/PendingMemories"
import { APP_NAME } from "@/lib/brand"

function getMemoriesQueryOptions() {
  return {
    queryFn: async () =>
      (await MemoriesService.readMemories({ query: { skip: 0, limit: 100 } }))
        .data,
    queryKey: ["memories"],
  }
}

export const Route = createFileRoute("/_layout/memories")({
  component: Memories,
  head: () => ({
    meta: [
      {
        title: `Memories - ${APP_NAME}`,
      },
    ],
  }),
})

function MemoriesTableContent() {
  const { data: memories } = useSuspenseQuery(getMemoriesQueryOptions())

  if (memories.data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center text-center py-12">
        <div className="rounded-full bg-muted p-4 mb-4">
          <Search className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">
          You don't have any memories yet
        </h3>
        <p className="text-muted-foreground">Add a memory to get started</p>
      </div>
    )
  }

  return <DataTable columns={columns} data={memories.data} />
}

function MemoriesTable() {
  return (
    <Suspense fallback={<PendingMemories />}>
      <MemoriesTableContent />
    </Suspense>
  )
}

function Memories() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Memories</h1>
          <p className="text-muted-foreground">
            Preserve and manage your memories
          </p>
        </div>
        <AddMemory />
      </div>
      <MemoriesTable />
    </div>
  )
}
