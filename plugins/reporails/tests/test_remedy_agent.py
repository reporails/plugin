"""Guard: the remedy agent must refuse every tool that can start a helper agent or a shell.

Run: python3 -m unittest discover plugins/reporails/tests
Set REMEDY_MD to test another copy of agents/remedy.md.
"""
import os
import re
import unittest
from pathlib import Path

REMEDY_MD = Path(os.environ.get("REMEDY_MD") or Path(__file__).resolve().parents[1] / "agents" / "remedy.md")
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


class RemedyAgentTest(unittest.TestCase):
    def test_disallowed_tools_cover_every_helper_starter(self):
        disallowed = frontmatter_disallowed_tools(REMEDY_MD.read_text(encoding="utf-8"))
        missing = [tool for tool in HELPER_STARTERS if tool not in disallowed]
        self.assertEqual(missing, [], f"remedy.md disallowedTools lacks: {', '.join(missing)}")

    def test_explain_is_denied_and_named_in_tool_paragraph(self):
        text = REMEDY_MD.read_text(encoding="utf-8")
        self.assertIn("mcp__plugin_reporails_reporails__explain", frontmatter_disallowed_tools(text))
        self.assertIn("Do not call `explain`", text)

    def test_every_remedy_brief_call_carries_has_guide(self):
        for path in (REMEDY_MD, REMEDY_MD.parents[1] / "skills" / "ails" / "workflows" / "heal.md"):
            text = path.read_text(encoding="utf-8")
            calls = re.findall(r"`remedy_brief\(([^`]*)\)`", text)
            for call in calls:
                self.assertIn("has_guide", call, f"{path.name}: remedy_brief({call})")
        self.assertIn("has_guide", REMEDY_MD.read_text(encoding="utf-8"))
        self.assertIn("has_guide=true", (REMEDY_MD.parents[1] / "skills" / "ails" / "workflows" / "heal.md").read_text(encoding="utf-8"))

    def test_put_back_step_covers_added_reasons(self):
        self.assertIn("`added_reasons`", REMEDY_MD.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
