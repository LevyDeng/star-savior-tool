"""Windowed executable entry point and isolated packaging diagnostics."""
import os
import sys
import traceback
from pathlib import Path


def self_test(directory):
    import json
    from PIL import Image, ImageDraw
    from PySide6.QtWidgets import QApplication
    from star_savior.app import MainWindow
    from star_savior.i18n import LANGUAGES
    from star_savior.ocr import recognize

    directory.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    window = MainWindow(directory)
    window.show()
    app.processEvents()
    image = Image.new('RGB', (700, 140), 'white')
    ImageDraw.Draw(image).text((30, 40), 'Star Savior Training', fill='black', font_size=36)
    results = {language: recognize(image, language)[0] for language in LANGUAGES}
    if not any('Star' in line for line in results['en-US']):
        raise RuntimeError('Packaged English OCR did not recognize the test image')
    window.grab().save(str(directory / 'window.png'))
    window.close()
    (directory / 'report.json').write_text(json.dumps({'ok': True, 'ocr': results}, indent=2), encoding='utf-8')


if __name__ == '__main__':
    diagnostic = len(sys.argv) == 3 and sys.argv[1] == '--self-test'
    data_dir = Path(sys.argv[2]) if diagnostic else Path(
        os.environ.get('STAR_SAVIOR_DATA_DIR') or
        (Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'StarSaviorTool' / 'StarSaviorGuideDemo'))
    data_dir.mkdir(parents=True, exist_ok=True)
    stream = (data_dir / 'application.log').open('a', encoding='utf-8', buffering=1)
    if sys.stdout is None:
        sys.stdout = stream
    if sys.stderr is None:
        sys.stderr = stream
    try:
        if diagnostic:
            self_test(data_dir)
        else:
            from star_savior.app import main
            main()
    except Exception:
        traceback.print_exc(file=stream)
        if not diagnostic:
            from PySide6.QtWidgets import QApplication, QMessageBox
            app = QApplication.instance() or QApplication([])
            QMessageBox.critical(None, 'Star Savior', f'Unable to start. Details: {data_dir / "application.log"}')
        sys.exit(1)
