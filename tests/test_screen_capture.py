"""Screen-mode capture must hide overlays without activating a game."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from star_savior.app import MainWindow


class ScreenCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_start_without_game_and_capture_selected_screen(self):
        with tempfile.TemporaryDirectory() as directory:
            window = MainWindow(Path(directory))
            window.window_list.setCurrentIndex(0)
            window.enable_floating()
            self.assertTrue(window.floating_button.isVisible())
            frame = QImage(101, 53, QImage.Format.Format_RGB888)
            frame.fill(0xff123456)
            screen = MagicMock()

            def grab(_):
                self.assertFalse(window.isVisible())
                self.assertFalse(window.floating_button.isVisible())
                self.assertFalse(window.floating_results.isVisible())
                return MagicMock(toImage=lambda: frame)

            screen.grabWindow.side_effect = grab
            with patch.object(window.floating_button, 'screen', return_value=screen), \
                    patch('star_savior.app.windows.activate') as activate, \
                    patch('star_savior.app.windows.capture') as capture, \
                    patch.object(window, 'start_ocr', side_effect=lambda image: window.worker_finished()) as ocr:
                window.prepare_capture(False)
                QTest.qWait(450)
                activate.assert_not_called()
                capture.assert_not_called()
                screen.grabWindow.assert_called_once_with(0)
                ocr.assert_called_once()
                image = ocr.call_args.args[0]
                self.assertEqual(image.size, (101, 53))
                self.assertEqual(image.getpixel((100, 52)), (18, 52, 86))
            self.assertTrue(window.floating_button.isVisible())
            self.assertFalse(window.busy)
            window.close()

    def test_empty_capture_restores_controls_and_busy_state(self):
        with tempfile.TemporaryDirectory() as directory:
            window = MainWindow(Path(directory))
            window.enable_floating()
            window.busy = True
            screen = MagicMock()
            screen.grabWindow.return_value.toImage.return_value = QImage()
            window.finish_capture(None, False, screen)
            self.assertFalse(window.busy)
            self.assertTrue(window.floating_button.isVisible())
            self.assertIn('Screen capture returned an empty image', window.status.text())
            window.close()
