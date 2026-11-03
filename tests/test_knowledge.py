"""Detect broken source links and accidental links to private feedback."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class KnowledgeLinksTests(unittest.TestCase):
    def test_local_evidence_links_exist_and_stay_in_public_source(self):
        for page in (ROOT / "knowledge").glob("*.md"):
            for link in re.findall(r"\]\(([^)]+)\)", page.read_text(encoding="utf-8")):
                if link.startswith(("https://", "http://")):
                    continue
                target = (page.parent / link.split("#", 1)[0]).resolve()
                self.assertTrue(target.is_relative_to(ROOT), (page, link))
                self.assertNotIn("feedback", target.relative_to(ROOT).parts, (page, link))
                self.assertTrue(target.is_file(), (page, link))

    def test_runtime_skill_does_not_load_development_knowledge(self):
        self.assertNotIn("knowledge/", (ROOT / "SKILL.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
