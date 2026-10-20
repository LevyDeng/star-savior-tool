"""Switching providers changes the query store, not either source's payload."""
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtWidgets import QApplication
from star_savior.app import MainWindow
from tests.test_espr import fixture
from tests.test_website import snapshot


class SourceUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_lookup_falls_back_in_both_directions_and_displays_result(self):
        with tempfile.TemporaryDirectory() as directory:
            window = MainWindow(Path(directory))
            window.stores['arcana'].replace(snapshot())
            window.stores['espr'].replace({'language': 'en-US', 'data': fixture()})
            window.language_list.setCurrentIndex(window.language_list.findData('en-US'))
            for preferred, actual in [('espr', 'arcana'), ('arcana', 'espr')]:
                window.source_list.setCurrentIndex(window.source_list.findData(preferred))
                event = window.stores[actual].load('en-US', 'Normal')[0]
                window.clear_results()
                window.ocr_finished({'title': [event.title], 'options': []}, 0.1)
                self.assertEqual(window.result_source, actual)
                self.assertEqual(window.candidates[0].event.title, event.title)
                self.assertIn(event.title, window.effects.toPlainText())
            window.close()

    def test_sources_remain_independent_and_selection_survives_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            window = MainWindow(Path(directory))
            self.assertEqual(window.source, 'espr')
            window.stores['arcana'].replace(snapshot())
            window.stores['espr'].replace({'language': 'en-US', 'data': fixture()})
            window.language_list.setCurrentIndex(window.language_list.findData('en-US'))
            self.assertEqual(window.store.load()[0].title, 'Beach tournament')
            window.source_list.setCurrentIndex(window.source_list.findData('arcana'))
            self.assertEqual(window.store.load()[0].title, 'An afternoon')
            window.close()
            restored = MainWindow(Path(directory))
            self.assertEqual(restored.source, 'arcana')
            restored.source_list.setCurrentIndex(restored.source_list.findData('espr'))
            self.assertEqual(restored.store.load()[0].title, 'Beach tournament')
            self.assertFalse(hasattr(restored, 'source_meta'))
            restored.close()
