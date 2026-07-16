"""Tests for the thin platform runner scripts."""

import json
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path
from unittest import TestCase


PROJECT = Path(__file__).resolve().parents[1]


class RunnerTests(TestCase):
    def test_posix_runner_forwards_every_argument(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            scripts = project / "scripts"
            python_dir = project / ".venv" / "bin"
            scripts.mkdir()
            python_dir.mkdir(parents=True)
            shutil.copy(PROJECT / "scripts" / "run.sh", scripts / "run.sh")

            fake_python = python_dir / "python"
            fake_python.write_text(
                "#!/usr/bin/env python3\n"
                "import json, sys\n"
                "print(json.dumps(sys.argv[1:]))\n",
                encoding="utf-8",
            )
            fake_python.chmod(fake_python.stat().st_mode | stat.S_IXUSR)

            completed = subprocess.run(
                [
                    "bash",
                    str(scripts / "run.sh"),
                    "example.py",
                    "alpha",
                    "two words",
                ],
                check=True,
                capture_output=True,
                text=True,
            )

        self.assertEqual(
            json.loads(completed.stdout),
            ["example.py", "alpha", "two words"],
        )

    def test_powershell_runner_forwards_arguments_and_exit_code(self):
        script = (PROJECT / "scripts" / "run.ps1").read_text(encoding="utf-8")

        self.assertIn("& $Python @args", script)
        self.assertIn("exit $LASTEXITCODE", script)
