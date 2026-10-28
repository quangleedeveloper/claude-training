import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Search } from "lucide-react"
import { Suspense } from "react"

import { PersonsService } from "@/client"
import { DataTable } from "@/components/Common/DataTable"
import PendingPersons from "@/components/Pending/PendingPersons"
import AddPerson from "@/components/Persons/AddPerson"
import { columns } from "@/components/Persons/columns"
import { APP_NAME } from "@/lib/brand"

function getPersonsQueryOptions() {
  return {
    queryFn: async () =>
      (await PersonsService.readPersons({ query: { skip: 0, limit: 100 } }))
        .data,
    queryKey: ["persons"],
  }
}

export const Route = createFileRoute("/_layout/persons")({
  component: Persons,
  head: () => ({
    meta: [
      {
        title: `People - ${APP_NAME}`,
      },
    ],
  }),
})

function PersonsTableContent() {
  const { data: persons } = useSuspenseQuery(getPersonsQueryOptions())

  if (persons.data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center text-center py-12">
        <div className="rounded-full bg-muted p-4 mb-4">
          <Search className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">You don't have any people yet</h3>
        <p className="text-muted-foreground">Add a person to get started</p>
      </div>
    )
  }

  return <DataTable columns={columns} data={persons.data} />
}

function PersonsTable() {
  return (
    <Suspense fallback={<PendingPersons />}>
      <PersonsTableContent />
    </Suspense>
  )
}

function Persons() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">People</h1>
          <p className="text-muted-foreground">
            The people your family remembers
          </p>
        </div>
        <AddPerson />
      </div>
      <PersonsTable />
    </div>
  )
}
