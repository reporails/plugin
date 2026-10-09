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


def async_post(tool_use_id, order, kind="skills", session=SESSION):
    body = post(tool_use_id, order, "", kind=kind, session=session)
    body["tool_input"]["run_in_background"] = True
    body["tool_response"] = {"isAsync": True, "status": "async_launched", "agentId": "a" + tool_use_id}
    return body


def notification(tool_use_id, report, status="completed"):
    return (
        "<task-notification>\n<task-id>ae50acfc113748b99</task-id>\n"
        f"<tool-use-id>{tool_use_id}</tool-use-id>\n"
        "<output-file>/tmp/claude-1000/x/tasks/ae50acfc113748b99.output</output-file>\n"
        f"<status>{status}</status>\n<summary>Agent \"d\" finished</summary>\n"
        "<note>A task-notification fires each time this agent stops.</note>\n"
        f"<result>{report}</result>\n"
        "<usage><subagent_tokens>17696</subagent_tokens><tool_uses>0</tool_uses><duration_ms>4534</duration_ms></usage>\n"
        "</task-notification>"
    )


def user_prompt(text, session=SESSION):
    return {
        "session_id": session,
        "transcript_path": "/tmp/t.jsonl",
        "cwd": "/abs/project",
        "prompt_id": "20b8c000-4f8e-4c9b-9e1e-41b73df7d231",
        "permission_mode": "acceptEdits",
        "hook_event_name": "UserPromptSubmit",
        "prompt": text,
    }


