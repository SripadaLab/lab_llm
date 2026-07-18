"""Tests for the thin platform runner scripts."""

import json
import os
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path
from unittest import TestCase, skipIf


PROJECT = Path(__file__).resolve().parents[1]


class RunnerTests(TestCase):
    def test_setup_scripts_install_every_workshop_extra(self):
        posix = (PROJECT / "scripts" / "setup.sh").read_text(encoding="utf-8")
        powershell = (PROJECT / "scripts" / "setup.ps1").read_text(
            encoding="utf-8"
        )

        self.assertIn('${PROJECT}[agents,privacy]', posix)
        self.assertIn('${Project}[agents,privacy]', powershell)

    def test_windows_setup_stays_local_and_checks_native_failures(self):
        script = (PROJECT / "scripts" / "setup.ps1").read_text(
            encoding="utf-8"
        )

        self.assertIn("--no-bin --no-registry", script)
        self.assertIn("Test-Path $VenvPython", script)
        self.assertGreaterEqual(script.count("if ($LASTEXITCODE -ne 0)"), 3)

    def test_research_agent_terminal_markers_are_windows_safe(self):
        script = (
            PROJECT / "examples" / "14_research_agent" / "example.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn("→", script)
        self.assertNotIn("›", script)

    @skipIf(os.name == "nt", "POSIX shell script test")
    def test_posix_uninstall_removes_setup_but_keeps_source_and_outputs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            scripts = project / "scripts"
            scripts.mkdir()
            shutil.copy(
                PROJECT / "scripts" / "uninstall.sh",
                scripts / "uninstall.sh",
            )

            for name in (".bin", ".python", ".cache", ".venv"):
                (project / name).mkdir()
            (project / ".env").write_text("OPENAI_API_KEY=test\n")
            (project / "uv.lock").write_text("generated\n")
            (project / "lab_llm.egg-info").mkdir()
            (project / "lab_llm" / "__pycache__").mkdir(parents=True)
            (project / "lab_llm" / "source.py").write_text("# keep\n")
            (project / "runs").mkdir()
            (project / "runs" / "result.json").write_text("{}\n")

            subprocess.run(
                ["bash", str(scripts / "uninstall.sh")],
                input="yes\n",
                check=True,
                capture_output=True,
                text=True,
            )

            for name in (
                ".bin",
                ".python",
                ".cache",
                ".venv",
                ".env",
                "uv.lock",
                "lab_llm.egg-info",
                "lab_llm/__pycache__",
            ):
                self.assertFalse((project / name).exists(), name)
            self.assertTrue((project / "lab_llm" / "source.py").is_file())
            self.assertTrue((project / "runs" / "result.json").is_file())

    def test_windows_uninstall_targets_match_setup_artifacts(self):
        script = (PROJECT / "scripts" / "uninstall.ps1").read_text(
            encoding="utf-8"
        )

        self.assertIn(
            '@(".bin", ".python", ".cache", ".venv", ".env", "uv.lock")',
            script,
        )
        self.assertIn('Filter "*.egg-info"', script)
        self.assertIn('Filter "__pycache__"', script)
        self.assertIn("checkpoints outside this folder", script)

    @skipIf(os.name == "nt", "POSIX shell script test")
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
