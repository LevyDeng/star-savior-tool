"""On-demand model selection, cache reuse, and failed-download preservation."""
import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from star_savior.models import ModelDownloadError, download_model, prepare_models


def test_directory():
    root = Path(__file__).resolve().parents[1] / '.runtime'
    root.mkdir(exist_ok=True)
    return tempfile.TemporaryDirectory(dir=root)


class ModelTests(unittest.TestCase):
    def test_language_downloads_only_shared_models_and_its_recognizer(self):
        with test_directory() as directory:
            selections = {}
            for language in ('zh-CN', 'zh-TW', 'en-US', 'ja-JP', 'ko-KR'):
                with patch('star_savior.models.download_model') as download:
                    params = prepare_models(language, directory)
                self.assertEqual(download.call_count, 3)
                self.assertEqual(params['Global.model_root_dir'], directory)
                selections[language] = {key: params[key + '.model_path'] for key in ('Det', 'Cls', 'Rec')}
            self.assertEqual(len({value['Det'] for value in selections.values()}), 1)
            self.assertEqual(len({value['Cls'] for value in selections.values()}), 1)
            self.assertEqual(len({value['Rec'] for value in selections.values()}), 5)

    def test_download_is_verified_then_reused_without_network(self):
        payload = b'valid model payload'
        digest = hashlib.sha256(payload).hexdigest()
        with test_directory() as directory:
            destination = Path(directory) / 'recognizer.onnx'
            response = io.BytesIO(payload)
            response.headers = {'Content-Length': str(len(payload))}
            progress = []
            with patch('star_savior.models.urlopen', return_value=response):
                download_model('https://example.com/model', destination, digest,
                               lambda *values: progress.append(values))
            self.assertEqual(destination.read_bytes(), payload)
            self.assertEqual(progress[-1][1:], (len(payload), len(payload)))
            with patch('star_savior.models.urlopen') as request:
                download_model('https://example.com/model', destination, digest)
                request.assert_not_called()

    def test_bad_download_preserves_existing_file_and_cleans_partial(self):
        with test_directory() as directory:
            destination = Path(directory) / 'recognizer.onnx'
            destination.write_bytes(b'old model')
            for failure in (False, True):
                response = io.BytesIO(b'incomplete model')
                response.headers = {}
                with patch('star_savior.models.urlopen', side_effect=OSError('Offline') if failure else None,
                           return_value=response):
                    with self.assertRaises(ModelDownloadError):
                        download_model('https://example.com/model', destination, 'invalid hash')
                self.assertEqual(destination.read_bytes(), b'old model')
                self.assertFalse(destination.with_suffix('.onnx.part').exists())
