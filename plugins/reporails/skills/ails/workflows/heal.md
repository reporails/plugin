# Heal — the location rewrite loop

Rewrite instruction-file locations whole, one kind at a time, with a `remedy` agent per location.
Confirm each `remedy` rewrite kept everything before accepting it.
This loop is MCP-only and needs a paid account.
`$ARGUMENTS` is `[path] [targets…]`, as "`check` / `heal` arguments" in `SKILL.md` defines.
Carry whatever `targets` you parsed on every `validate` call this workflow makes.
*Never call `validate` with `targets` the user did not give.*
A Pro `validate` reply arrives as a text view.
Read each of its fields by the key path its line starts with (`workflow.summary`, `workflow.locations`, `workflow.listed`, `host_hooks`, `preservation.ok`, `feedback`, `funnel.retryable`).
A reply called with `full=true`, and every free, anonymous, offline and error reply, arrives as JSON: read it by its field names.
Present every `validate` reply as `## Output` in [`check.md`](check.md) directs.

## Initial `validate` call

Find the `reporails` MCP `validate` tool as `## Tool detection` in [`setup.md`](setup.md) directs.
Heal cannot run without it: tell the user heal needs the `reporails` MCP connected.
Point them to the `setup` workflow ([`setup.md`](setup.md)), and stop.
Heal has no CLI fallback. *Do not fall back to the CLI.*

Make the `validate` call as `## The validate call` in [`check.md`](check.md) directs, then show the reply's notices and branch on the reply.
When the reply's `notices` list is non-empty, show each notice's text to the user verbatim at the top of the report, warnings (`warn`) first, with its `url` when it has one.
The reply carries the notices once per run: show them from the first reply only.
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
- A paid tier with `workflow.locations` present → follow `## The loop` below. `workflow.locations` is the index the loop works from: each entry's `order`, `kind`, `element`, `importance`, `finding_count`, and `files`. `workflow.listed` names the findings this run will not rewrite, each group with its `why`. When `targets` was given, the `workflow.targets` line carries the tokens and the `<n> of <m> locations` count — kept locations are re-numbered from 1.
A `workflow.locations` table over its size budget lists later kinds as one line each: `<kind>: <n> locations (orders a–b)`. Work only the kinds the table lists in full. The `validate` call before each round lists the next kind in full.

## Start block

Give the user this information once, as reply text the user sees, written after the initial `validate` reply and before the message that dispatches round 1.
Dispatch round 1's `remedy` agents only after the start block is shown. *Do not dispatch round 1 before the start block is shown, and do not write the start block only in your thinking.*
It is information, not a question, so a user who approved every fix still gets it.

