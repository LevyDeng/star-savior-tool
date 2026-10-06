"""Compact draggable title bar with an embedded language selector."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget


class TitleBar(QWidget):
    def __init__(self, window, language_selector):
        super().__init__(window)
        self.window = window
        self.setObjectName('titleBar')
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(38)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 0, 0)
        layout.setSpacing(0)
        self.title = QLabel(window.windowTitle())
        self.title.setObjectName('windowTitle')
        layout.addWidget(self.title)
        layout.addStretch(1)
        language_selector.setObjectName('titleLanguage')
        language_selector.setFixedWidth(170)
        layout.addWidget(language_selector)
        layout.addSpacing(8)
        for text, callback, name in (
                ('−', window.showMinimized, 'minimizeWindow'),
                ('□', self.toggle_maximized, 'maximizeWindow'),
                ('×', window.close, 'closeWindow')):
            button = QPushButton(text)
            button.setObjectName(name)
            button.setFixedSize(44, 38)
            button.clicked.connect(callback)
            layout.addWidget(button)
        window.windowTitleChanged.connect(self.title.setText)

    def toggle_maximized(self):
        if self.window.isMaximized():
            self.window.showNormal()
        else:
            self.window.showMaximized()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.window.windowHandle()
            if handle:
                handle.startSystemMove()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_maximized()
        super().mouseDoubleClickEvent(event)
