"""Local perspective-tolerant card matching and on-demand public image cache."""
import hashlib
import io
import os
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

import cv2
import numpy as np
from PIL import Image

IMAGE_BASE = 'https://star-savior-arcana-db.pages.dev/images/cards/'
MAX_IMAGE_BYTES = 4_000_000


def image_url(card):
    """Mirror the public website's Korean-name filename normalization."""
    name = card.get('name', {}).get('ko-KR', '')
    filename = re.sub(r'[\\/:*?"<>|\s]', '', name)
    if not filename:
        raise ValueError('Card has no image name')
    return IMAGE_BASE + quote(filename, safe='') + '.webp'


def verified_image(body):
    if not body or len(body) > MAX_IMAGE_BYTES:
        raise ValueError('Invalid card image size')
    with Image.open(io.BytesIO(body)) as image:
        if image.width * image.height > 8_000_000 or min(image.size) < 64:
            raise ValueError('Invalid card image dimensions')
        image.load()
        return image.convert('RGB')


def cached_image(card, directory):
    """Only publish complete, decodable downloads; preserve other cached images."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    url = image_url(card)
    digest = hashlib.sha256(url.encode('utf-8')).hexdigest()[:16]
    target = directory / f'{int(card["id"])}-{digest}.webp'
    if target.exists():
        try:
            return verified_image(target.read_bytes())
        except (OSError, ValueError):
            pass
    request = Request(url, headers={'User-Agent': 'Mozilla/5.0 (StarSaviorGuideDemo/1.0)'})
    with urlopen(request, timeout=10) as response:
        if response.url != url:
            raise ValueError('Unexpected card image redirect')
        body = response.read(MAX_IMAGE_BYTES + 1)
    image = verified_image(body)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=directory, suffix='.part', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(body)
        os.replace(temporary, target)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()
    return image


def _features(image, reference=False):
    gray = cv2.cvtColor(np.asarray(image.convert('RGB')), cv2.COLOR_RGB2GRAY)
    height, width = gray.shape
    scale = 438 / height if reference else min(3, 900 / max(height, width))
    gray = cv2.resize(gray, (max(1, round(width * scale)), max(1, round(height * scale))))
    points, descriptors = cv2.SIFT_create(nfeatures=1800, contrastThreshold=.015).detectAndCompute(gray, None)
    return gray.shape, points, descriptors


def rank_images(crop, references):
    """Require distributed feature matches consistent with a single homography."""
    shape, points, descriptors = _features(crop)
    if descriptors is None:
        return []
    ranked = []
    for card_id, image in references.items():
        ref_shape, ref_points, ref_descriptors = _features(image, reference=True)
        if ref_descriptors is None or len(descriptors) < 2:
            continue
        pairs = cv2.BFMatcher().knnMatch(ref_descriptors, descriptors, k=2)
        good = [pair[0] for pair in pairs if len(pair) == 2 and pair[0].distance < .75 * pair[1].distance]
        if len(good) < 8:
            continue
        source = np.float32([ref_points[m.queryIdx].pt for m in good])
        target = np.float32([points[m.trainIdx].pt for m in good])
        matrix, mask = cv2.findHomography(source, target, cv2.RANSAC, 4)
        if matrix is None or mask is None:
            continue
        mask = mask.ravel().astype(bool)
        inliers = int(mask.sum())
        if inliers < 12 or inliers / len(good) < .5:
            continue
        rh, rw = ref_shape
        hull = cv2.convexHull(source[mask])
        coverage = cv2.contourArea(hull) / (rh * rw)
        if coverage < .06:
            continue
        corners = np.float32([[0, 0], [rw, 0], [rw, rh], [0, rh]]).reshape(-1, 1, 2)
        projected = cv2.perspectiveTransform(corners, matrix).reshape(-1, 2)
        sh, sw = shape
        if not np.isfinite(projected).all() or not cv2.isContourConvex(projected.astype(np.float32)):
            continue
        area = abs(cv2.contourArea(projected.astype(np.float32)))
        if area < sw * sh * .08 or area > sw * sh * 1.5:
            continue
        if (projected[:, 0].min() < -.15 * sw or projected[:, 0].max() > 1.15 * sw
                or projected[:, 1].min() < -.15 * sh or projected[:, 1].max() > 1.15 * sh):
            continue
        ranked.append({'card_id': card_id, 'inliers': inliers, 'coverage': round(coverage, 3)})
    return sorted(ranked, key=lambda row: row['inliers'], reverse=True)


def resolve_card(crop, cards, directory):
    """Resolve only a clear winner with every competing reference available."""
    cards = {int(card['id']): card for card in cards}
    references, failures = {}, []

    def load(card):
        try:
            return card['id'], cached_image(card, directory), None
        except Exception as exc:
            return card['id'], None, str(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        for card_id, image, error in pool.map(load, cards.values()):
            if error:
                failures.append({'card_id': card_id, 'error': error})
            else:
                references[card_id] = image
    ranked = rank_images(crop, references)
    result = {'status': 'unavailable' if failures else 'uncertain', 'matches': ranked, 'failures': failures}
    if failures or not ranked:
        return result
    top = ranked[0]
    runner_up = ranked[1]['inliers'] if len(ranked) > 1 else 0
    if top['inliers'] >= max(16, runner_up + 8, runner_up * 1.8):
        result.update(status='matched', card_id=top['card_id'])
    return result
