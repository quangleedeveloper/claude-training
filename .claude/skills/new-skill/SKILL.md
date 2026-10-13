---
name: new-skill
description: Scaffold a new .claude/skills/<name>/SKILL.md file with the standard frontmatter and structure used in this template. Use when the user asks to create a new skill.
disable-model-invocation: false
---

Create a new Claude Code skill at `.claude/skills/<name>/SKILL.md` where `<name>` comes from $ARGUMENTS (use kebab-case).

Use this template:

```markdown
---
name: <skill-name>
description: <what the skill does and when Claude should invoke it>
---

<Instructions for Claude. Be specific about inputs ($ARGUMENTS), outputs, and steps.>
```

Steps:
1. Ask the user for the skill name if $ARGUMENTS is empty.
2. Ask for a description (used to auto-trigger the skill) and what it should do.
3. Ask if the skill has side effects — if yes, add `disable-model-invocation: true` to the frontmatter.
4. Write the file at `.claude/skills/<name>/SKILL.md` with the template above filled in.
5. Confirm the path and briefly describe when the skill will trigger.