def rep(order, element, status, detail, scores="7.5 → 9.0", path="/p/a/SKILL.md", extra=""):
    """A report in the shape remedy-location.md ships: header, one row per file, then the outcome line."""
    row = f"{path} | {status} | {scores} | introduced 0 | edits 1 applied | slots 0 decided | validate calls 2"
    return f"location {order} {element}\n{row}\n{extra}outcome: {order} | {element} | {status} | {detail}"


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
            "t1": (1, rep(1, "skill-a", "accepted", "score 7.5 → 9.0")),
            "t2": (2, "Rewrote it.\n" + rep(2, "skill-b", "restored", "dangling_fragments: a sentence now dangles", scores="8.0 → 8.0", path="/p/b/SKILL.md", extra="Failed checks:\n- dangling_fragments: a sentence now dangles\n")),
            "t3": (3, rep(3, "skill-c", "refused", 'The PreToolUse hook guard-config blocked the write: "no edits"', scores="6.0 → 6.0", path="/p/c/SKILL.md")),
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

    REPORT_1 = rep(1, "skill-a", "accepted", "score 7.5 → 9.0")
    REPORT_2 = rep(2, "skill-b", "restored", "dangling_fragments: a sentence now dangles", scores="8.0 → 8.0", path="/p/b/SKILL.md")

    def background_round(self):
        for tid, order in (("b1", 1), ("b2", 2)):
            self.assertEqual(self.run_hook(pre(tid, order)), "")
        for tid, order in (("b1", 1), ("b2", 2)):
            self.assertEqual(self.run_hook(async_post(tid, order)), "")

    def test_background_notifications_print_a_line_each_and_the_last_closes_the_round(self):
        self.background_round()
        first = self.message(user_prompt(notification("b1", self.REPORT_1)))
        self.assertEqual(first, "1 skill-a — accepted (score 7.5 → 9.0)")
        second = self.message(user_prompt(notification("b2", self.REPORT_2))).split("\n")
        self.assertEqual(second[0], "2 skill-b — restored (dangling_fragments: a sentence now dangles)")
        self.assertEqual(len(second), 2)
        self.assertRegex(second[1], r"^Round skills done — 1 accepted, 1 restored, 0 refused, \d+\.\d min$")

    def test_one_prompt_carrying_two_notifications_prints_both_lines_and_one_close(self):
        self.background_round()
        text = notification("b1", self.REPORT_1) + "\n" + notification("b2", self.REPORT_2)
        lines = self.message(user_prompt(text)).split("\n")
        self.assertEqual(len(lines), 3, lines)
        self.assertEqual(lines[0], "1 skill-a — accepted (score 7.5 → 9.0)")
        self.assertTrue(lines[1].startswith("2 skill-b — restored ("), lines[1])
        self.assertRegex(lines[2], r"^Round skills done — 1 accepted, 1 restored, 0 refused, \d+\.\d min$")

    def test_a_notification_for_an_unknown_tool_use_id_prints_nothing(self):
        self.background_round()
        self.assertEqual(self.run_hook(user_prompt(notification("other", self.REPORT_1))), "")
        # the round is still open: the real hand-backs still close it
        self.message(user_prompt(notification("b1", self.REPORT_1)))
        self.assertIn("Round", self.message(user_prompt(notification("b2", self.REPORT_2))))

    def test_a_notification_with_no_recorded_batch_prints_nothing(self):
        self.assertEqual(self.run_hook(user_prompt(notification("b1", self.REPORT_1))), "")

    def test_a_repeated_notification_prints_nothing_the_second_time(self):
        self.background_round()
        self.message(user_prompt(notification("b1", self.REPORT_1)))
        self.assertEqual(self.run_hook(user_prompt(notification("b1", self.REPORT_1))), "")

    def test_a_plain_user_prompt_prints_nothing(self):
        self.background_round()
        self.assertEqual(self.run_hook(user_prompt("please continue with the heal")), "")
        self.assertEqual(self.run_hook(user_prompt("")), "")

    def test_a_notification_without_an_outcome_line_is_refused(self):
        self.background_round()
        out = self.message(user_prompt(notification("b1", "Agent stopped before reporting.")))
        self.assertEqual(out, "1 skills — refused (no outcome line)")

    def test_compact_json_notifications_are_read(self):
        self.background_round()
        out = self.message(user_prompt(notification("b1", self.REPORT_1)), compact=True)
        self.assertEqual(out, "1 skill-a — accepted (score 7.5 → 9.0)")

    def test_foreground_and_background_hand_backs_share_one_round(self):
        self.run_hook(pre("f1", 1))
        self.run_hook(pre("b2", 2))
        self.run_hook(async_post("b2", 2))
        self.assertEqual(self.message(post("f1", 1, self.REPORT_1)), "1 skill-a — accepted (score 7.5 → 9.0)")
        self.assertIn("Round", self.message(user_prompt(notification("b2", self.REPORT_2))))

    def test_non_remedy_agent_prints_nothing(self):
        self.assertEqual(self.run_hook(pre("x1", 1, agent="general-purpose")), "")
        report = rep(1, "e", "accepted", "score 7.0 → 9.0")
        self.assertEqual(self.run_hook(post("x1", 1, report, agent="general-purpose")), "")

    def test_async_launch_prints_nothing_and_keeps_the_round_open(self):
        self.run_hook(pre("a1", 1))
        self.run_hook(pre("a2", 2))
        async_text = "Async agent launched successfully.\nagentId: abc"
        self.assertEqual(self.run_hook(post("a1", 1, async_text)), "")
        report = rep(2, "s2", "accepted", "score 7.0 → 9.0")
        # a1 is still pending, so the second hand-back must not close the round
        self.assertEqual(self.message(post("a2", 2, report)), "2 s2 — accepted (score 7.0 → 9.0)")

    def test_the_outcome_line_alone_decides_the_location_line(self):
        self.run_hook(pre("m1", 4, kind="agents"))
        self.run_hook(pre("m2", 5, kind="agents"))
        self.run_hook(pre("m3", 6, kind="agents"))
        rows = (
            "location 4 multi\n/p/a.md | accepted | 7.0 → 9.0 | introduced 0\n/p/b.md | accepted | 6.0 → 8.5 | introduced 0\n"
            "outcome: 4 | multi | accepted | score 7.0 → 9.0, 6.0 → 8.5"
        )
        self.assertEqual(self.message(post("m1", 4, rows, kind="agents")), "4 multi — accepted (score 7.0 → 9.0, 6.0 → 8.5)")
        mixed = "location 5 mixed\n/p/b.md | restored | 6.0 → 6.0\nlost_instructions\noutcome: 5 | mixed | refused | hook h blocked the write | twice"
        self.assertEqual(self.message(post("m2", 5, mixed, kind="agents")), "5 mixed — refused (hook h blocked the write | twice)")
        restored = "outcome: 6 | rest | restored | lost_instructions, narrowed_instructions"
        last = self.message(post("m3", 6, restored, kind="agents")).split("\n")
        self.assertEqual(last[0], "6 rest — restored (lost_instructions, narrowed_instructions)")
        self.assertRegex(last[1], r"^Round agents done — 1 accepted, 1 restored, 1 refused, \d+\.\d min$")
        self.assertEqual(sum("Round" in l for l in last), 1)

    def test_an_error_outcome_closes_the_round(self):
        self.run_hook(pre("e1", 1))
        self.run_hook(pre("e2", 2))
        ok = self.message(post("e1", 1, rep(1, "skill-a", "accepted", "score 7.5 → 9.0")))
        self.assertEqual(ok, "1 skill-a — accepted (score 7.5 → 9.0)")
        failed = "outcome: 2 | skill-b | refused | brief_unavailable: the plan could not be fetched"
        lines = self.message(post("e2", 2, failed)).split("\n")
        self.assertEqual(lines[0], "2 skill-b — refused (brief_unavailable: the plan could not be fetched)")
        self.assertRegex(lines[1], r"^Round skills done — 1 accepted, 0 restored, 1 refused, \d+\.\d min$")

    def test_a_hand_back_without_an_outcome_line_is_refused_and_the_round_closes(self):
        self.run_hook(pre("n1", 1))
        self.run_hook(pre("n2", 2))
        self.run_hook(post("n1", 1, rep(1, "skill-a", "accepted", "score 7.5 → 9.0")))
        for report in ("Agent stopped before reporting.", "location 2 skill-b\n/p/b.md | accepted | 7.0 → 9.0 | introduced 0"):
            self.run_hook(pre("n2", 2))
            lines = self.message(post("n2", 2, report)).split("\n")
            self.assertEqual(lines[0], "2 skills — refused (no outcome line)")
            self.assertIn("Round skills done", lines[1])
            self.run_hook(pre("n1", 1))
            self.run_hook(post("n1", 1, rep(1, "skill-a", "accepted", "score 7.5 → 9.0")))

    def test_a_location_header_never_names_the_element(self):
        self.run_hook(pre("h1", 3))
        report = "**location 3 skill-c**\n/p/c.md | accepted | 7.0 → 9.0 | introduced 0\noutcome: 3 | skill-c | accepted | score 7.0 → 9.0"
        self.assertTrue(self.message(post("h1", 3, report)).startswith("3 skill-c — accepted (score 7.0 → 9.0)"))
        self.run_hook(pre("h2", 4))
        report = "Location 4 skill-d\n/p/d.md | accepted | 7.0 → 9.0\noutcome: 4 | skill-d | accepted | score 7.0 → 9.0"
        self.assertTrue(self.message(post("h2", 4, report)).startswith("4 skill-d — accepted (score 7.0 → 9.0)"))

    def test_an_outcome_line_wrapped_in_emphasis_or_quote_is_read(self):
        wrapped = [
            "**outcome: 3 | skill-c | accepted | score 7.1 → 8.0**",
            "_outcome: 3 | skill-c | accepted | score 7.1 → 8.0_",
            "> outcome: 3 | skill-c | accepted | score 7.1 → 8.0",
            "> - ***outcome: 3 | skill-c | accepted | score 7.1 → 8.0***",
        ]
        for i, line in enumerate(wrapped):
            self.run_hook(pre(f"w{i}", 3))
            out = self.message(post(f"w{i}", 3, "location 3 skill-c\n/p/c.md | accepted | 7.1 → 8.0\n" + line)).split("\n")
            self.assertEqual(out[0], "3 skill-c — accepted (score 7.1 → 8.0)", line)

    def test_outcome_label_is_matched_in_any_case_and_inside_a_table_row(self):
        wrapped = [
            "Outcome: 3 | skill-c | accepted | score 7.1 → 8.0",
            "**Outcome:** 3 | skill-c | accepted | score 7.1 → 8.0",
            "| outcome: 3 | skill-c | accepted | score 7.1 → 8.0 |",
            "| **Outcome:** 3 | skill-c | accepted | score 7.1 → 8.0 |",
        ]
        for i, line in enumerate(wrapped):
            self.run_hook(pre(f"o{i}", 3))
            out = self.message(post(f"o{i}", 3, "location 3 skill-c\n" + line)).split("\n")
            self.assertEqual(out[0], "3 skill-c — accepted (score 7.1 → 8.0)", line)

    def test_a_stale_pending_row_of_the_same_order_does_not_block_the_next_round(self):
        self.run_hook(pre("lost", 1))  # refused or interrupted: its hand-back never fires
        self.run_hook(pre("n1", 1))
        self.run_hook(pre("n2", 2))
        self.message(post("n1", 1, rep(1, "skill-a", "accepted", "score 7.5 → 9.0")))
        out = self.message(post("n2", 2, rep(2, "skill-b", "accepted", "score 7.5 → 9.0"))).split("\n")
        self.assertRegex(out[1], r"^Round skills done — 2 accepted, 0 restored, 0 refused, ")

    def test_a_long_detail_is_cut_between_words_never_inside_a_character(self):
        detail = "score " + ", ".join(f"7.{i % 10} → 9.{i % 10}" for i in range(20))
        self.run_hook(pre("long", 1))
        line = self.message(post("long", 1, rep(1, "skill-a", "accepted", detail))).split("\n")[0]
        self.assertNotIn("\ufffd", line)
        self.assertTrue(line.endswith("…)"), line)
        self.assertLessEqual(len(line.encode("utf-8")), 260)
        self.assertTrue(detail.startswith(line.split("(", 1)[1][:-2].rstrip("…").rstrip(", ")))

    def test_a_lead_in_line_never_enters_the_detail(self):
        self.run_hook(pre("l1", 2))
        report = (
            "location 2 skill-b\n/p/b.md | restored | 8.0 → 8.0 | introduced 0\nFailed checks:\n- dangling_fragments\n"
            "outcome: 2 | skill-b | restored | dangling_fragments"
        )
        self.assertTrue(self.message(post("l1", 2, report)).startswith("2 skill-b — restored (dangling_fragments)"))

    def test_the_eleventh_dispatch_held_back_does_not_split_the_round(self):
        # The client holds the 11th dispatch back until one agent finishes, about 90 s after the first ten.
        def done(i):
            return post(f"d{i}", i, rep(i, f"skill-{i}", "accepted", "score 7.5 → 9.0"))
        for i in range(1, 11):
            self.run_hook(pre(f"d{i}", i))
        self.assertNotIn("Round", self.message(done(1)))
        batch = Path(self.tmp.name) / f"reporails-heal-{SESSION}" / "batch"
        old = int(time.time()) - 90
        rows = [l.split("\t") for l in batch.read_text().splitlines()]
        batch.write_text("".join("\t".join([r[0], r[1], r[2], str(old), r[4]]) + "\n" for r in rows))
        self.run_hook(pre("d11", 11))
        messages = [self.message(done(i)) for i in (2, 3, 4, 5, 6, 7, 8, 9, 11, 10)]
        self.assertEqual([m for m in messages if "Round" in m][0].count("Round"), 1)
        self.assertEqual(sum("Round" in m for m in messages), 1, messages)
        self.assertRegex(messages[-1].split("\n")[1], r"^Round skills done — 11 accepted, 0 restored, 0 refused, ")

    def test_a_dispatch_of_another_kind_drops_the_rows_of_an_earlier_round(self):
        self.run_hook(pre("old", 1, kind="skills"))
        self.run_hook(pre("new", 1, kind="agents"))
        out = self.message(post("new", 1, rep(1, "agent-a", "accepted", "score 7.5 → 9.0"), kind="agents")).split("\n")
        self.assertTrue(out[1].startswith("Round agents done — 1 accepted"), out)

    def test_missing_location_line_falls_back_to_the_kind(self):
        self.run_hook(pre("k1", 9, kind="rules"))
        report = "outcome: 9 | | accepted | score 7.0 → 9.0"
        out = self.message(post("k1", 9, report, kind="rules")).split("\n")
        self.assertEqual(out[0], "9 rules — accepted (score 7.0 → 9.0)")

    def test_a_new_round_starts_after_the_previous_one_closed(self):
        report = rep(1, "e", "accepted", "score 7.0 → 9.0")
        for kind in ("skills", "agents"):
            self.run_hook(pre("r-" + kind, 1, kind=kind))
            out = self.message(post("r-" + kind, 1, report, kind=kind), compact=True).split("\n")
            self.assertTrue(out[1].startswith(f"Round {kind} done — 1 accepted, 0 restored, 0 refused"), out)

    def test_a_round_across_kinds_names_every_kind_in_dispatch_order(self):
        report = rep(1, "e", "accepted", "score 7.0 → 9.0")
        self.run_hook(pre("c1", 1, kind="skills"))
        self.run_hook(pre("c2", 2, kind="agents"))
        self.run_hook(pre("c3", 3, kind="skills"))
        self.run_hook(post("c1", 1, report, kind="skills"))
        self.run_hook(post("c2", 2, report, kind="agents"))
        out = self.message(post("c3", 3, report, kind="skills")).split("\n")
        self.assertTrue(out[1].startswith("Round skills, agents done — 3 accepted"), out)

    def test_parallel_hand_backs_close_the_round_exactly_once(self):
        report = rep(1, "e", "accepted", "score 7.0 → 9.0")
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


