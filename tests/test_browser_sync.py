"""Native browser IPC rejects partial, cancelled, oversized, and wrong-locale results."""
import json
import tempfile
import unittest
from pathlib import Path

from star_savior.browser_sync import read_result
from tests.test_espr import fixture


class BrowserResultTests(unittest.TestCase):
    def test_complete_snapshot_and_explicit_cancellation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'snapshot.json'
            snapshot = {'language': 'en-US', 'data': fixture()}
            path.write_text(json.dumps(snapshot), encoding='utf-8')
            self.assertEqual(read_result(directory, 'en-US', 0), snapshot)
            self.assertIsNone(read_result(directory, 'en-US', 2))
            with self.assertRaisesRegex(RuntimeError, 'exited'):
                read_result(directory, 'en-US', -1)
            with self.assertRaisesRegex(ValueError, 'locale'):
                read_result(directory, 'zh-CN', 0)

    def test_missing_and_partial_payloads_never_succeed(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                read_result(directory, 'en-US', 0)
            path = Path(directory) / 'snapshot.json'
            for data in [{'events': [], 'tiers': []}, {'events': [1]}, {'tiers': []}]:
                path.write_text(json.dumps({'language': 'en-US', 'data': data}), encoding='utf-8')
                with self.assertRaises(ValueError):
                    read_result(directory, 'en-US', 0)
            path.write_bytes(b'x' * 8_000_001)
            with self.assertRaisesRegex(ValueError, 'size limit'):
                read_result(directory, 'en-US', 0)

    def test_runtime_and_timeout_errors_are_actionable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'error.json'
            path.write_text(json.dumps({'kind': 'runtime_missing'}), encoding='utf-8')
            with self.assertRaisesRegex(RuntimeError, 'https://developer.microsoft.com'):
                read_result(directory, 'en-US', 1)
            path.write_text(json.dumps({'kind': 'timeout'}), encoding='utf-8')
            with self.assertRaisesRegex(RuntimeError, 'networking'):
                read_result(directory, 'en-US', 1)
