"""Isolated UI smoke checks; no external account or real game is used."""
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from star_savior.app import MainWindow


class UITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setApplicationName('StarSaviorDemoTests')
        font = Path(r'C:\Windows\Fonts\segoeui.ttf')
        if font.exists():
            QFontDatabase.addApplicationFont(str(font))
            cls.app.setFont(QFont('Segoe UI', 10))

    def test_single_weak_candidate_is_shown_but_ambiguous_candidates_wait(self):
        from unittest.mock import patch
        from star_savior.core import Event, Option, match_regions
        event = Event('Training direction', '1', 'Test', [
            Option(1, 'Attack training', 'Strength +10'),
            Option(2, 'Survival training', 'Vitality +10')])
        recognition = {'title': ['Training direction'], 'options': ['Attack training']}
        state, candidates, _ = match_regions([event], **{
            'title_lines': recognition['title'], 'option_lines': recognition['options']})
        self.assertEqual(state, 'confirm')
        self.assertEqual(len(candidates), 1)
        with tempfile.TemporaryDirectory() as directory:
            window = MainWindow(Path(directory))
            window.language_list.setCurrentIndex(window.language_list.findData('en-US'))
            with patch.object(window.store, 'load', return_value=[event]):
                window.ocr_finished(recognition, 0.1)
            self.assertIn('Strength +10', window.effects.toPlainText())
            self.assertIn('only candidate', window.status.text())
            self.assertEqual(window.candidate_list.count(), 0)
            window.clear_results()
            second = Event(event.title, '2', 'Other', event.options)
            with patch.object(window.store, 'load', return_value=[event, second]):
                window.ocr_finished(recognition, 0.1)
            self.assertEqual(window.candidate_list.count(), 2)
            self.assertEqual(window.effects.toPlainText(), '')
            window.clear_results()
            with patch.object(window.store, 'load', return_value=[event]):
                window.ocr_finished({'title': ['Unrelated beach trip'], 'options': []}, 0.1)
            self.assertEqual(window.effects.toPlainText(), '')
            self.assertEqual(window.candidate_list.count(), 0)
            window.close()

    def test_difficulty_refreshes_results_and_persists(self):
        from unittest.mock import patch
        from star_savior.core import Event, Option
        with tempfile.TemporaryDirectory() as directory:
            window = MainWindow(Path(directory))
            window.language_list.setCurrentIndex(window.language_list.findData('en-US'))
            self.assertEqual(window.difficulty_list.currentData(), 'Normal')

            def events():
                points = 50 if window.store.difficulty == 'Hard' else 30
                return [Event('An afternoon', '1', 'Test',
                              [Option(1, 'Rest', f'Focus +20; Potential Point +{points}')])]

            with patch.object(window.store, 'load', side_effect=events), patch.object(window, 'start_ocr') as ocr:
                window.ocr_finished({'title': ['An afternoon'], 'options': ['Rest']}, 0.1)
                self.assertIn('Potential Point +30', window.effects.toPlainText())
                window.difficulty_list.setCurrentIndex(window.difficulty_list.findData('Hard'))
                self.assertIn('Potential Point +50', window.effects.toPlainText())
                self.assertIn('Focus +20', window.floating_results.effects.toPlainText())
                ocr.assert_not_called()
                window.busy = True
                window.difficulty_list.setCurrentIndex(window.difficulty_list.findData('Easy'))
                self.assertEqual(window.difficulty_list.currentData(), 'Hard')
                window.busy = False
            window.close()
            reopened = MainWindow(Path(directory))
            self.assertEqual(reopened.difficulty_list.currentData(), 'Hard')
            self.assertEqual(reopened.store.difficulty, 'Hard')
            reopened.close()

    def test_main_window_offline_start_and_shutdown(self):
        with tempfile.TemporaryDirectory() as directory:
            window = MainWindow(Path(directory))
            window.show()
            self.app.processEvents()
            preview = os.environ.get('STAR_SAVIOR_PREVIEW')
            if preview:
                window.grab().save(preview)
            self.assertEqual(window.store.load(), [])
            self.assertIn('数据更新时间', window.summary.text())
            self.assertFalse(hasattr(window, 'browser'))
            window.language_list.setCurrentIndex(window.language_list.findData('en-US'))
            self.assertIn('Data updated', window.summary.text())
            self.assertEqual(window.start_button.text(), 'Start')
            self.assertFalse(hasattr(window, 'capture_button'))
            self.assertFalse(hasattr(window, 'image_button'))
            self.assertFalse(hasattr(window, 'result_panel'))
            self.check_floating_capture(window)
            window.close()
            QTimer.singleShot(100, self.app.quit)
            self.app.exec()
            from shiboken6 import delete
            delete(window)
            # Chromium closes its SQLite handles asynchronously after profile destruction.
            QTimer.singleShot(300, self.app.quit)
            self.app.exec()

    def check_floating_capture(self, window):
        from PIL import Image
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from unittest.mock import patch
        window.window_list.addItem('Test game', 4242)
        window.window_list.setCurrentIndex(window.window_list.count() - 1)
        window.enable_floating()
        self.assertFalse(window.isVisible())
        self.assertTrue(window.floating_button.isVisible())
        window.floating_results.show()
        visibility_at_capture = []

        def fake_capture(hwnd):
            visibility_at_capture.append((window.floating_button.isVisible(), window.floating_results.isVisible()))
            return Image.new('RGB', (2000, 1250))

        with patch('star_savior.app.windows.activate'), patch('star_savior.app.windows.capture', side_effect=fake_capture) as capture, \
                patch.object(window, 'start_ocr', side_effect=lambda image: window.worker_finished()) as ocr:
            QTest.mouseClick(window.floating_button, Qt.MouseButton.LeftButton)
            QTest.qWait(400)
            capture.assert_called_once_with(4242)
            self.assertTrue(ocr.called, window.status.text())
            ocr.assert_called_once()
        self.assertEqual(visibility_at_capture, [(False, False)])
        self.assertTrue(window.floating_button.isVisible())
        self.assertFalse(window.isVisible())
        window.open_controls()
        self.assertTrue(window.isVisible())
        self.assertFalse(window.floating_button.isVisible())





    def test_floating_drag_does_not_trigger_scan(self):
        from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
        from PySide6.QtGui import QMouseEvent
        from PySide6.QtTest import QSignalSpy, QTest
        from star_savior.floating import FloatingButton
        button = FloatingButton()
        button.move(100, 100)
        button.show()
        self.app.processEvents()
        scans, moves = QSignalSpy(button.scan), QSignalSpy(button.moved)
        start = button.mapToGlobal(QPoint(36, 36))
        for kind, local, global_pos, buttons in [
            (QEvent.Type.MouseButtonPress, QPoint(36, 36), start, Qt.MouseButton.LeftButton),
            (QEvent.Type.MouseMove, QPoint(6, 36), start - QPoint(30, 0), Qt.MouseButton.LeftButton),
            (QEvent.Type.MouseButtonRelease, QPoint(36, 36), start - QPoint(30, 0), Qt.MouseButton.NoButton),
        ]:
            event = QMouseEvent(kind, QPointF(local), QPointF(global_pos),
                                Qt.MouseButton.NoButton if kind == QEvent.Type.MouseMove else Qt.MouseButton.LeftButton,
                                buttons, Qt.KeyboardModifier.NoModifier)
            self.app.sendEvent(button, event)
        self.assertEqual(scans.count(), 0)
        self.assertEqual(moves.count(), 1)
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        self.assertEqual(scans.count(), 1)
        button.set_busy(True)
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        self.assertEqual(scans.count(), 1)
        button.close()

    def test_overlay_native_click_does_not_activate_and_still_scans(self):
        if os.name != 'nt':
            self.skipTest('Native overlay activation requires Win32')
        import ctypes
        from ctypes import wintypes
        from unittest.mock import patch
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QSignalSpy, QTest
        from star_savior.floating import FloatingButton, FloatingResults
        message = wintypes.MSG()
        message.message = 0x0021
        for overlay in (FloatingButton(), FloatingResults()):
            with patch('star_savior.floating.windows.make_nonactivating') as prevent:
                overlay.show()
                self.app.processEvents()
                prevent.assert_called_once_with(int(overlay.winId()))
            self.assertTrue(overlay.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus)
            self.assertEqual(overlay.nativeEvent(b'windows_generic_MSG', ctypes.addressof(message)), (True, 3))
            if isinstance(overlay, FloatingButton):
                scans = QSignalSpy(overlay.scan)
                QTest.mouseClick(overlay, Qt.MouseButton.LeftButton)
                self.assertEqual(scans.count(), 1)
            overlay.close()

    def test_results_expand_to_content_and_scroll_only_past_screen_limit(self):
        from star_savior.floating import FloatingResults
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        result = FloatingResults()
        self.assertFalse(result.panel.candidate_section.toggle.isChecked())
        self.assertFalse(result.panel.detail_section.toggle.isChecked())
        result.status.setText('Matched')
        result.effects.setPlainText('An afternoon\n\n1. Rest\nHealth +15\n\n2. Train\nPower +10')
        result.show()
        result.fit_height()
        QTest.qWait(100)
        short_height = result.height()
        self.assertFalse(result.panel.verticalScrollBar().isVisible())
        self.assertEqual(result.effects.verticalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        result.effects.setPlainText('\n'.join('Effect line ' + str(i) for i in range(300)))
        QTest.qWait(100)
        self.assertGreater(result.height(), short_height)
        self.assertLessEqual(result.height(), result.screen().availableGeometry().height() - 64)
        self.assertTrue(result.panel.verticalScrollBar().isVisible())
        self.assertGreater(result.effects.height(), result.height())
        result.effects.setPlainText('One short result')
        QTest.qWait(100)
        self.assertFalse(result.panel.verticalScrollBar().isVisible())
        result.panel.detail_section.toggle.setChecked(True)
        self.assertFalse(result.details.isHidden())
        result.clear_results()
        self.assertTrue(result.details.isHidden())
        result.close()


if __name__ == '__main__':
    unittest.main()
