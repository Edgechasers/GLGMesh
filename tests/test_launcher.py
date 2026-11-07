"""Portable launcher checks; no model runtimes needed."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class LauncherTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('zsh'), 'Launcher requires zsh')
    def test_launcher_explicit_python_from_another_directory(self):
        if sys.version_info[:2] != (3,12): self.skipTest('Runtime requires Python 3.12')
        with tempfile.TemporaryDirectory(prefix='glgmesh launch ') as folder:
            result = subprocess.run([str(ROOT/'glgmesh.sh'),'--help'],cwd=folder,
                                    env={**os.environ,'GLGMESH_PYTHON':sys.executable},
                                    text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('low-poly',result.stdout)

    @unittest.skipUnless(shutil.which('zsh'), 'Launcher requires zsh')
    def test_launcher_missing_override_reports_requirement(self):
        result = subprocess.run([str(ROOT/'glgmesh.sh'),'--help'],
                                env={**os.environ,'GLGMESH_PYTHON':'/nonexistent/glgmesh-python'},
                                text=True,capture_output=True)
        self.assertEqual(result.returncode,127)
        self.assertIn('requires Python 3.12',result.stderr)

if __name__ == '__main__': unittest.main()
