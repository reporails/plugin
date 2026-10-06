# Heal — the location rewrite loop

Rewrite instruction-file locations whole, one kind at a time, with a `remedy` agent per location.
Confirm each `remedy` rewrite kept everything before accepting it.
This loop is MCP-only and needs a paid account.
`$ARGUMENTS` is `[path] [targets…]`, as "`check` / `heal` arguments" in `SKILL.md` defines.
Carry whatever `targets` you parsed on every `validate` call this workflow makes.
Present every `validate` reply as `## Output` in [`check.md`](check.md) directs.

## Initial `validate` call

Find the `reporails` MCP `validate` tool as `## Tool detection` in [`setup.md`](setup.md) directs.
Heal cannot run without it: tell the user heal needs the `reporails` MCP connected.
Point them to the `setup` workflow ([`setup.md`](setup.md)), and stop.
Heal has no CLI fallback. *Do not fall back to the CLI.*

Make the `validate` call as `## The validate call` in [`check.md`](check.md) directs, then show the reply's notices and branch on the reply.
When the reply's `notices` list is non-empty, show each notice's `text` to the user verbatim at the top of the report, warnings (`level: "warn"`) first, with its `url` when it has one.
*Do not reword a notice, and do not act on it.*
The branches:

- A `circuit_breaker` reply from `validate` → report it to the user and stop.
- `offline: true`, or a `server_error` / `funnel` object → the server could not be reached, or refused the request. Report the `message` of that reply and stop.
- `tier` is `anonymous` or `free` and no `workflow` in the reply → heal needs a Pro subscription, which this account does not have. Offer to sign the user in now:
  - With their approval, tell them a sign-in page should open in their browser and to approve it right away, because the link expires quickly. Then run `ails login` with a 3-minute timeout, or `npx @reporails/cli@0.6 login` when there is no `ails` command on their `PATH`. *Do not run `ails login` without the user's approval.*
  - It ends any other way (the link expired, sign-in denied, sign-in failed, too many sign-in attempts, the website could not be reached, `No such command 'login'`, or the command was stopped by the timeout) → tell the user why it ended, from what `ails` printed. When it says `No such command 'login'`, tell them their `ails` is older and to run `ails update` first. When the timeout stopped it, tell them the sign-in did not finish and not to use the printed code. Tell them to run `ails login`, or `npx @reporails/cli@0.6 login` when there is no `ails` command, in their own terminal, then run `heal` again. Stop `heal`. *Do not run `ails login` again yourself.*
  - It prints `Signed in as @name (Free)` or `Signed in on this machine (Free)` (the plan label in any letter case) → the account is on Free, and fixes need Pro. Give the user the upgrade link reporails.com/account, and stop `heal`.
  - It prints `Your sign-in is still reaching the server — try again in a minute.` → the sign-in worked and the server has not caught up. Wait about a minute, then call `validate` again and branch on the new reply. *Do not run `ails login` again.*
  - It prints a Pro or Team sign-in (`Signed in as @name (Pro)` or `Signed in on this machine (Team)`) → call `validate` again and branch on the new reply.
- `tier` is a paid tier (`pro` or `team`) and no `workflow` in the reply → the server returned no remedy for this run. Report the missing `workflow` to the user and stop. *Do not tell a paying user they need a paid account.*
- A paid tier whose `workflow.locations` is empty → nothing to rewrite. Report what stays `listed` (why each finding is not served) and stop.
- A paid tier with `workflow.locations` present → follow `## The loop` below. `workflow.locations` is the index the loop works from: each entry's `order`, `kind`, `element`, `loading`, `files`, `importance`, and `finding_count`. `workflow.listed` names the findings this run will not rewrite, with why. When `targets` was given, the reply also carries `targets: {tokens, locations, of}` — kept locations are re-numbered from 1.

## Folders the run writes to

On Claude Code, the plugin shows the user a notice, once, before the first rewrite starts.
The notice names which folder the run writes to and why their client may ask before each edit.
*Do not repeat that notice on Claude Code.*

