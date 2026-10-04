"""A process-independent mutex blocks duplicates and releases on exit."""
import os
import subprocess
import sys
import unittest
import uuid

from star_savior.instance import SingleInstance


@unittest.skipUnless(os.name == 'nt', 'Requires Windows named mutexes')
class InstanceTests(unittest.TestCase):
    def test_other_process_is_blocked_until_handle_closes(self):
        name = 'Local\\StarSaviorTool.Test.' + uuid.uuid4().hex
        owner = SingleInstance(name)
        script = ('from star_savior.instance import SingleInstance; '
                  f'guard = SingleInstance({name!r}); print(guard.acquire()); guard.close()')
        try:
            self.assertTrue(owner.acquire())
            self.assertEqual(subprocess.check_output([sys.executable, '-c', script], text=True).strip(), 'False')
            owner.close()
            self.assertEqual(subprocess.check_output([sys.executable, '-c', script], text=True).strip(), 'True')
        finally:
            owner.close()

    def test_crashed_owner_does_not_leave_a_stale_lock(self):
        name = 'Local\\StarSaviorTool.Test.' + uuid.uuid4().hex
        script = ('import os; from star_savior.instance import SingleInstance; '
                  f'guard = SingleInstance({name!r}); assert guard.acquire(); os._exit(0)')
        subprocess.check_call([sys.executable, '-c', script])
        guard = SingleInstance(name)
        try:
            self.assertTrue(guard.acquire())
        finally:
            guard.close()
