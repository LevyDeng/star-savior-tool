"""Small draggable scan button and independent non-modal results panel."""
from pathlib import Path
from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal, QTimer
from PySide6.QtGui import QColor, QConicalGradient, QGuiApplication, QPainter, QPen, QPixmap
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


class FloatingButtonPreview(QWidget):
    """Actual-size artwork preview with the same opacity as the overlay."""

    def __init__(self, pixmap, parent=None):
        super().__init__(parent)
        self.pixmap = pixmap
        self.icon_size = 72
        self.transparency = 0
        self.setFixedSize(176, 176)

    def set_appearance(self, size, transparency):
        self.icon_size = size
        self.transparency = transparency
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        for y in range(0, self.height(), 16):
            for x in range(0, self.width(), 16):
                color = '#edf3f9' if (x // 16 + y // 16) % 2 == 0 else '#dce6f0'
                painter.fillRect(x, y, 16, 16, QColor(color))
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setOpacity(1 - self.transparency / 100)
        margin = (self.width() - self.icon_size) // 2
        painter.drawPixmap(QRectF(margin, margin, self.icon_size, self.icon_size),
                           self.pixmap, QRectF(self.pixmap.rect()))


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
        self.setWindowOpacity(1.0)
        self.icon_pixmap = QPixmap(str(Path(__file__).with_name('assets') / 'floating-icon.png'))
        self.setToolTip(tr('capture', 'zh-CN'))
        self.busy = False
        self.language = 'zh-CN'
        self.origin = None
        self.start_position = None
        self.dragged = False
        self.angle = 0
        self.animation = QTimer(self)
        self.animation.setInterval(33)
        self.animation.timeout.connect(self.advance_animation)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_busy(self, busy):
        self.busy = busy
        if busy and self.isVisible():
            self.animation.start()
        else:
            self.animation.stop()
        self.update()

    def advance_animation(self):
        self.angle = (self.angle + 7) % 360
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        if self.busy:
            self.animation.start()

    def hideEvent(self, event):
        self.animation.stop()
        super().hideEvent(event)

    def set_language(self, language):
        self.language = language
        self.setToolTip(tr('capture', language))
        self.update()

    def set_appearance(self, size, transparency):
        size = max(40, min(160, int(size)))
        transparency = max(0, min(90, int(transparency)))
        self.setFixedSize(size, size)
        self.setWindowOpacity(1 - transparency / 100)
        self.clamp_to_screen()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawPixmap(self.rect(), self.icon_pixmap)
        if self.busy:
            painter.scale(self.width() / 72, self.height() / 72)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            sheen = QConicalGradient(QPointF(36, 36), -self.angle)
            for stop, color in ((0, QColor(114, 211, 155, 0)), (.3, QColor('#73d5a0')),
                                (.48, QColor('#d9ffe9')), (.55, QColor('#a3edc0')),
                                (.75, QColor(114, 211, 155, 0)), (1, QColor(114, 211, 155, 0))):
                sheen.setColorAt(stop, color)
            painter.setPen(QPen(sheen, 3))
            painter.drawEllipse(QRectF(5, 5, 62, 62))

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
        self.setWindowTitle('starsaviorhelper')
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
        self.setWindowTitle('starsaviorhelper · ' + tr('effects', language))
        self.panel.set_language(language)

    def clear_results(self):
        self.panel.clear_results()

    def set_candidate_count(self, count):
        self.panel.set_candidate_count(count)

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
