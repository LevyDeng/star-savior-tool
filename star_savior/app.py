"""Windows game OCR with a multilingual website-backed offline guide."""
from __future__ import annotations
import json
import os
import sys
import ctypes
from html import escape
from ctypes import wintypes
from pathlib import Path
from PySide6.QtCore import QAbstractNativeEventFilter, QSettings, QStandardPaths, QThread, QTimer, QUrl, Qt, Signal, QRect, QPoint
from PySide6.QtGui import QDesktopServices, QFont, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QListWidget, QMainWindow, QPushButton, QRubberBand, QTextBrowser, QVBoxLayout, QWidget
from .core import match_regions
from .layout import DEFAULT_REGIONS, valid_regions
from .floating import FloatingButton, FloatingResults
from .website import DIFFICULTIES, SOURCE_URL, WebsiteStore, download
from .i18n import LANGUAGES, tr
from .presentation import ResultPanel, THEME
from . import windows


class SyncWorker(QThread):
    result = Signal(object)
    failed = Signal(str)
    def run(self):
        try:
            self.result.emit(download())
        except Exception as exc:
            self.failed.emit(str(exc))


class RegionDialog(QDialog):
    def __init__(self, image, parent=None, label='title_area'):
        super().__init__(parent)
        language = getattr(parent, 'language', 'zh-CN')
        self.setWindowTitle(tr('region_prompt', language, label=tr(label, language)))
        data = image.tobytes('raw', 'RGB')
        qt_image = QImage(data, image.width, image.height, image.width * 3, QImage.Format.Format_RGB888).copy()
        self.pixmap = QPixmap.fromImage(qt_image).scaled(1000, 650, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.setFixedSize(self.pixmap.size())
        self.band = QRubberBand(QRubberBand.Shape.Rectangle, self)
        self.origin = QPoint()
        self.region = None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.pixmap)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.origin = event.position().toPoint()
            self.band.setGeometry(QRect(self.origin, self.origin))
            self.band.show()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.band.setGeometry(QRect(self.origin, event.position().toPoint()).normalized().intersected(self.rect()))

    def mouseReleaseEvent(self, event):
        rect = self.band.geometry()
        if rect.width() >= 20 and rect.height() >= 20:
            self.region = (rect.x() / self.width(), rect.y() / self.height(),
                           (rect.x() + rect.width()) / self.width(), (rect.y() + rect.height()) / self.height())

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.region:
            self.accept()
        else:
            super().keyPressEvent(event)


class OCRWorker(QThread):
    result = Signal(object, float)
    failed = Signal(str)

    def __init__(self, image, regions, language='zh-CN'):
        super().__init__()
        self.image = image
        self.regions = regions
        self.language = language

    def run(self):
        try:
            from .ocr import recognize_regions
            result, elapsed = recognize_regions(self.image, self.regions, self.language)
            self.result.emit(result, elapsed)
        except Exception as exc:
            self.failed.emit(tr('ocr_failed', self.language, error=exc))


class Hotkey(QAbstractNativeEventFilter):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.registered = os.name == 'nt' and bool(windows.user32.RegisterHotKey(None, 1, 0x4000 | 0x0001 | 0x0002, ord('S')))

    def nativeEventFilter(self, event_type, message):
        if os.name == 'nt':
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == 0x0312 and msg.wParam == 1:
                QTimer.singleShot(0, self.callback)
                return True, 0
        return False, 0

    def close(self):
        if self.registered:
            windows.user32.UnregisterHotKey(None, 1)


