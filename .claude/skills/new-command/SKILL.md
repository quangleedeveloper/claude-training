---
name: new-command
description: Scaffold a new .claude/commands/<name>.md file with the standard frontmatter and structure used in this template. Use when the user asks to create a new slash command.
---

Create a new Claude Code custom command file at `.claude/commands/<name>.md` where `<name>` comes from $ARGUMENTS (use kebab-case).

Use this template:

```markdown
---
description: <one-line description of what the command does>
---

# <Command Title>

<Instructions for Claude when this command is invoked. Be specific about inputs, outputs, and format.>
```

Steps:
1. Ask the user for the command name if $ARGUMENTS is empty.
2. Ask for a one-line description and what the command should do.
3. Write the file at `.claude/commands/<name>.md` with the template above filled in.
4. Confirm the path and briefly describe what the command does and how to invoke it (`/<name>`).