1. The scope: the rounds in order, each with its `kind` and the locations it holds (each one's `element`).
2. The places skipped, with the reason: the `workflow.listed` groups whose `why` is `excluded` (a path in the user's `heal_exclude` config, still checked, never rewritten), `at-ceiling` (already at score 10), and `leave-it` (the findings' brief says to leave the line as it stands). Add each location this run gave up on, by its `element`. Send no `remedy` agent to a skipped location.
3. A time range: about 4–9 min per round × the number of rounds.
4. Each `host_hooks` entry that can intercept the rewrites: its agent, event, matcher, and file. Tell the user how to let the `remedy` agent through that hook.
   - Where the entry's `identity` names fields, tell the user to match them in that hook, for example `agent_type` equal to `reporails:remedy`.
   - Where `identity` is `none`, tell the user to let the hook pass the `remedy` agent's tools (`Read`, `Edit`, `Write`) on the files heal names.
5. That the client may ask before each edit to an instruction file (a `CLAUDE.md` or `AGENTS.md`, or anything under an agent's config folder such as `.claude/`), because those files change how their agent behaves. On Claude Code, the plugin shows the user a notice naming the folders the run writes to and the session-wide option for `.claude/` edits. *Do not repeat that notice on Claude Code.* On any other client, name every folder holding a location's `files`.
6. That on the inline path (no sub-agent) the same hooks apply, and only the tool-and-path exemption works.

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
   Write the dispatch prompt as these four lines: `path: <the project's absolute path>`, `targets: <the targets, or (none)>`, `order: <the location's order>`, `kind: <the location's kind>`.
   Send every dispatch of the round in a single message, one `remedy` agent call per location, each in the foreground (not in the background).
   *Do not wait for one location's outcome before you dispatch the next location in the round.*
   Wait for all `remedy` agents of the round in that message. *Do not run a `remedy` agent in the background.*
   Follow `## Inline rewrite` for the round, with no dispatch, when the client has no sub-agent tool.
   Follow `## Inline rewrite` for the round too when a dispatch fails because the client cannot start a `remedy` agent at all.
   *Do not treat a refusal by the client's permission or safety check as a client that cannot start a `remedy` agent.*

   Two different refusals can happen here, and only one of them stops the run:
   - A refused dispatch — the client's own permission or safety check will not start the `remedy` agent at all — stops the run: tell the user which location was refused, and that heal rewrites instruction files, so it runs in a permission mode where the user approves or accepts file edits — in Claude Code, accept-edits mode rather than auto mode. *Do not rewrite a refused-dispatch location in this session instead.*
   - A refused write — the agent starts, but the client's own guard denies one of its file edits (for example, a self-modification guard refusing an edit to an agent definition file) — does not stop the run. The `remedy` agent reports that location `refused`; log it. Then move on to the rest of this round's `remedy` agents. *The rest of this round still dispatches, and later rounds still run.*
3. Collect the outcome each `remedy` agent reports, which is only a compact outcome — per file, its path and `accepted` (with any line it put back and any hedge it made direct), `restored` with the failed check(s), or `refused` with the reason the client's guard gave — never the brief or a file's contents.
   Take each `remedy` agent's reported outcome as given.
   On Claude Code, the plugin prints each location's line and the round-close line itself as each `remedy` agent returns, whether the client ran it in the foreground or the background. *Do not write them again on Claude Code.*
   On every other client, after each `remedy` agent's hand-back, write one line in this form: `<order> <element> — accepted (score a → b) | restored (<failed check>) | refused (<reason>)`. Name the hook in the `refused` reason when a hook refused the write.
   Write that line in a reply as soon as the agent's outcome arrives, before your next tool call.
   Write one line per location, also when several agents of the round return close together.
   Show the user that one line for each hand-back. *Do not paste a `remedy` agent's report into the reply.*
   Keep the rest of each report (its before → after pairs, `made_direct` and `made_specific` entries, `introduced`, `validate calls`, `put back`) for `## Finish`.
   Log every restore with its reason (the location's `element`, its files, and the failed check(s) reported).
   Log every refusal with its reason (the location's `element`, its files, and what the guard said).
   Give up a restored or refused location for the rest of this run: skip it in step 1 even if it reappears in a later round's index, matched by its `element` and `kind`, and at least one file in common with the given-up location's `files`.
   *Do not inspect the files or run a shell command to confirm a restore.*
4. On Claude Code, the plugin has printed the round-close line after the round's last hand-back. On every other client, after the round's last hand-back, write one round-close line in the form `Round <kind> done — <n> accepted, <n> restored, <n> refused, <minutes> min`. Show the user that line.
   On every other client, write the round-close line before the `validate` call that starts the next round.
   On every other client, show all of the round's lines (one per location, then the round-close line) before that call. *Do not move to the next round's `validate` before the round's lines are shown.*
   Call `validate(path, targets)` again before starting the next round.
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
Call `remedy_brief` for that location with the run's `path`, `targets`, and `has_guide=true`, as `## Brief retrieval` directs. The guide is in `agents/remedy.md`, which you read in full above, so `has_guide=true` is true here too.
Keep the 4-call bound on `validate` per file, the retry rule for a temporary error reply, the put-back, the best-version rule, and the restore rules of `## Validation and convergence` unchanged.
Keep each file's original text in your own context, as `## Original text` directs.
On a restore, write each file's original text back verbatim to its `path`.
*Do not copy a file to a backup, a temporary copy, or any other path with a shell command.*
*Do not run a shell command to read, edit, or write an instruction file.*
Report each location's outcome in the form `## Outcome report` of `agents/remedy.md` gives.
Take that outcome through step 3 as a `remedy` agent's reported outcome.

## Finish

Call `validate(path, targets)` once more after the last pass.
Report, in this order:

1. The compression line, before → now, from the `compression:` line of the first and the last reply.
2. "What your agent now reads differently": up to 5 before → after pairs, taken from the `gate_mover` and `conditional` fixes the agents reported.
3. The total `introduced` count, summed over the accepted locations.
4. The "Made direct" and "Made specific" lanes. Give each agent-reported `made_direct` and `made_specific` entry as `<before> → <after>`, so the user can undo it. A `made_direct` entry is a suggestion ("prefer X") turned into an order ("use X"). A `made_specific` entry is a kept instruction that gained a named construct.
5. "Left alone on purpose": group `workflow.listed` by its `why`. Give each group one line per rule — its title with its ID as a link, `Title ([CORE:E:0004](url))`, and its count — then the group's `why` once, after its rules.
6. The locations still open, each with the reason.
7. Last, and secondary: the project score and the finding count, before → now.

Write the same receipt as Markdown to `.ails/reports/heal-<YYYY-MM-DD-HHMM>.md` under the project `path`, with `<YYYY-MM-DD-HHMM>` as the local date and 24-hour time.
Add an appendix to that report file with one entry per location: its `element`, outcome, files' score before → after, `kept` counts, lines put back, `validate calls`, and rounds used.
Add the failed check to the entry of a `restored` location, and the refusal reason to the entry of a `refused` location.
*Do not put the appendix in the reply: write it only to the `.ails/reports/heal-<YYYY-MM-DD-HHMM>.md` file.*
Name the `.ails/reports/heal-<YYYY-MM-DD-HHMM>.md` file in the reply.

Offer a second pass only when the last `validate` reply's `workflow.locations` holds a location whose `importance` is `gate_mover` or `conditional` and that this run has not given up on, matched by its `element` and `kind`, and at least one file in common with the given-up location's `files`.
*Do not offer another pass when no such location remains.*
A second pass runs `## The loop` over those locations only, with that reply's `order`s, still one round per kind in index order, without asking when the user already approved every fix.
It ends at `## Finish`, which offers the choice again.
