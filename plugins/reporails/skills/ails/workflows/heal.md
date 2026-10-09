# Heal — the location plan loop

Fix instruction-file locations, one kind at a time, each from its own plan.
Work a location with a `remedy` agent where the client supports sub-agents, or yourself, inline, by the same procedure on any client: [`remedy-location.md`](remedy-location.md).
Confirm each location's result conformed to its plan and kept everything before accepting it.
This loop is MCP-only and needs a paid account.
`$ARGUMENTS` is `[path] [targets…]`, as "`check` / `heal` arguments" in `SKILL.md` defines.
Carry whatever `targets` you parsed on every run-level `validate` call this workflow makes (the initial call, the call before each round, and the final call), and on every `remedy_brief` call. The per-file `validate(path=<file>)` check inside a location's procedure is the one call that carries no `targets`.
*Never call `validate` with `targets` the user did not give.*
A Pro `validate` reply arrives as a text view.
Read each of its fields by the key path its line starts with (`workflow.summary`, `workflow.locations`, `workflow.listed`, `host_hooks`, `conformance.ok`, `preservation.ok`, `feedback`, `funnel.retryable`).
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
- A paid tier whose `workflow.locations` is empty → nothing to apply. Report what stays `listed` (the `reason` each finding is not served) and stop.
- A paid tier with `workflow.locations` present → follow `## The loop` below. `workflow.locations` is the index the loop works from: each entry's `order`, `kind`, `element`, `importance`, `finding_count`, and `files`. `workflow.listed` names the findings this run will not change, each group with its `reason`. When `targets` was given, the `workflow.targets` line carries the tokens and the `<n> of <m> locations` count — kept locations are re-numbered from 1.
A `workflow.locations` table over its size budget lists later kinds as one line each: `<kind>: <n> locations (orders a–b)`. Work only the kinds the table lists in full. The `validate` call before each round lists the next kind in full.

## Start block

Give the user this information once, as reply text the user sees, on every path and every client.
Write it in a reply after the initial `validate` reply and before the `heal_apply` call, whether you work the locations with `remedy` agents or inline.
Call `heal_apply` and start round 1 only after the start block is shown. *Do not call `heal_apply` or start round 1 before the start block is shown, and do not write the start block only in your thinking.*
Show the start block before any other reply text or tool call that follows the initial `validate` reply.
It is information, not a question, so a user who approved every fix still gets it.

