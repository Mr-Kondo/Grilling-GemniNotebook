"""Lifecycle tests use a disposable HOME, never the user's installed skills."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
NAME = "grilling-gemini-notebook"


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="skill-install-")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.repo = self.home / "repo"
        shutil.copytree(ROOT, self.repo, ignore=shutil.ignore_patterns(".git", "feedback", "__pycache__"))
        self.target = self.home / ".agents/skills" / NAME
        self.env = dict(os.environ, HOME=str(self.home), PYTHONDONTWRITEBYTECODE="1")
        bin_dir = self.home / "bin"
        bin_dir.mkdir()
        nlm = bin_dir / "nlm"
        nlm.write_text("#!/bin/sh\nexit 0\n")
        nlm.chmod(0o755)
        self.env["PATH"] = str(bin_dir) + os.pathsep + os.environ["PATH"]

    def run_installer(self, *args):
        return subprocess.run(["bash", str(self.repo / "scripts/install.sh"), *args],
                              env=self.env, text=True, capture_output=True, timeout=30)

    def assert_ok(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_install_update_uninstall_and_backup(self):
        self.assert_ok(self.run_installer("--install"))
        (self.target / "local-note.txt").write_text("keep my local change")
        self.assert_ok(self.run_installer("--update"))
        backups = self.home / ".local/state" / NAME / "backups"
        self.assertEqual(len(list(backups.rglob("local-note.txt"))), 1)
        self.assert_ok(self.run_installer("--verify"))
        self.assert_ok(self.run_installer("--uninstall"))
        self.assertFalse(self.target.exists())
        self.assert_ok(self.run_installer("--uninstall"))
        self.assertTrue(list(backups.rglob("SKILL.md")))

    def test_does_not_ship_logs_or_knowledge(self):
        for directory in ("feedback", "knowledge", "adr"):
            path = self.repo / directory
            path.mkdir(exist_ok=True)
            (path / "not-for-runtime.md").write_text("private or maintenance-only")
        self.assert_ok(self.run_installer())
        for directory in ("feedback", "knowledge", "adr", "tests"):
            self.assertFalse((self.target / directory).exists())
        self.assertFalse((self.target / "references/update-workflow.md").exists())

    def test_refuses_foreign_skill_on_update_and_uninstall(self):
        self.target.mkdir(parents=True)
        (self.target / "SKILL.md").write_text("---\nname: another-skill\n---\n")
        for mode in ("--update", "--uninstall"):
            self.assertNotEqual(self.run_installer(mode).returncode, 0)
            self.assertIn("another-skill", (self.target / "SKILL.md").read_text())

    def test_invalid_source_preserves_existing_install(self):
        self.assert_ok(self.run_installer())
        original = (self.target / "VERSION").read_bytes()
        (self.repo / "LICENSE").unlink()
        self.assertNotEqual(self.run_installer("--update").returncode, 0)
        self.assertEqual((self.target / "VERSION").read_bytes(), original)

    def test_symlink_is_backed_up_without_modifying_its_destination(self):
        self.assert_ok(self.run_installer())
        elsewhere = self.home / "original-skill"
        self.target.rename(elsewhere)
        self.target.symlink_to(elsewhere, target_is_directory=True)
        (elsewhere / "local-note.txt").write_text("untouched")
        self.assert_ok(self.run_installer("--update"))
        self.assertFalse(self.target.is_symlink())
        self.assertEqual((elsewhere / "local-note.txt").read_text(), "untouched")
        self.assertTrue(any(p.is_symlink() for p in
                            (self.home / ".local/state" / NAME / "backups").rglob("*")))

    def test_unknown_option_is_rejected(self):
        self.assertNotEqual(self.run_installer("--typo").returncode, 0)
        self.assertFalse(self.target.exists())

    def test_failed_swap_restores_previous_directory(self):
        self.assert_ok(self.run_installer())
        (self.target / "local-note.txt").write_text("restore me")
        mv = self.home / "bin/mv"
        real_mv = shutil.which("mv")
        mv.write_text('#!/bin/sh\ncase "$1" in *.stage.*) exit 1;; esac\n'
                      + 'exec "' + real_mv + '" "$@"\n')
        mv.chmod(0o755)
        self.assertNotEqual(self.run_installer("--update").returncode, 0)
        self.assertEqual((self.target / "local-note.txt").read_text(), "restore me")
        self.assertFalse(list(self.target.parent.glob(NAME + ".stage.*")))


if __name__ == "__main__":
    unittest.main()
