import type { ColumnDef } from "@tanstack/react-table"

import type { MemoryPublic } from "@/client"
import type { DataTableFeatures } from "@/components/Common/DataTable"
import { MemoryActionsMenu } from "./MemoryActionsMenu"
import PersonCell from "./PersonCell"

export const columns: ColumnDef<DataTableFeatures, MemoryPublic>[] = [
  {
    accessorKey: "title",
    header: "Title",
    cell: ({ row }) => (
      <span className="font-medium">{row.original.title}</span>
    ),
  },
  {
    accessorKey: "person_id",
    header: "Person",
    cell: ({ row }) => <PersonCell personId={row.original.person_id} />,
  },
  {
    accessorKey: "content",
    header: "Memory",
    cell: ({ row }) => (
      <span className="max-w-md truncate block text-muted-foreground">
        {row.original.content}
      </span>
    ),
  },
  {
    id: "actions",
    header: () => <span className="sr-only">Actions</span>,
    cell: ({ row }) => (
      <div className="flex justify-end">
        <MemoryActionsMenu memory={row.original} />
      </div>
    ),
  },
]
