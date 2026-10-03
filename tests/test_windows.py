"""Foreground preservation for game capture activation."""
import os
import unittest
from unittest.mock import patch

from star_savior import windows


@unittest.skipUnless(os.name == 'nt', 'Windows activation requires Win32')
class ActivationTests(unittest.TestCase):
    def test_foreground_game_is_not_reactivated(self):
        with patch.object(windows.user32, 'IsWindow', return_value=True), \
             patch.object(windows.user32, 'IsIconic', return_value=False), \
             patch.object(windows.user32, 'GetForegroundWindow', return_value=4242), \
             patch.object(windows.user32, 'SetForegroundWindow') as activate:
            windows.activate(4242)
            activate.assert_not_called()

    def test_failed_foreground_switch_is_reported(self):
        with patch.object(windows.user32, 'IsWindow', return_value=True), \
             patch.object(windows.user32, 'IsIconic', return_value=False), \
             patch.object(windows.user32, 'GetForegroundWindow', return_value=99), \
             patch.object(windows.user32, 'SetForegroundWindow', return_value=False):
            with self.assertRaises(RuntimeError):
                windows.activate(4242)