class MainWindow(QMainWindow):
    def __init__(self, data_dir):
        super().__init__()
        self.setWindowTitle('StarSavior 跑马助手')
        self.resize(820, 680)
        self.setStyleSheet(THEME)
        self.store = WebsiteStore(data_dir / 'website.sqlite3')
        self.settings = QSettings(str(data_dir / 'settings.ini'), QSettings.Format.IniFormat)
        self.language = self.settings.value('language', 'zh-CN')
        if self.language not in LANGUAGES:
            self.language = 'zh-CN'
        self.store.language = self.language
        self.difficulty = self.settings.value('difficulty', 'Normal')
        if self.difficulty not in DIFFICULTIES:
            self.difficulty = 'Normal'
        self.store.difficulty = self.difficulty
        self.last_recognition = None
        self.sync_worker = None
        self.translatable = []
        self.regions = dict(DEFAULT_REGIONS)
        self.worker = None
        self.candidates = []
        self.busy = False
        self.floating_mode = False
        self.floating_button = FloatingButton(self)
        self.floating_button.scan.connect(lambda: self.prepare_capture(False))
        self.floating_button.controls.connect(self.open_controls)
        self.floating_button.quit_requested.connect(self.exit_floating)
        self.floating_button.moved.connect(lambda position: self.settings.setValue('floating_position', position))
        self.floating_results = FloatingResults(self)
        self.floating_results.candidate_chosen.connect(self.confirm_candidate)
        position = self.settings.value('floating_position')
        if isinstance(position, QPoint):
            self.floating_button.move(position)
        else:
            area = QApplication.primaryScreen().availableGeometry()
            self.floating_button.move(area.right() - 90, area.top() + 180)
        self.floating_button.clamp_to_screen()
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        brand = QLabel('STAR SAVIOR')
        brand.setStyleSheet('font-size: 22px; font-weight: 700; color: #357db9; letter-spacing: 2px;')
        layout.addWidget(brand)
        self.summary = QLabel()
        self.summary.setObjectName('summary')
        layout.addWidget(self.summary)
        row = QHBoxLayout()
        row.addWidget(self.label('language'))
        self.language_list = QComboBox()
        for code, name in LANGUAGES.items():
            self.language_list.addItem(name, code)
        self.language_list.setCurrentIndex(self.language_list.findData(self.language))
        self.language_list.currentIndexChanged.connect(self.language_changed)
        row.addWidget(self.language_list)
        self.sync_button = self.button('sync', self.sync)
        self.sync_button.setProperty('primary', True)
        row.addWidget(self.sync_button)
        row.addWidget(self.button('website', lambda: QDesktopServices.openUrl(QUrl(SOURCE_URL))))
        layout.addLayout(row)
        row = QHBoxLayout()
        row.addWidget(self.label('difficulty'))
        self.difficulty_list = QComboBox()
        for difficulty in DIFFICULTIES:
            self.difficulty_list.addItem(self.t(difficulty), difficulty)
        self.difficulty_list.setCurrentIndex(self.difficulty_list.findData(self.difficulty))
        self.difficulty_list.currentIndexChanged.connect(self.difficulty_changed)
        row.addWidget(self.difficulty_list)
        row.addStretch()
        layout.addLayout(row)
        row = QHBoxLayout()
        self.window_list = QComboBox()
        self.window_list.setMinimumWidth(260)
        self.window_list.currentIndexChanged.connect(self.window_changed)
        row.addWidget(self.window_list, 1)
        refresh = self.button('refresh', self.refresh_windows)
        
        row.addWidget(refresh)
        self.select_region = self.button('regions', lambda: self.prepare_capture(True))
        
        row.addWidget(self.select_region)
        layout.addLayout(row)
        row = QHBoxLayout()
        floating = self.button('floating', self.enable_floating)
        floating.setProperty('primary', True)
        
        row.addWidget(floating)
        reset = self.button('reset', self.reset_regions)
        
        row.addWidget(reset)
        layout.addLayout(row)
        row = QHBoxLayout()
        self.capture_button = self.button('capture', lambda: self.prepare_capture(False))
        self.capture_button.setProperty('primary', True)
        
        row.addWidget(self.capture_button)
        self.image_button = self.button('image', self.open_image)
        
        row.addWidget(self.image_button)
        topmost = QCheckBox()
        self.translatable.append((topmost, 'topmost'))
        topmost.toggled.connect(self.set_topmost)
        row.addWidget(topmost)
        layout.addLayout(row)
        self.result_panel = ResultPanel(self)
        self.status = self.result_panel.status
        self.status.setText(self.t('ready'))
        self.ocr_text = self.result_panel.details
        self.candidate_list = self.result_panel.candidates
        self.candidate_list.itemClicked.connect(self.choose_candidate)
        self.effects = self.result_panel.effects
        layout.addWidget(self.result_panel, 1)
        self.setCentralWidget(body)
        self.result_panel.height_changed.connect(self.fit_results)
        self.retranslate()
        self.refresh_windows()
        self.update_summary()
        self.hotkey = Hotkey(lambda: self.prepare_capture(False))
        QApplication.instance().installNativeEventFilter(self.hotkey)
        if not self.hotkey.registered:
            self.status.setText(self.t('hotkey_unavailable'))

    def t(self, key, **values):
        return tr(key, self.language, **values)

    def fit_results(self):
        area = self.screen().availableGeometry()
        layout = self.centralWidget().layout()
        controls = layout.sizeHint().height() - self.result_panel.sizeHint().height()
        height = min(controls + self.result_panel.natural_height(), max(240, area.height() - 64))
        self.resize(min(self.width(), area.width() - 32), height)
        if self.isVisible():
            frame = self.frameGeometry()
            self.move(max(area.left(), min(self.x(), area.right() - frame.width() + 1)),
                      max(area.top(), min(self.y(), area.bottom() - frame.height() + 1)))

    def label(self, key):
        widget = QLabel(self.t(key))
        self.translatable.append((widget, key))
        return widget

    def button(self, key, callback):
        widget = QPushButton(self.t(key))
        self.translatable.append((widget, key))
        widget.clicked.connect(callback)
        return widget

    def retranslate(self):
        self.setWindowTitle('StarSavior · ' + self.t('effects'))
        for widget, key in self.translatable:
            widget.setText(self.t(key))
        for index in range(self.difficulty_list.count()):
            self.difficulty_list.setItemText(index, self.t(self.difficulty_list.itemData(index)))
        self.floating_button.set_language(self.language)
        self.floating_results.set_language(self.language)
        self.result_panel.set_language(self.language)

    def language_changed(self, *_):
        if self.busy or (self.sync_worker and self.sync_worker.isRunning()):
            self.language_list.blockSignals(True)
            self.language_list.setCurrentIndex(self.language_list.findData(self.language))
            self.language_list.blockSignals(False)
            return
        self.language = self.language_list.currentData()
        self.store.language = self.language
        self.settings.setValue('language', self.language)
        self.clear_results()
        self.retranslate()
        self.update_summary()
        self.refresh_windows()
        self.status.setText(self.t('ready'))

    def difficulty_changed(self, *_):
        if self.busy or (self.sync_worker and self.sync_worker.isRunning()):
            self.difficulty_list.blockSignals(True)
            self.difficulty_list.setCurrentIndex(self.difficulty_list.findData(self.difficulty))
            self.difficulty_list.blockSignals(False)
            return
        previous = self.last_recognition
        self.difficulty = self.difficulty_list.currentData()
        self.store.difficulty = self.difficulty
        self.settings.setValue('difficulty', self.difficulty)
        self.clear_results()
        self.update_summary()
        if previous:
            self.ocr_finished(*previous)
        else:
            self.status.setText(self.t('ready'))
        self.fit_results()

    def update_summary(self):
        updated = self.store.updated()
        self.summary.setText(self.t('summary', count=len(self.store.load()), updated=updated if updated != 'Never' else self.t('never')))

    def sync(self):
        if self.busy or (self.sync_worker and self.sync_worker.isRunning()):
            return
        self.sync_button.setEnabled(False)
        self.status.setText(self.t('syncing'))
        self.sync_worker = SyncWorker(self)
        self.sync_worker.result.connect(self.synced)
        self.sync_worker.failed.connect(self.sync_failed)
        self.sync_worker.finished.connect(lambda: self.sync_button.setEnabled(True))
        self.sync_worker.start()

    def synced(self, raw):
        try:
            self.store.replace(raw)
            self.clear_results()
            self.update_summary()
            self.status.setText(self.t('synced'))
        except Exception as exc:
            self.sync_failed(str(exc))

    def sync_failed(self, error):
        self.status.setText(self.t('sync_failed', error=error))

    def refresh_windows(self):
        previous = self.window_list.currentData()
        self.window_list.blockSignals(True)
        self.window_list.clear()
        self.window_list.addItem(self.t('select'), None)
        for hwnd, title in windows.list_windows():
            if hwnd not in (int(self.winId()),
                            int(self.floating_button.winId()), int(self.floating_results.winId())):
                self.window_list.addItem(title, hwnd)
        index = self.window_list.findData(previous)
        if index <= 0:
            saved_title = self.settings.value('game_window_title', '')
            index = self.window_list.findText(saved_title) if saved_title else -1
            if index <= 0:
                games = [i for i in range(1, self.window_list.count())
                         if 'starsavior' in self.window_list.itemText(i).replace(' ', '').casefold()]
                index = games[0] if len(games) == 1 else 0
        self.window_list.setCurrentIndex(max(0, index))
        self.window_list.blockSignals(False)
        if self.window_list.currentData() != previous:
            self.window_changed()

    def window_changed(self, *_):
        title = self.window_list.currentText()
        raw = self.settings.value('event_regions/' + title, '')
        try:
            regions = json.loads(raw) if raw else None
            self.regions = regions if valid_regions(regions) else dict(DEFAULT_REGIONS)
        except (ValueError, TypeError):
            self.regions = dict(DEFAULT_REGIONS)
        if self.window_list.currentData():
            self.settings.setValue('game_window_title', title)

    def reset_regions(self):
        self.regions = dict(DEFAULT_REGIONS)
        self.settings.remove('event_regions/' + self.window_list.currentText())
        self.status.setText(self.t('reset_done'))

    def enable_floating(self):
        if not self.window_list.currentData():
            self.status.setText(self.t('choose_first'))
            return
        self.floating_mode = True
        self.hide()
        self.floating_button.show()

    def open_controls(self):
        self.floating_mode = False
        self.floating_button.hide()
        self.floating_results.hide()
        self.show()
        self.raise_()

    def exit_floating(self):
        if self.close():
            QApplication.instance().quit()

    def restore_capture_ui(self):
        if self.floating_mode:
            self.floating_button.show()
        else:
            self.show()

    def show_scan_status(self, text):
        self.status.setText(text)
        self.floating_results.status.setText(text)
        self.result_panel.schedule_fit()
        self.floating_results.panel.schedule_fit()
        if self.floating_mode:
            self.floating_results.show_near(self.floating_button)

    def set_topmost(self, enabled):
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, enabled)
        self.show()

    def clear_results(self):
        self.last_recognition = None
        self.result_panel.clear_results()
        self.candidates = []
        self.floating_results.clear_results()

    def prepare_capture(self, selecting):
        if self.busy or QApplication.activeModalWidget():
            return
        self.clear_results()
        hwnd = self.window_list.currentData()
        if not hwnd:
            self.status.setText(self.t('choose_first'))
            return
        self.busy = True
        self.floating_button.set_busy(True)
        self.hide()
        self.floating_button.hide()
        self.floating_results.hide()
        try:
            windows.activate(hwnd)
        except Exception as exc:
            self.busy = False
            self.floating_button.set_busy(False)
            self.restore_capture_ui()
            self.show_scan_status(str(exc))
            return
        QTimer.singleShot(300, lambda: self.finish_capture(hwnd, selecting))

    def finish_capture(self, hwnd, selecting):
        try:
            image = windows.capture(hwnd)
            self.restore_capture_ui()
            if selecting:
                regions = {}
                for name, label in (('title', 'title_area'), ('options', 'options_area')):
                    dialog = RegionDialog(image, self, label)
                    if dialog.exec() != QDialog.DialogCode.Accepted:
                        break
                    regions[name] = dialog.region
                if valid_regions(regions):
                    self.regions = regions
                    self.settings.setValue('event_regions/' + self.window_list.currentText(), json.dumps(regions))
                    self.status.setText(self.t('regions_saved'))
                self.busy = False
                self.floating_button.set_busy(False)
            else:
                self.start_ocr(image)
        except Exception as exc:
            self.busy = False
            self.floating_button.set_busy(False)
            self.restore_capture_ui()
            self.show_scan_status(self.t('capture_failed', error=exc))

    def open_image(self):
        if self.busy:
            return
        self.clear_results()
        path, _ = QFileDialog.getOpenFileName(self, self.t('image'), '', 'Images (*.png *.jpg *.jpeg *.bmp)')
        if path:
            try:
                from PIL import Image
                with Image.open(path) as source:
                    image = source.convert('RGB')
                self.start_ocr(image)
            except Exception as exc:
                self.status.setText(self.t('image_failed', error=exc))

    def start_ocr(self, image):
        self.busy = True
        self.floating_button.set_busy(True)
        self.status.setText(self.t('ocr_busy'))
        self.worker = OCRWorker(image, dict(self.regions), self.language)
        self.worker.result.connect(self.ocr_finished)
        self.worker.failed.connect(self.ocr_failed)
        self.worker.finished.connect(self.worker_finished)
        self.worker.start()

    def worker_finished(self):
        self.busy = False
        self.floating_button.set_busy(False)

    def ocr_failed(self, error):
        self.show_scan_status(error)

    def ocr_finished(self, result, elapsed):
        self.last_recognition = (result, elapsed)
        title, options = result['title'], result['options']
        recognized = self.t('title') + ':\n' + ('\n'.join(title) or self.t('unreadable')) + '\n\n' + self.t('options') + ':\n' + ('\n'.join(options) or self.t('unreadable'))
        self.ocr_text.setPlainText(recognized)
        self.floating_results.details.setPlainText(recognized)
        events = self.store.load()
        state, self.candidates, reason = match_regions(events, title, options)
        if not events:
            self.show_scan_status(self.t('no_data'))
        elif state == 'unknown':
            self.show_scan_status(self.t('result', seconds=elapsed, reason=self.t(state)))
        elif state == 'matched':
            self.show_scan_status(self.t('result', seconds=elapsed, reason=self.t(state)))
            self.show_effects(self.candidates[0].event)
        else:
            self.show_scan_status(self.t('result', seconds=elapsed, reason=self.t(state)))
            for candidate in self.candidates:
                label = ' | '.join(value for value in (candidate.event.title, candidate.event.visible_phase,
                    candidate.event.visible_source, f'{candidate.score:.2f}') if value)
                self.candidate_list.addItem(label)
                self.floating_results.candidates.addItem(label)
                details = f'{candidate.event.phase}\n{candidate.event.source}'
                self.candidate_list.item(self.candidate_list.count() - 1).setToolTip(details)
                self.floating_results.candidates.item(self.floating_results.candidates.count() - 1).setToolTip(details)

    def choose_candidate(self, item):
        index = self.candidate_list.row(item)
        self.confirm_candidate(index)

    def confirm_candidate(self, index):
        if not 0 <= index < len(self.candidates):
            return
        self.show_effects(self.candidates[index].event)
        self.show_scan_status(self.t('matched'))

    def show_effects(self, event):
        context = ' | '.join(value for value in (event.visible_phase,
            f'{self.t("source")}: {event.visible_source}') if value)
        text = [f'<h2 style="color:#286da6; margin-bottom:6px;">{escape(event.title)}</h2>',
                f'<p style="color:#66829b; font-size:12px;">{escape(context)}</p>']
        for option in event.options:
            effect = escape(option.effect).replace('\n', '<br>')
            text.append(f'<h3 style="color:#286da6; margin-top:18px; margin-bottom:8px;">'
                        f'{option.order}. {escape(option.text)}</h3><p style="line-height:145%;">{effect}</p>')
        content = ''.join(text)
        self.effects.setHtml(content)
        self.floating_results.effects.setHtml(content)
        details = f'{self.t("data_details")}\n{event.phase}\n{event.source}'
        self.effects.setToolTip(details)
        self.floating_results.effects.setToolTip(details)

    def closeEvent(self, event):
        if self.busy or (self.worker and self.worker.isRunning()) or (self.sync_worker and self.sync_worker.isRunning()):
            event.ignore()
            self.status.setText(self.t('wait_close'))
            return
        self.hotkey.close()
        QApplication.instance().removeNativeEventFilter(self.hotkey)
        self.settings.sync()
        self.floating_button.hide()
        self.floating_results.hide()
        self.store.db.close()
        super().closeEvent(event)


def main():
    windows.enable_dpi_awareness()
    app = QApplication(sys.argv)
    app.setFont(QFont('Segoe UI', 10))
    app.setApplicationName('StarSaviorGuideDemo')
    app.setOrganizationName('StarSaviorTool')
    data_dir = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))
    # Tests can use an isolated directory without touching the user's browser profile.
    if os.environ.get('STAR_SAVIOR_DATA_DIR'):
        data_dir = Path(os.environ['STAR_SAVIOR_DATA_DIR'])
    data_dir.mkdir(parents=True, exist_ok=True)
    window = MainWindow(data_dir)
    window.show()
    if not window.store.load():
        QTimer.singleShot(0, window.sync)
    app.exec()
