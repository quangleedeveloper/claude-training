// The form edits "other names" as one comma-separated field ("Mom, Mẹ"); the API
// wants a list. The server trims and drops duplicates again, this just splits.
export const MAX_OTHER_NAMES = 10

export const parseOtherNames = (text: string): string[] =>
  text
    .split(",")
    .map((name) => name.trim())
    .filter((name) => name.length > 0)

export const formatOtherNames = (names: string[]): string => names.join(", ")
