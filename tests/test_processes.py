"""Console suppression for dependencies in the frozen Windows build."""
import os
import subprocess
import sys
import unittest
from unittest.mock import patch

from star_savior.processes import install_windowed_process_policy


@unittest.skipUnless(os.name == 'nt', 'Requires Windows process flags')
class ProcessPolicyTests(unittest.TestCase):
    def test_source_execution_is_unchanged(self):
        original = subprocess.Popen
        with patch.object(sys, 'frozen', False, create=True):
            install_windowed_process_policy()
        self.assertIs(subprocess.Popen, original)

    def test_flags_are_preserved_and_positional_arguments_supported(self):
        original = subprocess.Popen
        with patch.object(sys, 'frozen', True, create=True), patch.object(subprocess, 'Popen', original):
            install_windowed_process_policy()
            installed = subprocess.Popen
            install_windowed_process_policy()
            self.assertIs(subprocess.Popen, installed)
            for flags in (0, subprocess.CREATE_NEW_PROCESS_GROUP, subprocess.CREATE_NEW_CONSOLE,
                          subprocess.DETACHED_PROCESS):
                # Supply creationflags positionally as third-party callers may do.
                arguments = [[sys.executable], -1, None, None, None, None, None, True,
                             False, None, None, None, None, flags]
                with patch.object(original, '__init__', return_value=None) as initialize:
                    subprocess.Popen(*arguments)
                expected = flags if flags & (subprocess.CREATE_NEW_CONSOLE | subprocess.DETACHED_PROCESS) \
                    else flags | subprocess.CREATE_NO_WINDOW
                self.assertEqual(initialize.call_args.args[13], expected)

    def test_real_system_probe_keeps_output_and_exit_status(self):
        original = subprocess.Popen
        with patch.object(sys, 'frozen', True, create=True), patch.object(subprocess, 'Popen', original):
            install_windowed_process_policy()
            output = subprocess.check_output('ver', shell=True, text=True)
            self.assertIn('Windows', output)
            with self.assertRaises(subprocess.CalledProcessError):
                subprocess.check_output('exit /b 7', shell=True)
