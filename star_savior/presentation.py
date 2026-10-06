"""Blue-white theme and content-sized result presentation widgets."""
import math

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (QLabel, QLayout, QListWidget, QScrollArea,
                              QTextBrowser, QToolButton, QVBoxLayout, QWidget)

from .i18n import tr

THEME = """
QWidget { color: #223b56; font-family: "Microsoft YaHei UI", "Segoe UI"; font-size: 14px; }
QMainWindow, QDialog { background: #f1f7fc; }
QLabel { background: transparent; }
QLabel#summary { color: #59758f; padding: 4px 0; }
QLabel#status { color: #376184; background: #e9f3fd; border: 1px solid #d4e6f6; border-radius: 9px; padding: 10px; }
QPushButton { background: #ffffff; border: 1px solid #cbdfee; border-radius: 8px; padding: 9px 15px; }
QPushButton:hover { background: #eaf4ff; border-color: #84b8e4; }
QPushButton:pressed { background: #dbeeff; }
QPushButton[primary="true"] { background: #357db9; color: white; border-color: #357db9; }
QPushButton[primary="true"]:hover { background: #286da6; }
QPushButton#startButton { background: #357db9; color: white; border: 3px solid #d6eaff; border-radius: 42px; padding: 0; font-size: 19px; font-weight: 700; }
QPushButton#startButton:hover { background: #286da6; border-color: #acd3f5; }
QPushButton#startButton:pressed { background: #205987; }
QPushButton:disabled { color: #8ba0b2; background: #e8eff5; border-color: #dce6ee; }
QComboBox { background: white; border: 1px solid #cbdfee; border-radius: 8px; padding: 8px 12px; min-height: 20px; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView { background: white; selection-background-color: #deedfb; selection-color: #223b56; }
QTextBrowser, QListWidget { background: #ffffff; border: 1px solid #d5e5f1; border-radius: 10px; padding: 8px; selection-background-color: #d6eafe; selection-color: #173b60; }
QToolButton { background: #eaf3fb; border: 1px solid #d5e5f1; border-radius: 7px; padding: 8px; text-align: left; }
QToolButton:hover { background: #dfedfa; }
QScrollArea, QWidget#resultBody { border: none; background: transparent; }
QScrollBar:vertical { background: #edf3f8; width: 9px; margin: 2px; border-radius: 4px; }
QScrollBar::handle:vertical { background: #accae0; min-height: 24px; border-radius: 4px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QMenu { background: white; border: 1px solid #cbdfee; padding: 5px; }
QMenu::item { padding: 8px 18px; }
QMenu::item:selected { background: #e3f0fc; }
QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #abc7df; border-radius: 4px; background: white; }
QCheckBox::indicator:checked { background: #357db9; border-color: #357db9; }
"""


class ContentBrowser(QTextBrowser):
    height_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.document().contentsChanged.connect(self.fit_content)
        self.document().documentLayout().documentSizeChanged.connect(self.fit_content)
        self._fitting = False
        self.setFixedHeight(48)

    def fit_content(self, *_):
        if self._fitting:
            return
        self._fitting = True
        try:
            self.document().setTextWidth(max(60, self.viewport().width()))
            height = max(48, math.ceil(self.document().size().height()) + 26)
            if self.height() != height:
                self.setFixedHeight(height)
                self.height_changed.emit()
        finally:
            self._fitting = False

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_content()


class FoldSection(QWidget):
    changed = Signal()

    def __init__(self, content, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.toggle = QToolButton()
        self.toggle.setCheckable(True)
        self.toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle.setArrowType(Qt.ArrowType.RightArrow)
        layout.addWidget(self.toggle)
        self.content = content
        content.hide()
        layout.addWidget(content)
        self.toggle.toggled.connect(self.expanded)

    def expanded(self, checked):
        self.content.setVisible(checked)
        self.toggle.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)
        self.changed.emit()


class ResultPanel(QScrollArea):
    height_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.body = QWidget()
        self.body.setObjectName('resultBody')
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(10)
        self.body_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinAndMaxSize)
        self.status = QLabel()
        self.status.setObjectName('status')
        self.status.setWordWrap(True)
        self.body_layout.addWidget(self.status)
        self.effect_label = QLabel()
        self.body_layout.addWidget(self.effect_label)
        self.effects = ContentBrowser()
        self.body_layout.addWidget(self.effects)
        self.candidates = QListWidget()
        self.candidates.setFixedHeight(130)
        self.candidate_section = FoldSection(self.candidates)
        self.candidate_section.hide()
        self.body_layout.addWidget(self.candidate_section)
        self.details = ContentBrowser()
        self.detail_section = FoldSection(self.details)
        self.body_layout.addWidget(self.detail_section)
        self.setWidget(self.body)
        self.effects.height_changed.connect(self.schedule_fit)
        self.details.height_changed.connect(self.schedule_fit)
        self.candidate_section.changed.connect(self.schedule_fit)
        self.detail_section.changed.connect(self.schedule_fit)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.height_changed.emit)
        self.language = 'zh-CN'
        self.candidate_count = 0
        self.set_language('zh-CN')

    def schedule_fit(self):
        self.body_layout.invalidate()
        self.timer.start(0)

    def natural_height(self):
        self.body_layout.activate()
        return self.body_layout.sizeHint().height() + 4

    def set_language(self, language):
        self.language = language
        self.effect_label.setText(tr('effects', language))
        self._update_candidate_label()
        self.detail_section.toggle.setText(tr('text', language))
        self.schedule_fit()

    def set_candidate_count(self, count):
        self.candidate_count = max(0, int(count))
        self._update_candidate_label()
        self.candidate_section.setVisible(self.candidate_count > 1)
        self.schedule_fit()

    def _update_candidate_label(self):
        if self.candidate_count > 1:
            text = tr('candidates_count', self.language, count=self.candidate_count)
        else:
            text = tr('candidates', self.language)
        self.candidate_section.toggle.setText(text)

    def clear_results(self):
        self.status.clear()
        self.candidates.clear()
        self.set_candidate_count(0)
        self.effects.clear()
        self.effects.setToolTip('')
        self.details.clear()
        self.candidate_section.toggle.setChecked(False)
        self.detail_section.toggle.setChecked(False)
        self.schedule_fit()
