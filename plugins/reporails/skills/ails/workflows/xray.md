# Xray — Session X-ray Page

Open the session x-ray page for this project and show the user its address.
`$ARGUMENTS` after `xray` is an optional `[session]`: a session id the user named.

## MCP path (preferred)

Check the tool list for the `reporails` MCP `xray` tool first (its name ends in `reporails__xray`).
Take the setup offer from [`setup.md`](setup.md) when the tool is missing.

1. Call `xray`, passing `session` only when the user named one in `$ARGUMENTS`.
2. Show the user the reply's `url` as a clickable address, with one line saying the page shows what happened in the session: its context, tools, hooks and subagents.
3. Add one line when the reply's `picked` is `current_unknown`: the folder's newest session is shown because the agent did not say which session it is.
4. Show the reply's `message` and stop when the reply is `{"error": ...}`.

*Do not paste a session id the user did not give.*

## CLI path (fallback)

Use this path when the `xray` tool is still missing after the setup offer.
Follow the CLI fallback order in [`setup.md`](setup.md).
Run it from the project directory, then show the address it prints:

```bash
ails xray --current --background
```

Run this instead when the user named a session:

```bash
ails xray --session <id> --background
```

Run `npx @reporails/cli@0.6 xray --current --background` when the `ails` binary is not installed.
