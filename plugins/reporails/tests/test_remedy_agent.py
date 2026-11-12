"""Guard: the remedy agent must refuse every tool that can start a helper agent or a shell.

Run: python3 -m unittest discover plugins/reporails/tests
Set REMEDY_MD to test another copy of agents/remedy.md.
"""
import json
import os
import re
import unittest
from pathlib import Path

REMEDY_MD = Path(os.environ.get("REMEDY_MD") or Path(__file__).resolve().parents[1] / "agents" / "remedy.md")
HEAL_MD = REMEDY_MD.parents[1] / "skills" / "ails" / "workflows" / "heal.md"
PROC_MD = REMEDY_MD.parents[1] / "skills" / "ails" / "workflows" / "remedy-location.md"
SKILL_MD = REMEDY_MD.parents[1] / "skills" / "ails" / "SKILL.md"
README_MD = REMEDY_MD.parents[3] / "README.md"
PROC_SECTIONS = ("Plan retrieval", "What the plan carries", "Original text", "Apply the edits", "Decide the slots",
                 "Hoist slots", "When a write is refused", "Validate", "Host instructions",
                 "The preservation contract", "Outcome report")
HELPER_STARTERS = ("Agent", "Task", "Workflow", "Bash", "PowerShell", "Skill", "SendMessage", "RemoteTrigger")


def frontmatter_disallowed_tools(text):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise AssertionError("remedy.md has no frontmatter")
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, _, value = line.partition(":")
        if key.strip() == "disallowedTools":
            return [tool.strip() for tool in value.split(",") if tool.strip()]
    raise AssertionError("remedy.md frontmatter has no disallowedTools")


def section(text, name):
    m = re.search(rf"^(#+) {re.escape(name)}$", text, re.M)
    if not m:
        raise AssertionError(f"no section {name}")
    rest = text[m.end():]
    nxt = re.search(rf"^#{{1,{len(m.group(1))}}} ", rest, re.M)
    return rest[: nxt.start()] if nxt else rest


