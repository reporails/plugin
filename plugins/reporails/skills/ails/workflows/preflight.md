# Preflight Workflow — `/reporails:ails preflight <capability>`

Fetch the framework rule set with `preflight` for a capability before authoring that file.
Write content that satisfies the `preflight` rules from the start.

## When to use

- About to create a new `SKILL.md` file for a Claude skill.
- About to define a new `.claude/agents/<name>.md` agent file.
- About to author a new `.claude/rules/<slug>.md` rule file.
- About to draft a `CLAUDE.md`, `AGENTS.md`, or similar root instruction file.
- Asked to "write a skill for …", "build an agent that …", or "add a rule about …".

Use `/reporails:ails check` or `/reporails:ails heal` instead when the file already exists and you are patching its findings.

## Inputs

- `$ARGUMENTS` — the capability keyword: `skill`, `agent`, `rule`, `main`, or `memory`. Singular and plural forms both work.

## Steps

1. Extract the capability keyword from `$ARGUMENTS`.
   Ask the user which capability they are authoring when `$ARGUMENTS` names none or an unrecognized word.

2. Detect the environment with the same fallback chain the rest of `/reporails:ails` uses:
   - the reporails MCP `preflight` tool (its name ends in `reporails__preflight`), preferred — call it with `capability` (required) and `agent` (optional)
   - the one-time setup from [`setup.md`](setup.md), offered when that tool is missing
   - `ails rules list --capability <capability> -f md` when `ails` is on `PATH`
   - `npx @reporails/cli@0.6 rules list --capability <capability> -f md` otherwise

3. Fetch the rule set:
   - MCP: call `preflight` with `capability: <capability>` and, when the agent is known, `agent: <agent>`.
   - CLI fallback, only if MCP is still not available after the setup offer:
     ```bash
     ails rules list --capability <capability> --agent <agent> -f md
     ```
   The default `-f md` format includes Pass / Fail example blocks.
   Add `--no-examples` to the fetch command when context budget is tight.

4. Present the fetched rules as the authoring context, giving each rule its fields:
   - `category` (`structure` / `direction` / `coherence` / `efficiency` / `maintenance` / `governance`) — sets workflow order
   - `severity` (`critical` / `high` / `medium` / `low`) — orders rules within a category
   - title and short description
   - Pass / Fail example, when the rule carries one

5. Write the file, working the rules in workflow order: `structure` first (frontmatter, file path, links resolve), then `direction`, `coherence`, `efficiency`, `maintenance`, `governance`.

6. Run `/reporails:ails check <capability>:<name>` once the draft is on disk.
   Re-read the `preflight` rule body for a content-quality finding the draft missed.
   File a separate issue for a genuine novel case the `preflight` rule set does not yet cover.
   *Do not expect most findings to appear, because the `preflight` rules already caught them before writing.*

## Workflow order

Address the rules in this order, because the `preflight` rule set is sorted:

1. `structure` — frontmatter declared, file location correct, links and imports resolve. Nothing downstream works when these fail.
2. `direction` — directive instructions stay clear, with no ambiguity, so the agent knows what to do.
3. `coherence` — content stays consistent, with no contradictions and one source of truth.
4. `efficiency` — content stays within context budget, with no bloat.
5. `maintenance` — content stays fresh, with no stale references.
6. `governance` — content stays aligned with policy.

Work the `category` rules in this order, `structure` first, for a near-zero-findings draft on the first try.
*Do not write content before checking `structure`, which creates rework.*

## Output

Present the rule set as a numbered list grouped by `category`, with each rule's Pass / Fail example inline.
Write the authored `<capability>` file next.
Run `/reporails:ails check <capability>:<name>` after writing.
That single target token narrows the run to the file you just wrote.
Report the resulting `check` score against the 7.0 target.
Report every remaining `check` finding tied back to its violated rule, with the next step for each.

## Failure modes

- Capability unknown: ask the user to clarify which `capability` they mean. `skill`, `agent`, `rule`, and `main` are the most common.
- Rule set empty: the `capability` is not declared in the detected agent's config, most often a typo; ask the user to confirm the `capability`.
- MCP `preflight` returns an error: fall through to the CLI `ails rules list` command, then to `npx @reporails/cli@0.6`.
