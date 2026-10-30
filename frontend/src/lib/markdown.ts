// A memory's text is stored as Markdown. Places that show it in one line (the table)
// want the words without the syntax, so strip the few marks the editor can write.
export const markdownToPlainText = (markdown: string): string =>
  markdown
    .replace(/^\s{0,3}(#{1,6}|>|[-*+]|\d+\.)\s+/gm, "")
    .replace(/(\*\*|__|\*|_)(\S(?:[\s\S]*?\S)?)\1/g, "$2")
    .replace(/\\([\\`*_{}[\]()#+\-.!>])/g, "$1")
    .replace(/\s*\n+\s*/g, " ")
    .trim()
