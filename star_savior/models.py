"""Resolve and atomically cache only the OCR assets a language needs."""
import hashlib
import os
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class ModelDownloadError(RuntimeError):
    pass


def cache_directory():
    base = os.environ.get('STAR_SAVIOR_DATA_DIR')
    if base:
        return Path(base) / 'models'
    local = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / '.cache')))
    return local / 'StarSaviorTool' / 'StarSaviorGuideDemo' / 'models'


def language_params(language):
    from rapidocr.utils.typings import LangRec, OCRVersion, ModelType
    codes = {'zh-CN': LangRec.CH, 'zh-TW': LangRec.CHINESE_CHT, 'en-US': LangRec.EN,
             'ja-JP': LangRec.JAPAN, 'ko-KR': LangRec.KOREAN}
    if language not in codes:
        raise ValueError('Unsupported OCR language')
    return {} if language == 'zh-CN' else {'Rec.lang_type': codes[language],
        'Rec.ocr_version': OCRVersion.PPOCRV4, 'Rec.model_type': ModelType.MOBILE}


def download_model(url, destination, expected_hash, progress=None):
    if destination.is_file() and hashlib.sha256(destination.read_bytes()).hexdigest() == expected_hash:
        return
    temporary = destination.with_suffix(destination.suffix + '.part')
    try:
        request = Request(url, headers={'User-Agent': 'StarSaviorHelper/1.0'})
        with urlopen(request, timeout=30) as response:
            total = int(response.headers.get('Content-Length', 0))
            size = 0
            digest = hashlib.sha256()
            if progress:
                progress(destination.name, size, total)
            with temporary.open('wb') as output:
                while chunk := response.read(256 * 1024):
                    size += len(chunk)
                    if size > 256 * 1024 * 1024:
                        raise ValueError('Model exceeds download size limit')
                    output.write(chunk)
                    digest.update(chunk)
                    if progress:
                        progress(destination.name, size, total)
            if digest.hexdigest() != expected_hash:
                raise ValueError('Model checksum verification failed')
        temporary.replace(destination)
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        raise ModelDownloadError(f'{destination.name}: {exc}') from exc


def prepare_models(language, directory=None, progress=None):
    from rapidocr.main import DEFAULT_CFG_PATH
    from rapidocr.inference_engine.base import FileInfo, InferSession
    from rapidocr.utils.parse_parameters import ParseParams
    params = language_params(language)
    cfg = ParseParams.update_batch(ParseParams.load(DEFAULT_CFG_PATH), params)
    directory = Path(directory) if directory else cache_directory()
    directory.mkdir(parents=True, exist_ok=True)
    params['Global.model_root_dir'] = str(directory)
    for section in ('Det', 'Cls', 'Rec'):
        task = cfg[section]
        info = InferSession.get_model_url(FileInfo(task.engine_type, task.ocr_version,
            task.task_type, task.lang_type, task.model_type))
        url = info['model_dir']
        destination = directory / Path(urlparse(url).path).name
        download_model(url, destination, info['SHA256'], progress)
        params[section + '.model_path'] = str(destination)
    if progress:
        progress(None, 0, 0)
    return params
