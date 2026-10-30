import { Markdown } from "@tiptap/markdown"
import { EditorContent, useEditor } from "@tiptap/react"
import StarterKit from "@tiptap/starter-kit"
import {
  Bold,
  Heading2,
  Italic,
  List,
  ListOrdered,
  type LucideIcon,
  Quote,
} from "lucide-react"
import { useEffect } from "react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

interface MemoryEditorProps {
  // The story as Markdown: the same `content` text the API stores and the AI reads
  value: string
  onChange: (markdown: string) => void
  onBlur?: () => void
  label: string
  disabled?: boolean
  invalid?: boolean
}

interface ToolbarAction {
  label: string
  icon: LucideIcon
  isActive: () => boolean
  run: () => void
}

const MemoryEditor = ({
  value,
  onChange,
  onBlur,
  label,
  disabled,
  invalid,
}: MemoryEditorProps) => {
  const editor = useEditor({
    // No links, images, code or underline: only what the toolbar offers
    extensions: [
      StarterKit.configure({
        code: false,
        codeBlock: false,
        horizontalRule: false,
        link: false,
        strike: false,
        underline: false,
      }),
      Markdown,
    ],
    content: value,
    contentType: "markdown",
    editable: !disabled,
    immediatelyRender: false,
    // The toolbar shows which formats are on, so it must follow every transaction
    shouldRerenderOnTransaction: true,
    editorProps: {
      attributes: {
        role: "textbox",
        "aria-label": label,
        "aria-multiline": "true",
        "aria-invalid": invalid ? "true" : "false",
        class:
          "min-h-32 max-h-80 overflow-y-auto px-3 py-2 text-sm outline-none [&_blockquote]:border-l-2 [&_blockquote]:pl-3 [&_blockquote]:text-muted-foreground [&_h2]:text-base [&_h2]:font-semibold [&_ol]:list-decimal [&_ol]:pl-5 [&_ul]:list-disc [&_ul]:pl-5",
      },
    },
    onUpdate: ({ editor: current }) => onChange(current.getMarkdown()),
    onBlur: () => onBlur?.(),
  })

  // Follow the form when it changes the value from outside (reset after a save)
  useEffect(() => {
    if (!editor || editor.getMarkdown() === value) return
    editor.commands.setContent(value, {
      contentType: "markdown",
      emitUpdate: false,
    })
  }, [editor, value])

  useEffect(() => {
    editor?.setEditable(!disabled)
  }, [editor, disabled])

  if (!editor) return null

  const actions: ToolbarAction[] = [
    {
      label: "Bold",
      icon: Bold,
      isActive: () => editor.isActive("bold"),
      run: () => editor.chain().focus().toggleBold().run(),
    },
    {
      label: "Italic",
      icon: Italic,
      isActive: () => editor.isActive("italic"),
      run: () => editor.chain().focus().toggleItalic().run(),
    },
    {
      label: "Heading",
      icon: Heading2,
      isActive: () => editor.isActive("heading", { level: 2 }),
      run: () => editor.chain().focus().toggleHeading({ level: 2 }).run(),
    },
    {
      label: "Bulleted list",
      icon: List,
      isActive: () => editor.isActive("bulletList"),
      run: () => editor.chain().focus().toggleBulletList().run(),
    },
    {
      label: "Numbered list",
      icon: ListOrdered,
      isActive: () => editor.isActive("orderedList"),
      run: () => editor.chain().focus().toggleOrderedList().run(),
    },
    {
      label: "Quote",
      icon: Quote,
      isActive: () => editor.isActive("blockquote"),
      run: () => editor.chain().focus().toggleBlockquote().run(),
    },
  ]

  return (
    <div
      className={cn(
        "rounded-md border bg-transparent shadow-xs focus-within:border-ring focus-within:ring-[3px] focus-within:ring-ring/50",
        invalid && "border-destructive",
        disabled && "opacity-50",
      )}
    >
      <div
        role="toolbar"
        aria-label={`${label} formatting`}
        className="flex flex-wrap gap-1 border-b p-1"
      >
        {actions.map((action) => (
          <Button
            key={action.label}
            type="button"
            variant={action.isActive() ? "secondary" : "ghost"}
            size="icon"
            className="size-8"
            aria-label={action.label}
            aria-pressed={action.isActive()}
            disabled={disabled}
            // Keep the selection in the editor when a toolbar button is pressed
            onMouseDown={(event) => event.preventDefault()}
            onClick={action.run}
          >
            <action.icon />
          </Button>
        ))}
      </div>
      <EditorContent editor={editor} />
    </div>
  )
}

export default MemoryEditor