1. The scope: the rounds in order, each with its `kind` and the locations it holds (each one's `element`).
2. The places skipped, with the reason: the `workflow.listed` groups whose `reason` is `excluded` (a path in the user's `heal_exclude` config, still checked, never changed), `at-ceiling` (already at score 10), and `leave-it` (the findings' brief says to leave the line as it stands). Add each location this run gave up on, by its `element`. Send no `remedy` agent to a skipped location.
3. A time range: about 4–9 min per round × the number of rounds.
4. Each `host_hooks` entry that can intercept the edits: its agent, event, matcher, and file. Tell the user how to let the `remedy` agent through that hook.
   - Where the entry's `identity` names fields, tell the user to match them in that hook, for example `agent_type` equal to `reporails:remedy`.
   - Where `identity` is `none`, tell the user to let the hook pass the `remedy` agent's tools (`Read`, `Edit`, `Write`) on the files heal names.
5. That the client may ask before each edit to an instruction file (a `CLAUDE.md` or `AGENTS.md`, or anything under an agent's config folder such as `.claude/`), because those files change how their agent behaves. On Claude Code, the plugin shows the user a notice naming the folders the run writes to and the session-wide option for `.claude/` edits. *Do not repeat that notice on Claude Code.* On any other client, name every folder holding a location's `files`.
6. That on the inline path (no sub-agent) the same hooks apply, and only the tool-and-path exemption works.

## Apply the no-judgment fixes

Call `heal_apply` only after the start block is shown.
Before round 1, make every fix that needs no decision in one call.
Find the `reporails` MCP `heal_apply` tool by the name ending `__heal_apply`, as `## Tool detection` in [`setup.md`](setup.md) directs for `validate`.
Call `heal_apply(path, targets)` once, with the run's `targets`. *Do not call it again in this run.*
Show the reply's first line to the user verbatim, in the form `heal_apply: <n> fixed · <m> left for a decision · <k> put back`.
Keep its `<n>` and `<k>` for `## Finish`.

- A reply that wrote nothing because the account is not Pro (free, signed out or offline) → stop exactly as the non-Pro `validate` branch in `## Initial `validate` call` does, with the reason the reply gives.
- Otherwise call `validate(path, targets)` again and branch on the new reply as the initial `validate` call's branches do, so the rounds work from what is left.
  A location absent from the new `workflow.locations`, or whose row shows `finding_count` 0, has nothing left to decide and is not dispatched.
  The rounds below use only this reply's index and its `order`s.

## The loop

Run one round per `kind`, in the order the index already gives them.
Kinds loaded at session start come first, then invoked kinds, then on-demand kinds.
The index order IS the round order: a round is a consecutive run of locations sharing one `kind`.
*When a `remedy` agent works a location, this loop does not call `remedy_brief` or read that location's file contents itself.* That is the agent's job, in its own context. When you work a location inline, you do both, as `## Inline path` directs.

1. Tell the user which locations are in this round (each one's `element`, `kind`, `files`, `finding_count`), and ask to proceed.
   Skip any location this run already gave up on, matched by its `element` and `kind`, and at least one file in common with the given-up location's `files`.
   A user who already approved every fix for the whole run is not asked again.
2. Dispatch one `remedy` agent per location, all of the round at once.
   Pass the project's absolute `path`, the `targets` this run is using, the location's `order`, its `kind`, and the absolute path of [`remedy-location.md`](remedy-location.md) — nothing else.
   Write the dispatch prompt as these five lines: `path: <the project's absolute path>`, `targets: <the targets, or (none)>`, `order: <the location's order>`, `kind: <the location's kind>`, `procedure: <the absolute path of remedy-location.md, next to this file>`.
   Send every dispatch of the round in a single message, one `remedy` agent call per location, each in the foreground (not in the background).
   *Do not wait for one location's outcome before you dispatch the next location in the round.*
   Wait for all `remedy` agents of the round in that message. *Do not run a `remedy` agent in the background.*
   Follow `## Inline path` for the round, with no dispatch, when the client has no sub-agent tool.
   Follow `## Inline path` for the round too when a dispatch fails because the client cannot start a `remedy` agent at all.
   Sub-agent dispatch is how a round's locations run in parallel where the client supports it. The inline path is the same work, one location at a time, and is first-class on every client.
   *Do not treat a refusal by the client's permission or safety check as a client that cannot start a `remedy` agent.*

   Two different refusals can happen here, and only one of them stops the run:
   - A refused dispatch — the client's own permission or safety check will not start the `remedy` agent at all — stops the run: tell the user which location was refused, and that heal edits instruction files, so it runs in a permission mode where the user approves or accepts file edits — in Claude Code, accept-edits mode rather than auto mode. *Do not work a refused-dispatch location in this session instead.*
   - A refused write — the agent starts, but the client's own guard denies one of its file edits (for example, a self-modification guard refusing an edit to an agent definition file) — does not stop the run. The `remedy` agent reports that location `refused`; log it. Then move on to the rest of this round's `remedy` agents. *The rest of this round still dispatches, and later rounds still run.*
3. Collect the outcome each `remedy` agent reports, which is only a compact outcome — per file, its path and `accepted` (with its score before → after, its `introduced` count, up to 3 before → after pairs, and any `left:` lines), `restored` with the failed check(s), or `refused` with the reason the client's guard gave — never the brief or a file's contents.
   Take each `remedy` agent's reported outcome as given.
   On Claude Code, the plugin prints the line of each location a dispatched `remedy` sub-agent worked (a dispatch through the client's sub-agent tool) itself as each sub-agent returns, whether the client ran it in the foreground or the background. *Do not write that line again on Claude Code for such a location.*
   On every other client, after each `remedy` agent's hand-back, write one line in this form: `<order> <element> — accepted (score a → b) | restored (<failed check>) | refused (<reason>)`. Name the hook in the `refused` reason when a hook refused the write.
   Write that line in a reply as soon as the agent's outcome arrives, before your next tool call.
   Write one line per location, also when several agents of the round return close together.
   Show the user that one line for each hand-back. *Do not paste a `remedy` agent's report into the reply.*
   Keep the rest of each report (its before → after pairs, `introduced`, `left:` lines, `validate calls`) for `## Finish`.
   Log every restore with its reason (the location's `element`, its files, and the failed check(s) reported).
   Log every refusal with its reason (the location's `element`, its files, and what the guard said).
   Give up a restored or refused location for the rest of this run: skip it in step 1 even if it reappears in a later round's index, matched by its `element` and `kind`, and at least one file in common with the given-up location's `files`.
   *Do not inspect the files or run a shell command to confirm a restore.*
4. On Claude Code, the plugin has printed the round-close line after the last hand-back of a round whose every location a dispatched `remedy` sub-agent worked. In a round with an inline location, including a round where a dispatch fell back to the inline path, write the round-close line yourself, covering the whole round, on every client. On every other client, after the round's last hand-back, write one round-close line in the form `Round <kind> done — <n> accepted, <n> restored, <n> refused, <minutes> min`. Show the user that line.
   On every other client, write the round-close line before the `validate` call that starts the next round.
   On every other client, show all of the round's lines (one per location, then the round-close line) before that call. *Do not move to the next round's `validate` before the round's lines are shown.*
   Call `validate(path, targets)` again before starting the next round.
   The locations re-number against the now-changed files.
   Use the new `order`s for that round's dispatches.

Go to `## Finish` after the last round.

A `circuit_breaker` reply to any `validate` call this workflow makes on the project `path` stops the whole run at once.
That covers the initial call, step 4 above, and `## Finish` below.
Report what the run has `accepted`, `restored`, and `refused` so far.
*Do not call `validate` again for this path.*

## Inline path

Run this section in place of step 2's dispatch when the client cannot start a `remedy` agent, or when sub-agents are unavailable.
Work the round's locations yourself, in `order`, one location at a time.
*Do not start a location before the previous location's outcome is final.*
For each location, with yourself as the `remedy` agent, read [`remedy-location.md`](remedy-location.md) in full and follow it, with the run's `path` and `targets` and the location's `order` and `kind`.
Take each location's outcome, in the form that file's outcome report gives, through step 3 of `## The loop` as a `remedy` agent's reported outcome.
The plugin prints no line for a location you work inline, so on every client, Claude Code included, write the location's one line, in step 3's form, as soon as the location's outcome is final and before you start the next location.
After the round's last location, write the round-close line, in step 4's form, before the next round's `validate` call.

## Finish

Call `validate(path, targets)` once more after the last pass.
Report, in this order:

1. The compression line, before → now, from the `compression:` line of the first and the last reply.
2. "What your agent now reads differently": up to 5 before → after pairs, taken from the pairs the agents reported under their `accepted` rows.
3. The total `introduced` count, summed from the `introduced <n>` of the accepted files' rows.
4. "Left for you": one line per `left:` line the agents reported, as they gave it. A `hoist` slot appears here as `move <file>:<line> into <to>; the same line is in <also path>`.
5. "Left alone on purpose": group `workflow.listed` by its `reason`. Give each group one line per rule — its title with its ID as a link, `Title ([CORE:E:0004](url))`, and its count — then the group's `reason` once, after its rules.
6. The locations still open, each with the reason.
7. Last, and secondary: the project score and the finding count, before → now.
8. The fixes made before the rounds: `<n> fixed` and `<k> put back`, as the `heal_apply:` line reported them. Give no count that line did not.

Write the same receipt as Markdown to `.ails/reports/heal-<YYYY-MM-DD-HHMM>.md` under the project `path`, with `<YYYY-MM-DD-HHMM>` as the local date and 24-hour time.
Add an appendix to that report file with one entry per location: its `element`, outcome, files' score before → after, `introduced` count, and `validate calls`, all as the agents reported them.
Add the failed check to the entry of a `restored` location, and the refusal reason to the entry of a `refused` location.
*Do not put the appendix in the reply: write it only to the `.ails/reports/heal-<YYYY-MM-DD-HHMM>.md` file.*
Name the `.ails/reports/heal-<YYYY-MM-DD-HHMM>.md` file in the reply.

Offer a second pass only when the last `validate` reply's `workflow.locations` holds a location whose `importance` is `gate_mover` or `conditional` and that this run has not given up on, matched by its `element` and `kind`, and at least one file in common with the given-up location's `files`.
*Do not offer another pass when no such location remains.*
A second pass runs `## The loop` over those locations only, with that reply's `order`s, still one round per kind in index order, without asking when the user already approved every fix.
It ends at `## Finish`, which offers the choice again.
