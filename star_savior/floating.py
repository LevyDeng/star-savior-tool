"""Small draggable scan button and independent non-modal results panel."""
from PySide6.QtCore import QPoint, Qt, Signal, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QListWidget, QMenu, QTextBrowser, QVBoxLayout, QWidget
from .i18n import tr
from .presentation import ResultPanel, THEME
from . import windows


class NonActivatingWindow:
    """Prevent native click activation for both overlay windows."""

    def nativeEvent(self, event_type, message):
        result = windows.mouse_activation_result(message)
        if result is not None:
            return True, result
        return super().nativeEvent(event_type, message)

    def showEvent(self, event):
        windows.make_nonactivating(int(self.winId()))
        super().showEvent(event)


class FloatingButton(NonActivatingWindow, QWidget):
    scan = Signal()
    controls = Signal()
    quit_requested = Signal()
    release_models_requested = Signal()
    moved = Signal(QPoint)

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)
        self.setFixedSize(72, 72)
        self.setToolTip('单击识别；拖动可移动；右键打开设置或退出。')
        self.busy = False
        self.language = 'zh-CN'
        self.origin = None
        self.start_position = None
        self.dragged = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_busy(self, busy):
        self.busy = busy
        self.update()

    def set_language(self, language):
        self.language = language
        self.setToolTip(tr('capture', language))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor('#d9ecff'), 3))
        painter.setBrush(QColor('#88a8c1') if self.busy else QColor('#357db9'))
        painter.drawEllipse(4, 4, 64, 64)
        painter.setPen(QColor('white'))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, '...' if self.busy else tr('scan', self.language))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.origin = event.globalPosition().toPoint()
            self.start_position = self.pos()
            self.dragged = False

    def mouseMoveEvent(self, event):
        if self.origin is not None and event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self.origin
            if delta.manhattanLength() >= QApplication.startDragDistance():
                self.dragged = True
            if self.dragged:
                self.move(self.start_position + delta)

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or self.origin is None:
            return
        self.origin = None
        if self.dragged:
            self.clamp_to_screen()
            self.moved.emit(self.pos())
        elif not self.busy:
            self.scan.emit()

    def clamp_to_screen(self):
        screen = QGuiApplication.screenAt(self.frameGeometry().center()) or QGuiApplication.primaryScreen()
        area = screen.availableGeometry()
        self.move(max(area.left(), min(self.x(), area.right() - self.width() + 1)),
                  max(area.top(), min(self.y(), area.bottom() - self.height() + 1)))

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        controls = menu.addAction(tr('settings', self.language))
        release_models = menu.addAction(tr('release_models', self.language))
        quit_action = menu.addAction(tr('quit', self.language))
        release_models.triggered.connect(lambda checked=False: self.release_models_requested.emit())
        action = menu.exec(event.globalPos())
        if action == controls:
            self.controls.emit()
        elif action == quit_action:
            self.quit_requested.emit()


class FloatingResults(NonActivatingWindow, QDialog):
    candidate_chosen = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint |
                         Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setWindowTitle('StarSavior · 事件效果')
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)
        self.resize(520, 320)
        self.setStyleSheet(THEME)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        self.panel = ResultPanel(self)
        layout.addWidget(self.panel)
        self.status = self.panel.status
        self.candidates = self.panel.candidates
        self.candidates.itemClicked.connect(lambda item: self.candidate_chosen.emit(self.candidates.row(item)))
        self.effects = self.panel.effects
        self.details = self.panel.details
        self.panel.height_changed.connect(self.fit_height)
        self.anchor = None
        self.set_language('zh-CN')

    def set_language(self, language):
        self.setWindowTitle('StarSavior · ' + tr('effects', language))
        self.panel.set_language(language)

    def clear_results(self):
        self.panel.clear_results()

    def fit_height(self):
        screen = QGuiApplication.screenAt(self.frameGeometry().center()) or QGuiApplication.primaryScreen()
        area = screen.availableGeometry()
        width = min(max(360, self.width()), area.width() - 32)
        height = min(self.panel.natural_height() + 32, max(100, area.height() - 64))
        self.resize(width, height)
        if self.isVisible():
            self.position_near(area)

    def position_near(self, area):
        x, y = self.x(), self.y()
        if self.anchor:
            x, y = self.anchor.x() - self.width() - 8, self.anchor.y()
            if x < area.left():
                x = self.anchor.x() + self.anchor.width() + 8
        frame = self.frameGeometry()
        self.move(max(area.left(), min(x, area.right() - frame.width() + 1)),
                  max(area.top(), min(y, area.bottom() - frame.height() + 1)))

    def show_near(self, button):
        screen = QGuiApplication.screenAt(button.frameGeometry().center()) or QGuiApplication.primaryScreen()
        area = screen.availableGeometry()
        self.anchor = button
        self.fit_height()
        self.position_near(area)
        self.show()
        QTimer.singleShot(0, self.fit_height)