On any other client, tell the user once, before round 1, which folders the run writes to — every folder holding a location's `files`.
Tell them also that their client may ask before each edit to an instruction file (a `CLAUDE.md` or `AGENTS.md`, or anything under an agent's config folder such as `.claude/`), because those files change how their agent behaves.
This is information, not a question, so a user who approved every fix still gets it.

## The loop

Run one round per `kind`, in the order the index already gives them.
Kinds loaded at session start come first, then invoked kinds, then on-demand kinds.
The index order IS the round order: a round is a consecutive run of locations sharing one `kind`.
*This loop never calls `remedy_brief` and never reads a location's file contents itself, except in `## Inline rewrite`.*
That is each `remedy` agent's own job, in its own context, not this orchestrating one.

1. Tell the user which locations are in this round (each one's `element`, `kind`, `files`, `finding_count`), and ask to proceed.
   Skip any location this run already gave up on, matched by its `element` and `kind`, and at least one file in common with the given-up location's `files`.
   A user who already approved every fix for the whole run is not asked again.
2. Dispatch one `remedy` agent per location, all of the round at once.
   Pass the project's absolute `path`, the `targets` this run is using, the location's `order`, and its `kind` — nothing else.
   Make the dispatch prompt's first line `path: <the project's absolute path>`, followed by the targets, the order, and the kind.
   Send every dispatch of the round in a single message, one `remedy` agent call per location.
   *Do not wait for one location's outcome before you dispatch the next location in the round.*
   Wait for all `remedy` agents of the round.
   Follow `## Inline rewrite` for the round, with no dispatch, when the client has no sub-agent tool.
   Follow `## Inline rewrite` for the round too when a dispatch fails because the client cannot start a `remedy` agent at all.
   *Do not treat a refusal by the client's permission or safety check as a client that cannot start a `remedy` agent.*

   Two different refusals can happen here, and only one of them stops the run:
   - A refused dispatch — the client's own permission or safety check will not start the `remedy` agent at all — stops the run: tell the user which location was refused, and that heal rewrites instruction files, so it runs in a permission mode where the user approves or accepts file edits — in Claude Code, accept-edits mode rather than auto mode. *Do not rewrite a refused-dispatch location in this session instead.*
   - A refused write — the agent starts, but the client's own guard denies one of its file edits (for example, a self-modification guard refusing an edit to an agent definition file) — does not stop the run. The `remedy` agent reports that location `refused`; log it. Then move on to the rest of this round's `remedy` agents. *The rest of this round still dispatches, and later rounds still run.*
3. Collect the outcome each `remedy` agent reports, which is only a compact outcome — per file, its path and `accepted` (with any line it put back and any hedge it made direct), `restored` with the failed check(s), or `refused` with the reason the client's guard gave — never the brief or a file's contents.
   Take each `remedy` agent's reported outcome as given.
   Log every restore with its reason (the location's `element`, its files, and the failed check(s) reported).
   Log every refusal with its reason (the location's `element`, its files, and what the guard said).
   Give up a restored or refused location for the rest of this run: skip it in step 1 even if it reappears in a later round's index, matched by its `element` and `kind`, and at least one file in common with the given-up location's `files`.
   *Do not inspect the files or run a shell command to confirm a restore.*
4. Call `validate(path, targets)` again before starting the next round.
   The locations re-number against the now-rewritten files.
   Use the new `order`s for that round's dispatches.

Go to `## Finish` after the last round.

A `circuit_breaker` reply to any `validate` call this workflow makes on the project `path` stops the whole run at once.
That covers the initial call, step 4 above, and `## Finish` below.
Report what the run has `accepted`, `restored`, and `refused` so far.
*Do not call `validate` again for this path.*

## Inline rewrite

Run this section in place of step 2's dispatch when the client cannot start a `remedy` agent.
Read [`agents/remedy.md`](../../../agents/remedy.md) in full before the first location, at `../../../agents/remedy.md` from this file.
Work the round's locations yourself, in `order`, one location at a time.
*Do not start a location before the previous location's outcome is final.*
*Do not run two locations in the same step.*
For each location, follow every section of `agents/remedy.md` from `## Brief retrieval` through `## Element check`, with yourself as the `remedy` agent.
Call `remedy_brief` for that location with the run's `path` and `targets`, as `## Brief retrieval` directs.
Keep the 4-call bound on `validate` per file, the retry rule for a temporary error reply, the put-back, the best-version rule, and the restore rules of `## Validation and convergence` unchanged.
Keep each file's original text in your own context, as `## Original text` directs.
Write that text back verbatim on a restore.
*Do not copy a file to a backup, a temporary copy, or any other path with a shell command.*
*Do not run a shell command to read, edit, or write an instruction file.*
Report each location's outcome in the form `## Outcome report` of `agents/remedy.md` gives.
Take that outcome through step 3 as a `remedy` agent's reported outcome.

## Finish

Call `validate(path, targets)` once more after the last pass.
Report, in this order:

1. The result: the project score before the run → now, and the finding count before → now.
2. Per location, one table row each: the location's `element`, its outcome (`accepted`, `restored`, or `refused`), its files' score before → after, the rounds its agent used, what it kept (the `kept` counts), the lines it put back, and — for a restored location, the failed check that restored it, or for a refused location, the reason the client's guard gave.
   List each hedge its agent made direct under an accepted location's row, as a change the user can see: `made direct: <before> → <after>`, with the sentence before and after as the agent reported them.
   These are rewrites that turned a suggestion ("prefer X", "consider running X") into an order ("use X", "run X").
   They are accepted, and listed so the user can undo any of them.
3. What stays open: group `workflow.listed` by its shared `why` text.
   Give each group one line per rule — its title with its ID as a link, `Title ([CORE:E:0004](url))`, from the reply's `rules` map, and its count — then the group's `why` once, after its rules.
   Then list any location of `workflow.locations` still open, with the reason.

Write the same report as Markdown, with `<YYYY-MM-DD-HHMM>` as the local date and 24-hour time, to `.ails/reports/heal-<YYYY-MM-DD-HHMM>.md` under the project `path`.
Name that `.ails/reports/heal-<YYYY-MM-DD-HHMM>.md` file in the reply.

Ask the user whether to stop at `## Finish` or continue.
Continuing runs another pass of `## The loop` over every location in that validate reply's index whose `importance` is `gate_mover` or `conditional` and that this run has not given up on, matched by its `element` and `kind`, and at least one file in common with the given-up location's `files`.
Dispatch with that index's `order`s, still one round per kind in index order, without asking when the user already approved every fix.
That pass, too, ends at `## Finish`, which offers the choice again.
