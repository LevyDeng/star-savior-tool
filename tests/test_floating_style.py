"""Rendering and animation lifecycle checks for the floating scan control."""
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtWidgets import QApplication
from star_savior.floating import FloatingButton


class FloatingStyleTests(unittest.TestCase):
    def test_glass_button_renders_and_animation_tracks_visibility(self):
        app = QApplication.instance() or QApplication([])
        button = FloatingButton()
        try:
            button.show()
            app.processEvents()
            idle = button.grab().toImage()
            self.assertGreater(idle.pixelColor(36, 33).alpha(), 200)
            button.set_busy(True)
            self.assertTrue(button.animation.isActive())
            button.advance_animation()
            app.processEvents()
            self.assertNotEqual(idle, button.grab().toImage())
            button.hide()
            self.assertFalse(button.animation.isActive())
            button.show()
            self.assertTrue(button.animation.isActive())
            button.set_busy(False)
            self.assertFalse(button.animation.isActive())
        finally:
            button.close()
