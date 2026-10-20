"""Synchronize through the installed system WebView2 Runtime, without Qt WebEngine."""
import json
import os
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QObject, QEventLoop, QProcess, QStandardPaths, QTimer
from PySide6.QtWidgets import QApplication, QDialog

from .espr import extractor_path, source_url
from .i18n import tr


def bridge_path():
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS) / 'webview2-runtime' / 'StarSaviorSync.exe'
    return Path(__file__).parents[1] / 'build' / 'webview2-runtime' / 'StarSaviorSync.exe'


def read_result(directory, language, exit_code):
    """Read only a finished process's bounded result, never a stale snapshot."""
    directory = Path(directory)
    error = directory / 'error.json'
    if error.exists():
        if error.stat().st_size > 100_000:
            raise ValueError('WebView2 error report exceeds its size limit')
        details = json.loads(error.read_text(encoding='utf-8-sig'))
        kind = details.get('kind')
        if kind == 'runtime_missing':
            raise RuntimeError(tr('webview2_missing', language))
        if kind == 'timeout':
            raise RuntimeError(tr('browser_sync_timeout', language))
        raise RuntimeError('WebView2: ' + str(details.get('detail', kind)))
    if exit_code == 2:
        return None
    if exit_code != 0:
        raise RuntimeError(f'WebView2 process exited with code {exit_code}')
    result = directory / 'snapshot.json'
    if not result.exists() or result.stat().st_size > 8_000_000:
        raise ValueError('WebView2 returned no complete snapshot or exceeded its size limit')
    snapshot = json.loads(result.read_text(encoding='utf-8-sig'))
    data = snapshot.get('data', {})
    if (snapshot.get('language') != language or not isinstance(data.get('events'), list)
            or not data['events'] or not isinstance(data.get('tiers'), list)):
        raise ValueError('WebView2 returned an invalid locale snapshot')
    return snapshot


class BrowserSyncDialog(QObject):
    """Modal Qt controller; the native bridge owns the visible browser window."""
    def __init__(self, language, parent=None, profile=None, timeout_seconds=120):
        super().__init__(parent)
        self.language = language
        self.snapshot = None
        self.profile = Path(profile) if profile else (
            Path(parent.settings.fileName()).parent / 'webview2' if parent is not None
            else Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)) / 'webview2')
        self.timeout_seconds = timeout_seconds
        self.process = QProcess(self)
        self.loop = QEventLoop(self)
        self.watchdog = QTimer(self)
        self.watchdog.setSingleShot(True)
        self.watchdog.timeout.connect(self.expired)
        self.process.finished.connect(self.completed)
        self.process.errorOccurred.connect(self.process_error)
        self.error = None
        self.done = False
        self.cancelled = False
        QApplication.instance().aboutToQuit.connect(self.reject)

    def exec(self):
        executable = bridge_path()
        if not executable.is_file():
            raise RuntimeError(tr('webview2_bridge_missing', self.language))
        self.profile.mkdir(parents=True, exist_ok=True)
        parent = self.parent()
        old_busy = getattr(parent, 'busy', False)
        enabled = parent.isEnabled() if parent is not None else False
        with tempfile.TemporaryDirectory(prefix='starsavior-sync-') as directory:
            self.directory = Path(directory)
            config = {
                'title': 'ESPR.gg · ' + tr('browser_sync', self.language),
                'hint': tr('browser_sync_hint', self.language),
                'cancel': tr('network_cancel', self.language),
                'url': source_url(self.language), 'language': self.language,
                'script': extractor_path().read_text(encoding='utf-8'),
                'profile': str(self.profile.resolve()),
                'timeout_seconds': self.timeout_seconds,
                'parent_pid': os.getpid(), 'owner': int(parent.winId()) if parent is not None else 0,
            }
            config_path = self.directory / 'config.json'
            config_path.write_text(json.dumps(config, ensure_ascii=False), encoding='utf-8')
            try:
                if parent is not None:
                    parent.busy = True
                    parent.setEnabled(False)
                self.watchdog.start(int((self.timeout_seconds + 15) * 1000))
                self.process.start(str(executable), [str(config_path)])
                if not self.done:
                    self.loop.exec()
                if self.error:
                    raise self.error
                return QDialog.DialogCode.Accepted if self.snapshot else QDialog.DialogCode.Rejected
            finally:
                self.watchdog.stop()
                if self.process.state() != QProcess.ProcessState.NotRunning:
                    self.process.kill()
                    self.process.waitForFinished(3000)
                if parent is not None:
                    parent.busy = old_busy
                    parent.setEnabled(enabled)

    def completed(self, exit_code, status):
        try:
            if not self.error and not self.cancelled:
                self.snapshot = read_result(self.directory, self.language, exit_code)
        except Exception as error:
            self.error = error
        self.done = True
        self.loop.quit()

    def process_error(self, error):
        if self.cancelled or self.error:
            return
        self.error = RuntimeError('WebView2: ' + self.process.errorString())
        if error == QProcess.ProcessError.FailedToStart:
            self.done = True
            self.loop.quit()

    def expired(self):
        self.error = RuntimeError(tr('browser_sync_timeout', self.language))
        self.reject()

    def reject(self):
        self.cancelled = True
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()
        self.done = True
        self.loop.quit()
