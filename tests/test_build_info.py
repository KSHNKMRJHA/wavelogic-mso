import re
import subprocess
import unittest
from pathlib import Path

from branding import get_build_label

REPO_ROOT = Path(__file__).resolve().parents[1]


class BuildLabelTests(unittest.TestCase):
    def test_build_label_has_expected_format(self):
        label = get_build_label()
        self.assertIsNotNone(label)
        self.assertRegex(label, r"^v\d+ · build [0-9a-f]{7,40}$")

    def test_build_label_count_is_positive_integer(self):
        label = get_build_label()
        count = int(label.split(" · ")[0].lstrip("v"))
        self.assertGreater(count, 0)

    def test_build_label_matches_git_head_when_available(self):
        if not (REPO_ROOT / ".git").exists():
            self.skipTest("not a git checkout")
        sha = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "--short=7", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        self.assertTrue(get_build_label().endswith(f"build {sha}"))


if __name__ == "__main__":
    unittest.main()