class RemedyAgentTest(unittest.TestCase):
    def test_disallowed_tools_cover_every_helper_starter(self):
        disallowed = frontmatter_disallowed_tools(REMEDY_MD.read_text(encoding="utf-8"))
        missing = [tool for tool in HELPER_STARTERS if tool not in disallowed]
        self.assertEqual(missing, [], f"remedy.md disallowedTools lacks: {', '.join(missing)}")

    def test_explain_is_denied_and_named_in_tool_paragraph(self):
        text = REMEDY_MD.read_text(encoding="utf-8")
        self.assertIn("mcp__plugin_reporails_reporails__explain", frontmatter_disallowed_tools(text))
        self.assertIn("Do not call `explain`", PROC_MD.read_text(encoding="utf-8"))

    def test_no_surface_names_heal_apply(self):
        for path in (HEAL_MD, PROC_MD, REMEDY_MD, SKILL_MD):
            self.assertNotIn("heal_apply", path.read_text(encoding="utf-8"), path.name)

    def test_every_remedy_brief_call_carries_has_guide(self):
        for path in (REMEDY_MD, HEAL_MD, PROC_MD):
            text = path.read_text(encoding="utf-8")
            calls = re.findall(r"`remedy_brief\(([^`]*)\)`", text)
            for call in calls:
                self.assertIn("has_guide", call, f"{path.name}: remedy_brief({call})")
        self.assertIn("has_guide", PROC_MD.read_text(encoding="utf-8"))
        self.assertIn("`remedy_brief(path, location, targets, has_guide=true)`", PROC_MD.read_text(encoding="utf-8"))

    def test_brief_call_has_no_part_or_paging(self):
        for path in (REMEDY_MD, HEAL_MD, PROC_MD):
            text = path.read_text(encoding="utf-8")
            for call in re.findall(r"`remedy_brief\(([^`]*)\)`", text):
                self.assertNotIn("part", call, f"{path.name}: remedy_brief({call})")
            for gone in ("total_parts", "next_part"):
                self.assertNotIn(gone, text, f"{path.name} still pages: {gone}")
        self.assertIn("has_guide=true", PROC_MD.read_text(encoding="utf-8"))

    def test_edits_are_applied_verbatim(self):
        text = PROC_MD.read_text(encoding="utf-8")
        self.assertIn("`edits`", text)
        self.assertIn("verbatim", text)
        self.assertIn("`old_string`", text)
        self.assertIn("`before`", text)
        self.assertIn("`after`", text)

    def test_slots_are_line_or_section_bound(self):
        text = PROC_MD.read_text(encoding="utf-8")
        for token in ("`slots`", "`bound`", "`line`", "`section`", "`ops[op]`", "`guides[rule]`"):
            self.assertIn(token, text)
        self.assertIn("Never change any other line", text)

    def test_conformance_and_preservation_restore(self):
        text = PROC_MD.read_text(encoding="utf-8")
        self.assertIn("`conformance.ok`", text)
        self.assertIn("`preservation.ok`", text)
        self.assertIn("original text back", text)

    def test_no_whole_file_rewrite_left(self):
        for path in (REMEDY_MD, HEAL_MD, PROC_MD):
            text = path.read_text(encoding="utf-8")
            for gone in ("mechanical_fixes", "artifact_rules", "relations", "BEGIN GENERATED", "Ideal instruction guide"):
                self.assertNotIn(gone, text, f"{path.name} still mentions {gone}")

    def test_hoist_is_reported_not_applied(self):
        text = PROC_MD.read_text(encoding="utf-8")
        hoist = section(text, "Hoist slots")
        for token in ("`hoist`", "`also`", "[path, line]", "Leave the line", "left:"):
            self.assertIn(token, hoist)
        for gone in ("verbatim into the file at `to`", "restore all three", "delete the partner", "`also.path`"):
            self.assertNotIn(gone, text)
        self.assertIn("the same line is in", text)
        heal = HEAL_MD.read_text(encoding="utf-8")
        self.assertIn("`hoist`", heal)
        self.assertIn("move <file>:<line> into <to>", heal)
        self.assertNotIn("delete the partner", heal)

    def test_procedure_file_holds_each_section_once(self):
        text = PROC_MD.read_text(encoding="utf-8")
        for name in PROC_SECTIONS:
            self.assertEqual(len(re.findall(rf"^#+ {re.escape(name)}$", text, re.M)), 1, name)

    def test_agent_and_inline_path_follow_the_procedure_without_restating_it(self):
        agent = REMEDY_MD.read_text(encoding="utf-8")
        heal = HEAL_MD.read_text(encoding="utf-8")
        self.assertIn("remedy-location.md", heal)
        self.assertIn("procedure:", agent)
        self.assertNotIn("../../../agents/remedy.md", heal)
        for name in PROC_SECTIONS:
            self.assertNotRegex(agent, rf"(?m)^#+ {re.escape(name)}$")
            self.assertNotRegex(heal, rf"(?m)^#+ {re.escape(name)}$")
        for restated in ("old_string", "conformance.ok", "Apply every `edits`", "circuit_breaker"):
            self.assertNotIn(restated, agent)
        inline = section(heal, "Inline path")
        for restated in ("old_string", "conformance.ok", "Apply every `edits`", "hoist"):
            self.assertNotIn(restated, inline)
        self.assertIn("remedy-location.md", inline)

    def test_acceptance_requires_no_score_fall(self):
        validate = section(PROC_MD.read_text(encoding="utf-8"), "Validate")
        accept = next(l for l in validate.splitlines() if l.startswith("1."))
        self.assertIn("`score_after`", accept)
        self.assertIn("`score_before`", accept)

    def test_per_file_check_carries_no_targets(self):
        proc = PROC_MD.read_text(encoding="utf-8")
        self.assertIn("without `targets`", proc)
        heal = HEAL_MD.read_text(encoding="utf-8")
        self.assertIn("per-file `validate(path=<file>)` check", heal.splitlines()[7])

    def test_finish_uses_only_reported_fields(self):
        heal = HEAL_MD.read_text(encoding="utf-8")
        finish = section(heal, "Finish")
        loop = section(heal, "The loop")
        outcome = section(PROC_MD.read_text(encoding="utf-8"), "Outcome report")
        for gone in ("gate_mover` and `conditional` fixes", "`kept`", "rounds used"):
            self.assertNotIn(gone, finish + loop)
        self.assertIn("introduced <n>", outcome)
        self.assertIn("introduced", finish)

    def test_finish_receipt_carries_made_direct_and_made_specific_lanes(self):
        heal = HEAL_MD.read_text(encoding="utf-8")
        finish = section(heal, "Finish")
        outcome = section(PROC_MD.read_text(encoding="utf-8"), "Outcome report")
        receipt = finish[finish.index("Report, in this order:"):finish.index("Write the same receipt")]
        items = [line for line in receipt.splitlines()[1:] if line.strip()]
        for number, line in enumerate(items, 1):
            self.assertTrue(line.startswith(f"{number}. "), f"unnumbered or out-of-order line in the receipt list: {line!r}")
        titles = [re.match(r"\d+\. (.*)", line).group(1) for line in items]
        lead = [i for i, t in enumerate(titles) if t.startswith("The compression line")]
        direct = [i for i, t in enumerate(titles) if t.startswith('"Made direct"')]
        specific = [i for i, t in enumerate(titles) if t.startswith('"Made specific"')]
        left = [i for i, t in enumerate(titles) if t.startswith('"Left for you"')]
        score = [i for i, t in enumerate(titles) if t.startswith("Last, and secondary")]
        self.assertEqual((lead, direct, specific), ([0], [3], [4]))
        self.assertLess(specific[0], left[0])
        self.assertLess(left[0], score[0])
        shapes = {"made direct": "<text> → <new_text>", "made specific": "<before> → <after>"}
        for lane, line in (("made direct", items[direct[0]]), ("made specific", items[specific[0]])):
            self.assertIn(f"`{lane}: {shapes[lane]}`", line)
            self.assertIn("from the `accepted` rows", line)
            self.assertIn("as reported", line)
        self.assertNotIn("preservation.", receipt)
        self.assertNotIn("repair", receipt.lower())
        self.assertIn("same receipt", finish)
        for lane, shape in shapes.items():
            self.assertIn(f"`{lane}: {shape}`", outcome)
        for key in ("made_direct", "made_specific"):
            self.assertIn(f"`preservation.{key}:`", outcome)
        self.assertIn("each followed by a compact list", outcome)
        # Recorded live validate reply lines; the procedure must name each key they carry.
        recorded = {
            "made_direct": 'preservation.made_direct: [{"line":13,"text":"You should probably prefer small functions over long ones.","new_line":13,"new_text":"Write small functions instead of long ones."}]',
            "made_specific": 'preservation.made_specific: [{"line":22,"before":"Run the linter before committing.","after":"Run `uv run ruff check src/` before committing."}]',
        }
        for key, reply in recorded.items():
            for field in re.findall(r'"(\w+)":', reply):
                self.assertIn(f"`{field}`", outcome, f"{key}: {field}")
        self.assertNotIn('{"line", "before", "after"}', outcome)
        loop = section(heal, "The loop")
        step3 = loop[loop.index("3. Collect"):loop.index("\n4. ")]
        for lane in ("`made direct:`", "`made specific:`"):
            self.assertIn(lane, step3)
        self.assertIn("`preservation.ok: true`", outcome)
        self.assertIn("`accepted`", outcome)

    def test_public_docs_state_only_what_the_user_gets(self):
        for path in (README_MD, SKILL_MD):
            text = path.read_text(encoding="utf-8").lower()
            for gone in ("exact edits", "bounded decisions", "partner", "plan of", "hoist", "bounded"):
                self.assertNotIn(gone, text, f"{path.name}: {gone}")

    def test_heal_inline_path_is_first_class(self):
        text = HEAL_MD.read_text(encoding="utf-8")
        self.assertIn("## Inline path", text)
        self.assertNotIn("## Inline rewrite", text)
        self.assertIn("on any client", text)

    def test_finish_names_the_scripted_fix_count(self):
        finish = section(HEAL_MD.read_text(encoding="utf-8"), "Finish")
        self.assertIn("edits <n> applied", finish)
        self.assertIn("`accepted` rows", finish)

    def test_inline_path_writes_location_and_round_close_lines_on_every_client(self):
        heal = HEAL_MD.read_text(encoding="utf-8")
        inline = section(heal, "Inline path")
        self.assertIn("every client, Claude Code included", inline)
        self.assertIn("round-close line", inline)
        self.assertIn("step 3", inline)
        self.assertIn("step 4", inline)
        self.assertNotIn("Round <kind> done", inline)
        loop = section(heal, "The loop")
        for line in loop.splitlines():
            if "the plugin prints" in line:
                self.assertIn("dispatched `remedy` sub-agent", line)
        self.assertNotIn("Do not write them again on Claude Code.", loop)

    def test_start_block_is_shown_before_round_one(self):
        heal = HEAL_MD.read_text(encoding="utf-8")
        start = section(heal, "Start block")
        self.assertIn("before round 1", start)
        self.assertIn("do not write the start block only in your thinking", start)
        self.assertIn("Start round 1 only after the start block is shown", start)
        self.assertEqual(heal.count("Round <kind> done"), 1)

    def test_slot_change_follows_its_ops_line_in_place_of_op(self):
        proc = PROC_MD.read_text(encoding="utf-8")
        carries = section(proc, "What the plan carries")
        self.assertIn("change", carries)
        slots = section(proc, "Decide the slots")
        self.assertIn("ops[<change", slots)
        self.assertNotIn("repeat exactly that object", slots)
        self.assertNotIn("split-repeat", slots)

    def test_claude_code_carve_out_covers_only_dispatched_sub_agent_locations(self):
        loop = section(HEAL_MD.read_text(encoding="utf-8"), "The loop")
        step3 = next(l for l in loop.splitlines() if "the plugin prints" in l)
        self.assertIn("dispatched", step3)
        self.assertIn("sub-agent", step3)
        self.assertNotIn("worked by a `remedy` agent", step3)
        step4 = next(l for l in loop.splitlines() if l.startswith("4."))
        self.assertIn("every location", step4)
        self.assertIn("dispatched", step4)
        self.assertRegex(loop, r"(?i)inline location[^\n]*round-close line[^\n]*whole round")

    def test_start_block_ordering_rule_asks_nothing_of_the_host_project(self):
        start = section(HEAL_MD.read_text(encoding="utf-8"), "Start block")
        self.assertIn("before any other reply text or tool call that follows the initial `validate` reply", start)
        self.assertNotIn("Answer anything else", start)
        self.assertNotIn("host project asks", start)

    def test_slot_change_line_wins_over_the_rule_pass_example(self):
        slots = section(PROC_MD.read_text(encoding="utf-8"), "Decide the slots")
        self.assertIn("the `change` line wins", slots)

    def test_inline_lines_are_reply_text_not_only_thinking(self):
        inline = section(HEAL_MD.read_text(encoding="utf-8"), "Inline path")
        self.assertIn("reply text the user sees", inline)
        self.assertIn("before your next tool call", inline)
        self.assertIn("Do not write them only in your thinking", inline)

    def test_every_report_ends_with_one_outcome_line_for_every_outcome(self):
        proc = PROC_MD.read_text(encoding="utf-8")
        report = section(proc, "Outcome report")
        self.assertIn("`outcome: <order> | <element> | <accepted, restored or refused> | <detail>`", report)
        self.assertIn("last line", report)
        plan = section(proc, "Plan retrieval")
        self.assertIn("outcome line", plan)
        self.assertIn("refused", plan)
        agent = REMEDY_MD.read_text(encoding="utf-8")
        self.assertIn("outcome: <order> | <kind> | refused |", agent)

    def test_host_instructions_are_described_in_user_terms(self):
        for path in (PROC_MD, HEAL_MD, SKILL_MD, REMEDY_MD):
            text = path.read_text(encoding="utf-8").lower()
            for gone in ("doctrine", "reply-format", "reply format"):
                self.assertNotIn(gone, text, f"{path.name}: {gone}")
        host = section(PROC_MD.read_text(encoding="utf-8"), "Host instructions")
        self.assertIn("whatever the project asks of replies", host)

    def test_start_block_reads_the_skipped_groups_by_code(self):
        start = section(HEAL_MD.read_text(encoding="utf-8"), "Start block")
        for token in ("`code`", "`excluded`", "`at-ceiling`", "`leave-it`"):
            self.assertIn(token, start)
        self.assertNotIn("whose `reason` is", start)
        self.assertIn("`reason` sentence", section(HEAL_MD.read_text(encoding="utf-8"), "Finish"))

    def test_skill_md_says_the_per_file_check_carries_no_targets(self):
        skill = SKILL_MD.read_text(encoding="utf-8")
        self.assertNotIn("into every `validate` and `remedy_brief` call", skill)
        self.assertIn("workflows/heal.md", skill)
        self.assertNotIn("remedy_brief", skill.split("`$ARGUMENTS` after")[1])

    def test_skill_version_matches_every_manifest(self):
        plugin = REMEDY_MD.parents[1]
        versions = {json.loads(p.read_text(encoding="utf-8"))["version"] for p in (
            plugin / "plugin.json", plugin / ".claude-plugin" / "plugin.json", plugin / ".codex-plugin" / "plugin.json")}
        self.assertEqual(len(versions), 1, versions)
        m = re.search(r'^\s+version: "([^"]+)"', SKILL_MD.read_text(encoding="utf-8"), re.M)
        self.assertIsNotNone(m)
        self.assertEqual({m.group(1)}, versions)

    def test_the_outcome_line_status_is_the_locations_status_everywhere(self):
        heal = HEAL_MD.read_text(encoding="utf-8")
        loop = section(heal, "The loop")
        self.assertIn("status on its `outcome:` line", loop)
        self.assertIn("per-file details", loop)
        self.assertIn("`outcome:` line", section(heal, "Finish"))

    def test_the_targets_rule_lives_in_heal_md(self):
        carry = HEAL_MD.read_text(encoding="utf-8").splitlines()[7]
        for token in ("`remedy_brief`", "run-level `validate`"):
            self.assertIn(token, carry)


if __name__ == "__main__":
    unittest.main()
