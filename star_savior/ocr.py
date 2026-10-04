"""Local OCR adapter with no UI or platform dependencies."""
import threading
import time
import gc

_engines = {}
_lock = threading.Lock()


def release_models():
    """Release cached sessions without interrupting an active inference."""
    if not _lock.acquire(blocking=False):
        return False
    try:
        _engines.clear()
        gc.collect()
        return True
    finally:
        _lock.release()


def recognize_regions(image, regions, language='zh-CN'):
    """Read the title and choices from one captured frame, independently."""
    from .layout import crop_regions
    started = time.perf_counter()
    crops = crop_regions(image, regions)
    title, _ = recognize(crops['title'], language)
    options, _ = recognize(crops['options'], language)
    return {'title': title, 'options': options}, time.perf_counter() - started


def recognize(image, language='zh-CN'):
    """Return ordered text lines and processing seconds; cache the CPU model."""
    items, elapsed = recognize_boxes(image, language)
    return [item['text'] for item in items], elapsed


def recognize_boxes(image, language='zh-CN'):
    """Retain box positions and scores for reviewed guide-table reconstruction."""
    import numpy as np
    from rapidocr import RapidOCR
    from rapidocr.utils.typings import LangRec, OCRVersion, ModelType
    started = time.perf_counter()
    with _lock:
        if language not in _engines:
            # Retain only one language's sessions; downloaded models remain cached.
            _engines.clear()
            gc.collect()
            codes = {'zh-CN': LangRec.CH, 'zh-TW': LangRec.CHINESE_CHT, 'en-US': LangRec.EN,
                     'ja-JP': LangRec.JAPAN, 'ko-KR': LangRec.KOREAN}
            params = {'EngineConfig.onnxruntime.use_cuda': False,
                      'EngineConfig.onnxruntime.use_dml': False,
                      'EngineConfig.onnxruntime.use_cann': False,
                      'EngineConfig.onnxruntime.use_coreml': False}
            if language != 'zh-CN':
                params.update({'Rec.lang_type': codes[language],
                               'Rec.ocr_version': OCRVersion.PPOCRV4, 'Rec.model_type': ModelType.MOBILE})
            _engines[language] = RapidOCR(params=params)
        output = _engines[language](np.asarray(image.convert('RGB')))
    items = []
    if output.txts is not None and output.boxes is not None:
        ordered = sorted(zip(output.boxes, output.txts),
                         key=lambda item: (float(min(p[1] for p in item[0])), float(min(p[0] for p in item[0]))))
        scores = dict((str(box.tolist()), float(score)) for box, score in zip(output.boxes, output.scores))
        items = [{'text': str(text), 'box': box.tolist(), 'score': scores[str(box.tolist())]}
                 for box, text in ordered]
    return items, time.perf_counter() - started
