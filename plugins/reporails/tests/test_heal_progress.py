"""Behaviour of hooks/heal-progress.sh: one line per finished remedy agent, one line per round.

Runs the real script under `sh` with a temp TMPDIR and JSON on stdin.
Run: python3 -m unittest discover plugins/reporails/tests
"""
import json
import os
import shutil
import signal
import stat
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
SCRIPT = PLUGIN / "hooks" / "heal-progress.sh"
HOOKS_JSON = PLUGIN / "hooks" / "hooks.json"
SESSION = "sess-1"
REMEDY = "reporails:remedy"


def prompt(order, kind):
    return f"path: /abs/project\ntargets: (none)\norder: {order}\nkind: {kind}"


def pre(tool_use_id, order, kind="skills", agent=REMEDY, session=SESSION):
    return {
        "session_id": session,
        "hook_event_name": "PreToolUse",
        "tool_name": "Agent",
        "tool_input": {"subagent_type": agent, "description": "d", "prompt": prompt(order, kind), "run_in_background": False},
        "tool_use_id": tool_use_id,
    }


def post(tool_use_id, order, report, kind="skills", agent=REMEDY, session=SESSION):
    return {
        "session_id": session,
        "hook_event_name": "PostToolUse",
        "tool_name": "Agent",
        "tool_input": {"subagent_type": agent, "description": "d", "prompt": prompt(order, kind), "run_in_background": False},
        "tool_response": {
            "status": "completed",
            "prompt": prompt(order, kind),
            "agentId": "a1",
            "agentType": agent,
            "content": [{"type": "text", "text": report}],
            "totalDurationMs": 1000,
        },
        "tool_use_id": tool_use_id,
    }


class HealProgressTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def run_hook(self, payload, compact=False):
        self.assertTrue(SCRIPT.is_file(), f"{SCRIPT} is missing")
        text = json.dumps(payload, ensure_ascii=False, separators=(",", ":") if compact else None)
        done = subprocess.run(
            ["sh", str(SCRIPT)], input=text, capture_output=True, text=True, encoding="utf-8",
            env={**os.environ, "TMPDIR": self.tmp.name}, timeout=60,
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stderr, "")
        return done.stdout

    def message(self, payload, **kw):
        out = self.run_hook(payload, **kw)
        self.assertNotEqual(out.strip(), "", "expected a systemMessage, got no output")
        return json.loads(out)["systemMessage"]

    def test_three_agents_each_print_a_line_and_the_last_closes_the_round(self):
        reports = {
            "t1": (1, "location 1 skill-a\n/p/a/SKILL.md | accepted | 7.5 → 9.0 | validate calls 2 | put back 0 | introduced 0 | open 0"),
            "t2": (2, "Rewrote it.\nlocation 2 skill-b\n`/p/b/SKILL.md | restored | 8.0 → 8.0 | validate calls 4 | put back 1 | introduced 0 | open 1`\n- dangling_fragments: a sentence now dangles"),
            "t3": (3, "location 3 skill-c\n/p/c/SKILL.md | refused | 6.0 → 6.0 | validate calls 0 | put back 0 | introduced 0 | open 0\nThe PreToolUse hook guard-config blocked the write: \"no edits\""),
        }
        for tid, (order, _) in reports.items():
            self.assertEqual(self.run_hook(pre(tid, order)), "")
        first = self.message(post("t1", *reports["t1"]))
        self.assertEqual(first, "1 skill-a — accepted (score 7.5 → 9.0)")
        second = self.message(post("t2", *reports["t2"]))
        self.assertEqual(second, "2 skill-b — restored (dangling_fragments: a sentence now dangles)")
        third = self.message(post("t3", *reports["t3"])).split("\n")
        self.assertEqual(len(third), 2)
        self.assertTrue(third[0].startswith("3 skill-c — refused ("), third[0])
        self.assertIn("guard-config", third[0])
        self.assertIn('"no edits"', third[0])
        self.assertRegex(third[1], r"^Round skills done — 1 accepted, 1 restored, 1 refused, \d+\.\d min$")

    def test_non_remedy_agent_prints_nothing(self):
        self.assertEqual(self.run_hook(pre("x1", 1, agent="general-purpose")), "")
        report = "location 1 e\n/p/f.md | accepted | 7.0 → 9.0 | validate calls 1 | put back 0 | introduced 0 | open 0"
        self.assertEqual(self.run_hook(post("x1", 1, report, agent="general-purpose")), "")

    def test_async_launch_prints_nothing_and_keeps_the_round_open(self):
        self.run_hook(pre("a1", 1))
        self.run_hook(pre("a2", 2))
        async_text = "Async agent launched successfully.\nagentId: abc"
        self.assertEqual(self.run_hook(post("a1", 1, async_text)), "")
        report = "location 2 s2\n/p/s2.md | accepted | 7.0 → 9.0 | validate calls 1 | put back 0 | introduced 0 | open 0"
        # a1 is still pending, so the second hand-back must not close the round
        self.assertEqual(self.message(post("a2", 2, report)), "2 s2 — accepted (score 7.0 → 9.0)")

    def test_several_files_aggregate(self):
        self.run_hook(pre("m1", 4, kind="agents"))
        self.run_hook(pre("m2", 5, kind="agents"))
        self.run_hook(pre("m3", 6, kind="agents"))
        rows = (
            "location 4 multi\n"
            "/p/a.md | accepted | 7.0 → 9.0 | validate calls 1 | put back 0 | introduced 0 | open 0\n"
            "/p/b.md | accepted | 6.0 → 8.5 | validate calls 1 | put back 0 | introduced 0 | open 0"
        )
        self.assertEqual(self.message(post("m1", 4, rows, kind="agents")), "4 multi — accepted (score 7.0 → 9.0, 6.0 → 8.5)")
        mixed = (
            "location 5 mixed\n"
            "/p/a.md | accepted | 7.0 → 9.0 | validate calls 1 | put back 0 | introduced 0 | open 0\n"
            "/p/b.md | restored | 6.0 → 6.0 | validate calls 4 | put back 1 | introduced 0 | open 1\nlost_instructions\n"
            "/p/c.md | refused | 6.0 → 6.0 | validate calls 0 | put back 0 | introduced 0 | open 0\nhook h blocked the write"
        )
        self.assertEqual(self.message(post("m2", 5, mixed, kind="agents")), "5 mixed — refused (hook h blocked the write)")
        restored = (
            "location 6 rest\n"
            "/p/a.md | accepted | 7.0 → 9.0 | validate calls 1 | put back 0 | introduced 0 | open 0\n"
            "/p/b.md | restored | 6.0 → 6.0 | validate calls 4 | put back 1 | introduced 0 | open 1\nlost_instructions, narrowed_instructions"
        )
        last = self.message(post("m3", 6, restored, kind="agents")).split("\n")
        self.assertEqual(last[0], "6 rest — restored (lost_instructions, narrowed_instructions)")
        self.assertRegex(last[1], r"^Round agents done — 1 accepted, 1 restored, 1 refused, \d+\.\d min$")

    def test_missing_location_line_falls_back_to_the_kind(self):
        self.run_hook(pre("k1", 9, kind="rules"))
        report = "/p/r.md | accepted | 7.0 → 9.0 | validate calls 1 | put back 0 | introduced 0 | open 0"
        out = self.message(post("k1", 9, report, kind="rules")).split("\n")
        self.assertEqual(out[0], "9 rules — accepted (score 7.0 → 9.0)")

    def test_a_new_round_starts_after_the_previous_one_closed(self):
        report = "location 1 e\n/p/f.md | accepted | 7.0 → 9.0 | validate calls 1 | put back 0 | introduced 0 | open 0"
        for kind in ("skills", "agents"):
            self.run_hook(pre("r-" + kind, 1, kind=kind))
            out = self.message(post("r-" + kind, 1, report, kind=kind), compact=True).split("\n")
            self.assertTrue(out[1].startswith(f"Round {kind} done — 1 accepted, 0 restored, 0 refused"), out)

    def test_a_round_across_kinds_names_every_kind_in_dispatch_order(self):
        report = "location 1 e\n/p/f.md | accepted | 7.0 → 9.0 | validate calls 1 | put back 0 | introduced 0 | open 0"
        self.run_hook(pre("c1", 1, kind="skills"))
        self.run_hook(pre("c2", 2, kind="agents"))
        self.run_hook(pre("c3", 3, kind="skills"))
        self.run_hook(post("c1", 1, report, kind="skills"))
        self.run_hook(post("c2", 2, report, kind="agents"))
        out = self.message(post("c3", 3, report, kind="skills")).split("\n")
        self.assertTrue(out[1].startswith("Round skills, agents done — 3 accepted"), out)

    def test_parallel_hand_backs_close_the_round_exactly_once(self):
        report = "location 1 e\n/p/f.md | accepted | 7.0 → 9.0 | validate calls 1 | put back 0 | introduced 0 | open 0"
        ids = [f"p{i}" for i in range(8)]
        for i, tid in enumerate(ids):
            self.run_hook(pre(tid, i + 1))
        procs = [
            subprocess.Popen(["sh", str(SCRIPT)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8",
                             env={**os.environ, "TMPDIR": self.tmp.name})
            for _ in ids
        ]
        outs = [p.communicate(json.dumps(post(tid, i + 1, report), ensure_ascii=False))[0] for i, (p, tid) in enumerate(zip(procs, ids))]
        messages = [json.loads(o)["systemMessage"] for o in outs]
        closes = [m for m in messages if "\nRound skills done — 8 accepted" in m]
        self.assertEqual(len(closes), 1, messages)
        self.assertEqual(sum("Round" in m for m in messages), 1)

    def test_unrelated_input_prints_nothing(self):
        for text in ("", "not json", '{"hook_event_name": "PreToolUse", "tool_name": "Read"}'):
            done = subprocess.run(["sh", str(SCRIPT)], input=text, capture_output=True, text=True,
                                  env={**os.environ, "TMPDIR": self.tmp.name}, timeout=60)
            self.assertEqual((done.returncode, done.stdout, done.stderr), (0, "", ""))


ROW = "/p/f.md | accepted | 7.0 → 9.0 | validate calls 1 | put back 0 | introduced 0 | open 0"
SHELLS = ["sh"] + (["dash"] if shutil.which("dash") else [])


class HealProgressRobustnessTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state = Path(self.tmp.name) / f"reporails-heal-{SESSION}"

    def env(self, path=None):
        return {**os.environ, "TMPDIR": self.tmp.name, **({"PATH": path} if path else {})}

    def run_script(self, payload, script=SCRIPT, shell="sh", path=None):
        done = subprocess.run([shell, str(script)], input=json.dumps(payload, ensure_ascii=False), capture_output=True,
                              text=True, encoding="utf-8", env=self.env(path), timeout=60)
        return done

    def test_event_detection_needs_no_gnu_sed_alternation(self):
        # A sed without `\|` (BSD/macOS) must still tell Pre from Post.
        real = shutil.which("sed")
        fake = Path(self.tmp.name) / "fakebin"
        fake.mkdir()
        wrapper = fake / "sed"
        wrapper.write_text('#!/bin/sh\nfor a in "$@"; do case "$a" in *\\\\\\|*) exit 1;; esac; done\nexec ' + real + ' "$@"\n')
        wrapper.chmod(wrapper.stat().st_mode | stat.S_IXUSR)
        path = f"{fake}:{os.environ['PATH']}"
        for tid, order in (("b1", 1), ("b2", 2)):
            done = self.run_script(pre(tid, order), path=path)
            self.assertEqual((done.returncode, done.stdout), (0, ""))
        first = self.run_script(post("b1", 1, "location 1 e\n" + ROW), path=path).stdout
        self.assertNotIn("Round", first, "the first hand-back closed the round: Pre was read as Post")
        self.assertIn("Round", self.run_script(post("b2", 2, "location 2 e\n" + ROW), path=path).stdout)

    def test_markdown_table_row_with_leading_pipe_is_read(self):
        self.run_script(pre("t1", 1))
        report = "location 1 tbl\n| `/p/f.md` | accepted | 7.0 → 9.0 | validate calls 1 | put back 0 | introduced 0 | open 0 |"
        out = json.loads(self.run_script(post("t1", 1, report)).stdout)["systemMessage"]
        self.assertTrue(out.startswith("1 tbl — accepted (score 7.0 → 9.0)"), out)

    def test_a_dispatch_that_never_returned_does_not_block_a_later_round(self):
        self.run_script(pre("lost", 1))
        batch = self.state / "batch"
        old = int(time.time()) - 120
        lines = [l.split("\t") for l in batch.read_text().splitlines()]
        batch.write_text("".join("\t".join([l[0], l[1], l[2], str(old), l[4]]) + "\n" for l in lines))
        self.run_script(pre("next", 1))
        out = json.loads(self.run_script(post("next", 1, "location 1 e\n" + ROW)).stdout)["systemMessage"]
        self.assertRegex(out.split("\n")[1], r"^Round skills done — 1 accepted, 0 restored, 0 refused, ")

    def test_restored_reason_is_the_agents_own_text(self):
        self.run_script(pre("r1", 1))
        report = "location 1 e\n/p/f.md | restored | 8.0 → 8.0 | validate calls 4 | put back 1 | introduced 0 | open 1\n  brand_new_check failed, lost_instructions too  "
        out = json.loads(self.run_script(post("r1", 1, report)).stdout)["systemMessage"]
        self.assertTrue(out.startswith("1 e — restored (brand_new_check failed, lost_instructions too)"), out)

    def test_missing_helper_never_blocks_the_dispatch(self):
        for name in ("heal-progress.sh", "heal-notice.sh"):
            bare = Path(self.tmp.name) / ("bare-" + name)
            bare.mkdir()
            shutil.copy(PLUGIN / "hooks" / name, bare / name)
            for shell in SHELLS:
                done = self.run_script(pre("z", 1), script=bare / name, shell=shell)
                self.assertEqual((done.returncode, done.stdout), (0, ""), f"{name} under {shell}")

    def start_dead_pid(self):
        proc = subprocess.Popen(["true"])
        proc.wait()
        return proc.pid

    def test_a_lock_of_a_dead_holder_is_taken_over(self):
        (self.state / "lock.d").mkdir(parents=True)
        (self.state / "lock.d" / "pid").write_text(str(self.start_dead_pid()))
        started = time.time()
        done = self.run_script(pre("l1", 1))
        self.assertEqual(done.returncode, 0)
        self.assertLess(time.time() - started, 5)
        self.assertIn("l1", (self.state / "batch").read_text())

    def test_a_lock_of_a_live_holder_is_waited_on_not_stolen(self):
        holder = subprocess.Popen(["sleep", "60"])
        self.addCleanup(holder.kill)
        (self.state / "lock.d").mkdir(parents=True)
        (self.state / "lock.d" / "pid").write_text(str(holder.pid))
        waiter = subprocess.Popen(["sh", str(SCRIPT)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
                                  encoding="utf-8", env=self.env())
        self.addCleanup(waiter.kill)
        waiter.stdin.write(json.dumps(pre("l2", 1)))
        waiter.stdin.close()
        time.sleep(13)
        self.assertIsNone(waiter.poll(), "the hook stole a live holder's lock")
        holder.kill()
        holder.wait()
        self.assertEqual(waiter.wait(timeout=20), 0)
        self.assertIn("l2", (self.state / "batch").read_text())


class HooksJsonTest(unittest.TestCase):
    def commands(self, event):
        entries = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))["hooks"][event]
        return [(e["matcher"], h["command"]) for e in entries for h in e["hooks"]]

    def test_progress_script_is_wired_on_both_events(self):
        for event in ("PreToolUse", "PostToolUse"):
            wired = [m for m, c in self.commands(event) if "heal-progress.sh" in c]
            self.assertEqual(wired, ["Agent|Task"], event)

    def test_heal_notice_is_still_wired(self):
        wired = [m for m, c in self.commands("PreToolUse") if "heal-notice.sh" in c]
        self.assertEqual(wired, ["Agent|Task"])


if __name__ == "__main__":
    unittest.main()
