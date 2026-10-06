"""Exercise saved network settings and sync-worker configuration."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QCheckBox, QDialogButtonBox, QLineEdit
from star_savior.app import MainWindow, SyncWorker


class NetworkUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_dialog_saves_and_reload_preserves_options(self):
        with tempfile.TemporaryDirectory() as directory:
            window = MainWindow(Path(directory))
            self.assertFalse(window.settings.value('sync_skip_tls', False, type=bool))

            def save_dialog():
                dialog = QApplication.activeModalWidget()
                dialog.findChild(QLineEdit).setText('http://127.0.0.1:7890')
                dialog.findChild(QCheckBox).setChecked(True)
                buttons = dialog.findChild(QDialogButtonBox)
                buttons.button(QDialogButtonBox.StandardButton.Save).click()

            QTimer.singleShot(0, save_dialog)
            window.configure_network()
            window.close()
            restored = MainWindow(Path(directory))
            self.assertEqual(restored.settings.value('sync_proxy'), 'http://127.0.0.1:7890')
            self.assertTrue(restored.settings.value('sync_skip_tls', False, type=bool))
            with patch.object(SyncWorker, 'start'):
                restored.sync()
                self.assertEqual(restored.sync_worker.proxy_url, 'http://127.0.0.1:7890')
                self.assertFalse(restored.sync_worker.verify_tls)
            restored.close()

    def test_worker_passes_options_to_download(self):
        with patch('star_savior.app.download', return_value={}) as fetch:
            worker = SyncWorker(proxy_url='http://localhost:7890', verify_tls=False)
            worker.run()
            fetch.assert_called_once_with('http://localhost:7890', False)
