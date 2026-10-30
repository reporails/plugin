"""Behaviour of hooks/record-event.sh, its hooks.json registration, and the bin/ails wrapper.

Runs the real scripts under `sh` with a controlled PATH.
Run: python3 -m pytest plugins/reporails/tests/test_record_event.py
"""
import json
import stat
import subprocess
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
SCRIPT = PLUGIN / "hooks" / "record-event.sh"
WRAPPER = PLUGIN / "bin" / "ails"
HOOKS_JSON = PLUGIN / "hooks" / "hooks.json"
COMMAND = 'sh "${CLAUDE_PLUGIN_ROOT}"/hooks/record-event.sh'
PAYLOAD = b'{"session_id":"s1","hook_event_name":"Stop","x":"\xc3\xa9 \\n"}\n'
SYSTEM_PATH = "/usr/bin:/bin"


def fake(directory, name, body):
    path = directory / name
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def recorder(directory, name, tail=""):
    """A fake executable writing its argv and stdin next to itself."""
    return fake(
        directory,
        name,
        f'printf "%s\\n" "$@" > "{directory}/{name}.argv"\ncat > "{directory}/{name}.stdin"\n{tail}',
    )


def run(script, tmp_path, args=(), payload=PAYLOAD, path=None):
    env = {"PATH": f"{tmp_path / 'bin'}:{SYSTEM_PATH}" if path is None else path}
    return subprocess.run(["sh", str(script), *args], input=payload, capture_output=True, env=env, timeout=30)


def bindir(tmp_path):
    d = tmp_path / "bin"
    d.mkdir()
    return d


def test_fake_ails_gets_args_and_exact_payload(tmp_path):
    d = bindir(tmp_path)
    recorder(d, "ails", "echo noise; echo err >&2\n")
    result = run(SCRIPT, tmp_path)
    assert result.returncode == 0
    assert result.stdout == b""
    assert result.stderr == b""
    assert (d / "ails.argv").read_text().split() == ["hook", "--agent", "claude"]
    assert (d / "ails.stdin").read_bytes() == PAYLOAD


def test_no_ails_never_calls_npx(tmp_path):
    d = bindir(tmp_path)
    recorder(d, "npx")
    result = run(SCRIPT, tmp_path)
    assert result.returncode == 0
    assert result.stdout == b""
    assert result.stderr == b""
    assert not (d / "npx.argv").exists()


def test_plugin_bin_on_path_never_reaches_npx(tmp_path):
    d = bindir(tmp_path)
    recorder(d, "npx")
    result = run(SCRIPT, tmp_path, path=f"{WRAPPER.parent}:{d}:{SYSTEM_PATH}")
    assert result.returncode == 0
    assert result.stdout == b""
    assert not (d / "npx.argv").exists()


def test_ails_exit_2_still_exits_0_silently(tmp_path):
    d = bindir(tmp_path)
    fake(d, "ails", "cat >/dev/null\necho out; echo err >&2\nexit 2\n")
    result = run(SCRIPT, tmp_path)
    assert result.returncode == 0
    assert result.stdout == b""
    assert result.stderr == b""


def test_hooks_json_registers_recorder_on_nine_events():
    hooks = json.loads(HOOKS_JSON.read_text())["hooks"]
    plain = ["SessionStart", "SessionEnd", "UserPromptSubmit", "Stop", "SubagentStop", "PreCompact", "PostCompact"]
    for event in plain:
        entries = [e for e in hooks[event] if any(h["command"] == COMMAND for h in e["hooks"])]
        assert len(entries) == 1, event
        assert "matcher" not in entries[0], event
        assert all("async" not in h for h in entries[0]["hooks"]), event
    for event in ("PreToolUse", "PostToolUse"):
        entries = [e for e in hooks[event] if any(h["command"] == COMMAND for h in e["hooks"])]
        assert len(entries) == 1, event
        assert entries[0]["matcher"] == "Read|Edit|Write|NotebookEdit", event
        assert entries[0]["hooks"] == [{"type": "command", "command": COMMAND, "async": True}], event


def test_hooks_json_heal_entries_intact():
    hooks = json.loads(HOOKS_JSON.read_text())["hooks"]
    notice = {"type": "command", "command": 'sh "${CLAUDE_PLUGIN_ROOT}"/hooks/heal-notice.sh'}
    progress = {"type": "command", "command": 'sh "${CLAUDE_PLUGIN_ROOT}"/hooks/heal-progress.sh'}
    assert {"matcher": "Agent|Task", "hooks": [notice, progress]} in hooks["PreToolUse"]
    assert {"matcher": "Agent|Task", "hooks": [progress]} in hooks["PostToolUse"]
    assert {"hooks": [progress]} in hooks["UserPromptSubmit"]


def test_wrapper_runs_installed_ails_not_itself(tmp_path):
    d = bindir(tmp_path)
    recorder(d, "ails")
    recorder(d, "npx")
    path = f"{WRAPPER.parent}:{d}:{SYSTEM_PATH}"
    result = run(WRAPPER, tmp_path, args=("check", "-v"), payload=b"", path=path)
    assert result.returncode == 0
    assert (d / "ails.argv").read_text().split() == ["check", "-v"]
    assert not (d / "npx.argv").exists()


def test_wrapper_falls_back_to_npx(tmp_path):
    d = bindir(tmp_path)
    recorder(d, "npx")
    path = f"{WRAPPER.parent}:{d}:{SYSTEM_PATH}"
    result = run(WRAPPER, tmp_path, args=("check",), payload=b"", path=path)
    assert result.returncode == 0
    assert (d / "npx.argv").read_text().split() == ["@reporails/cli@0.6", "check"]
