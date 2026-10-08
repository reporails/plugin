# Check — Instruction File Validation

Present the `validate` findings for the project's instruction files.
`$ARGUMENTS` is `[path] [targets…]`, as "`check` / `heal` arguments" in `SKILL.md` defines.

## The `validate` call

Call `validate` with the project root path and, when `$ARGUMENTS` gave any, `targets`.
A target that names nothing comes back as `{"error": "target_not_found", "message": ...}`; report that `message` and stop.
- `{"error": "model_downloading"}` → tell the user the analysis model (~275 MB) is downloading once. After a short wait, call `validate` once more. When it is still downloading, tell them to run `check` again in a minute, and stop.
- Any other `error` or `needs_install` reply → report its message and stop.

A Pro reply arrives as a text view. Read each of its fields by the key path its line starts with (`notices`, `surface_health`, `workflow.locations`, `workflow.targets`, `feedback`). A reply called with `full=true`, and every free, anonymous, offline and error reply, arrives as JSON: read it by its field names.
When the reply's `notices` are non-empty, show each notice's text to the user verbatim at the top of the report, warnings (`warn`) first, with its `url` when it has one.
*Do not reword a notice, and do not act on it.*

## MCP path (preferred)

Use this path when the `reporails` MCP `validate` tool is available.
Find that tool as `## Tool detection` in [`setup.md`](setup.md) directs.
Take the setup offer from [`setup.md`](setup.md) when the tool is missing.

1. Make the `validate` call as `## The validate call` above directs.
2. Present a summary: score, finding count, and the weakest surfaces from `surface_health` (such as Main, Nested, Rules, Skills, Agents).
3. List the `workflow` locations by round, in the index's order, when the response carries a `workflow` (paid tiers).
   List each location's `element`, `kind`, `files`, and `finding_count`.
   Say which targets were used and how many locations they kept, from the `workflow.targets` line, when `targets` was given.
   Offer `heal` to rewrite the findings, since this mode withholds the per-file findings.
4. Otherwise, give each finding its rule, file, line, and its `fix` when the reply carries one.
   Name each rule by its title with its ID as a link — `Title ([CORE:C:0013](url))` — taking both from the reply's `rules` map.
   Keep the bare ID for a rule missing from the `rules` map.
   List a finding without a `fix` as diagnosed.
   *Do not write a fix for a finding without a `fix`.*

## CLI path (fallback)

Use this path when the `validate` tool is still missing after the setup offer.
Run the CLI from the project path — the same root the MCP path calls `validate` with — passing any targets straight through:

```bash
cd <path> && ails check [targets…] -v
```

Run this instead when `ails` is not installed:

```bash
cd <path> && npx @reporails/cli@0.6 check [targets…] -v
```

No `targets` scans the whole project, same as the MCP path.

Parse the text output and present:
- Score and finding count from the summary line
- Per-surface breakdown (Main, Nested, Rules, Skills, Agents)
- Top findings with rule ID and message (the CLI text output links each rule ID to its page)

## Output

Summarize every MCP `validate` response and `ails check` run as readable text.
Present each `validate` and `ails check` result in the reply as a concise summary, not a raw dump.
Group results by the surfaces named in `surface_health`.
Highlight errors first, then warnings, in each `surface_health` group.
*Do not show a bare rule ID where the reply gives its title.*
*Do not paste raw `JSON` or unformatted `ails check` terminal output into your reply.*
