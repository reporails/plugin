# Explain — Rule Detail Lookup

Explain what one rule checks and how to satisfy it, for the rule ID given in `$ARGUMENTS`.

## Input

Read the rule ID from `$ARGUMENTS`, where a rule ID takes the three-part form `<pack>:<category>:<number>`, such as `CORE:C:0013` or `CLAUDE:S:0005`.

Ask the user which rule ID to explain when `$ARGUMENTS` names none, before calling `explain`.

## MCP path (preferred)

Check the tool list for the `reporails` MCP `explain` tool first (its name ends in `reporails__explain`).
Take the setup offer from [`setup.md`](setup.md) when the tool is missing.

1. Call `explain` with `rule_id` set to the rule ID from `$ARGUMENTS`.
2. Read the reply's markdown body: the rule's title and severity on the first lines, then its statement, its `## Antipatterns` and `## Limitations` sections, its Pass / Fail examples, and its `Checks:` list.

## CLI path (fallback)

Run `ails explain <rule_id>` from the project directory when the MCP `explain` tool is still unavailable after the setup offer:

```bash
ails explain CORE:C:0013
```

Run `npx @reporails/cli explain <rule_id>` instead when the `ails` binary is not installed:

```bash
npx @reporails/cli explain CORE:C:0013
```

## Output format

Relay the `explain` reply as the user's answer, unedited.
Keep its title and severity line, its statement, its Antipatterns, its Limitations, its Pass / Fail examples, and its `Checks:` list.
Keep them in the order the `explain` reply gives them.
