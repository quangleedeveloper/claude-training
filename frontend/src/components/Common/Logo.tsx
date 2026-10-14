import { Link } from "@tanstack/react-router"

import { cn } from "@/lib/utils"

const PROJECT_NAME = "Memorial Robot"

interface LogoProps {
  variant?: "full" | "icon" | "responsive"
  className?: string
  asLink?: boolean
}

function Wordmark({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "text-lg font-semibold tracking-tight whitespace-nowrap",
        className,
      )}
    >
      {PROJECT_NAME}
    </span>
  )
}

function Monogram({ className }: { className?: string }) {
  return (
    <span
      role="img"
      aria-label={PROJECT_NAME}
      className={cn(
        "bg-primary text-primary-foreground inline-flex size-5 items-center justify-center rounded text-[10px] font-bold",
        className,
      )}
    >
      MR
    </span>
  )
}

export function Logo({
  variant = "full",
  className,
  asLink = true,
}: LogoProps) {
  const content =
    variant === "responsive" ? (
      <>
        <Wordmark
          className={cn("group-data-[collapsible=icon]:hidden", className)}
        />
        <Monogram
          className={cn("hidden group-data-[collapsible=icon]:flex", className)}
        />
      </>
    ) : variant === "full" ? (
      <Wordmark className={className} />
    ) : (
      <Monogram className={className} />
    )

  if (!asLink) {
    return content
  }

  return <Link to="/">{content}</Link>
}