ROW = "/p/f.md | accepted | 7.0 → 9.0 | introduced 0 | edits 1 applied | slots 0 decided | validate calls 1\noutcome: 1 | e | accepted | score 7.0 → 9.0"
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
        self.assertIn("Round", self.run_script(post("b2", 2, "location 2 e\n" + ROW.replace("outcome: 1","outcome: 2")), path=path).stdout)

    def test_outcome_line_in_a_list_item_or_backticks_is_read(self):
        self.run_script(pre("t1", 1))
        report = "location 1 tbl\n- `outcome: 1 | tbl | accepted | score 7.0 → 9.0`"
        out = json.loads(self.run_script(post("t1", 1, report)).stdout)["systemMessage"]
        self.assertTrue(out.startswith("1 tbl — accepted (score 7.0 → 9.0)"), out)

    def test_a_dispatch_that_never_returned_does_not_block_a_later_round(self):
        self.run_script(pre("lost", 1))
        batch = self.state / "batch"
        old = int(time.time()) - 3600
        lines = [l.split("\t") for l in batch.read_text().splitlines()]
        batch.write_text("".join("\t".join([l[0], l[1], l[2], str(old), l[4]]) + "\n" for l in lines))
        self.run_script(pre("next", 1))
        out = json.loads(self.run_script(post("next", 1, "location 1 e\n" + ROW)).stdout)["systemMessage"]
        self.assertRegex(out.split("\n")[1], r"^Round skills done — 1 accepted, 0 restored, 0 refused, ")

    def test_restored_detail_is_the_agents_own_text(self):
        self.run_script(pre("r1", 1))
        report = "outcome: 1 | e | restored | brand_new_check failed, lost_instructions too  "
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

    def test_progress_script_is_wired_on_user_prompt_submit_without_a_matcher(self):
        entries = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))["hooks"]["UserPromptSubmit"]
        wired = [e.get("matcher") for e in entries for h in e["hooks"] if "heal-progress.sh" in h["command"]]
        self.assertEqual(wired, [None])

    def test_heal_notice_is_still_wired(self):
        wired = [m for m, c in self.commands("PreToolUse") if "heal-notice.sh" in c]
        self.assertEqual(wired, ["Agent|Task"])


if __name__ == "__main__":
    unittest.main()
