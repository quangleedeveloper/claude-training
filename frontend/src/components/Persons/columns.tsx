import type { ColumnDef } from "@tanstack/react-table"

import type { PersonPublic } from "@/client"
import type { DataTableFeatures } from "@/components/Common/DataTable"
import { formatOtherNames } from "@/lib/personNames"
import { PersonActionsMenu } from "./PersonActionsMenu"

export const columns: ColumnDef<DataTableFeatures, PersonPublic>[] = [
  {
    accessorKey: "name",
    header: "Name",
    cell: ({ row }) => <span className="font-medium">{row.original.name}</span>,
  },
  {
    accessorKey: "other_names",
    header: "Other names",
    cell: ({ row }) => (
      <span className="text-muted-foreground">
        {formatOtherNames(row.original.other_names ?? []) || "None"}
      </span>
    ),
  },
  {
    id: "actions",
    header: () => <span className="sr-only">Actions</span>,
    cell: ({ row }) => (
      <div className="flex justify-end">
        <PersonActionsMenu person={row.original} />
      </div>
    ),
  },
]
