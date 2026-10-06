# reporails plugin

A portable [Agent Plugins](https://agent-plugins.org) package delivering AI instruction-file quality — preflight, check, heal, explain — into Claude Code, Codex, Cursor, GitHub Copilot, and Antigravity from one repo. It bundles the `ails` skill and the `reporails` MCP server; the `reporails-cli` package backs both.

## What's inside

| File | What | Read by |
|---|---|---|
| `plugins/reporails/skills/ails/` | The `ails` skill — preflight + check + heal + explain, including the remedy loop (validate → rewrite → re-validate) | all 5 |
| `plugins/reporails/plugin.json` | Portable Agent Plugins manifest | codex, cursor, copilot (+ supplies antigravity's `name`) |
| `plugins/reporails/mcp.json` | Portable MCP config (`type: stdio`) | codex, cursor, copilot |
| `plugins/reporails/mcp_config.json` | Antigravity MCP config | antigravity |
| `plugins/reporails/.mcp.json` + `plugins/reporails/.claude-plugin/` | Claude-native MCP config + manifest | claude |
| `.claude-plugin/marketplace.json` + `.agents/plugins/marketplace.json` | Marketplace catalogs pointing at `plugins/reporails/` | claude, codex |

Every MCP config points at the same `reporails-mcp` server via `uvx`, so all five agents reach one engine, and there is one skill to maintain.

## Install

From a terminal, one command sets everything up: it installs `uv` when it is missing, puts `ails` on your `PATH`, installs this plugin into Claude Code and Codex when they are present, and ends by pointing you to `ails login`:

```bash
npx @reporails/cli@0.6 install
```

Or install by hand. Claude Code and Codex install from the marketplace catalogs in this repository:

- **Claude Code** — `/plugin marketplace add reporails/plugin`, then `/plugin install reporails@reporails` (from a shell: `claude plugin marketplace add reporails/plugin`, then `claude plugin install reporails@reporails`)
- **Codex** — `codex plugin marketplace add reporails/plugin`, then `codex plugin add reporails@reporails`

Cursor, Copilot (VS Code) and Antigravity have no marketplace listing; clone the repository, then install from the clone:

```bash
git clone https://github.com/reporails/plugin
```

- **Cursor** — copy `plugin/plugins/reporails/` into `~/.cursor/plugins/local/reporails/`, then restart Cursor
- **Copilot (VS Code)** — "Install Plugin From Source" → the `plugin/plugins/reporails/` folder
- **Antigravity** — `agy plugin install plugin/plugins/reporails`

`ails install` prints the same commands.

## Requirements

- [`uv`](https://docs.astral.sh/uv/) installed — every agent's MCP config launches the server with `uvx`.
- The first start downloads the command-line tool (`reporails-cli>=0.6.0,<0.7`) with its dependencies and about 275 MB of model files, once per machine, so it needs network access. On a slow connection the agent can show the server as failed to connect; reconnect it once the download finishes (Claude Code: `/mcp`), or restart the agent.
- `pip install reporails-cli` does not provide `uvx`, so it cannot start the plugin's server.
- Fixes (`heal`) need a Pro subscription and a sign-in: `ails login`, or `npx @reporails/cli@0.6 login` when you have only the plugin and no `ails` command.

To also have the command-line tool on your `PATH` outside the plugin:

```bash
uv tool install reporails-cli
```

## The `ails` skill

- `preflight <skill|agent|rule|main>` — fetch the workflow-ordered rules before you author
- `check` — validate instruction files, score, per-finding rule references
- `heal` — rewrite instruction-file locations toward their ideal form (paid account)
- `explain <rule_id>` — single-rule detail with Pass / Fail examples

The slash-command namespace varies by agent (e.g. `/reporails:ails check` in Claude Code); the skill body drives the same loop everywhere.

## License

Business Source License 1.1 (`BUSL-1.1`), licensor Mészáros Gábor e.v., trading as Reporails. See [LICENSE](LICENSE).
You may use the plugin for any purpose except offering a competing AI instruction management product or service.
Each release becomes available under Apache-2.0 three years after its release date.
The Reporails CLI and its model files carry their own licences.
