import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

import just


class RunTests(unittest.TestCase):
    def test_string_command_preserves_quoted_arguments_and_uses_repo_root(self):
        with patch.object(just.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as subprocess_run:
            just.run('python -c "print(\'two words\')"')

        self.assertEqual(just.repo_root, Path(just.__file__).parent)
        subprocess_run.assert_called_once_with(
            ["python", "-c", "print('two words')"],
            cwd=just.repo_root,
        )

    def test_nonzero_command_exit_raises_system_exit_with_its_code(self):
        with patch.object(just.subprocess, "run", return_value=subprocess.CompletedProcess([], 23)):
            with self.assertRaises(SystemExit) as raised:
                just.run("false")

        self.assertEqual(raised.exception.code, 23)
