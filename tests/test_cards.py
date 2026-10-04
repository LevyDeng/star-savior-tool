"""Perspective matching, ambiguity, and transactional image cache checks."""
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
from PIL import Image

from star_savior.cards import cached_image, image_url, rank_images, resolve_card, verified_image


def reference(seed):
    rng = np.random.default_rng(seed)
    image = np.full((418, 224, 3), 230, dtype=np.uint8)
    for _ in range(120):
        center = tuple(int(v) for v in rng.integers((8, 8), (216, 410)))
        color = tuple(int(v) for v in rng.integers(0, 220, 3))
        cv2.circle(image, center, int(rng.integers(2, 12)), color, -1)
    return Image.fromarray(image)


def screenshot(image):
    source = np.float32([[0, 0], [224, 0], [224, 418], [0, 418]])
    destination = np.float32([[42, 75], [172, 40], [258, 423], [104, 457]])
    transform = cv2.getPerspectiveTransform(source, destination)
    return Image.fromarray(cv2.warpPerspective(np.asarray(image), transform, (310, 500), borderValue=(90, 90, 90)))


def card(card_id):
    return {'id': card_id, 'name': {'ko-KR': 'Test Card: ' + str(card_id)}}


class CardTests(unittest.TestCase):
    def test_filename_normalization(self):
        self.assertTrue(image_url({'name': {'ko-KR': 'A B:C?/D!'}}).endswith('/ABCD%21.webp'))
        with self.assertRaises(ValueError):
            image_url({'name': {}})

    def test_perspective_matching_and_duplicate_image_ambiguity(self):
        original = reference(1)
        crop = screenshot(original)
        ranked = rank_images(crop, {1: original, 2: reference(2)})
        self.assertEqual(ranked[0]['card_id'], 1)
        self.assertGreaterEqual(ranked[0]['inliers'], 16)
        with patch('star_savior.cards.cached_image', side_effect=lambda c, _: original):
            result = resolve_card(crop, [card(1), card(2)], Path('unused'))
        self.assertEqual(result['status'], 'uncertain')
        self.assertNotIn('card_id', result)

    def test_blank_and_unrelated_crops_have_no_winner(self):
        self.assertEqual(rank_images(Image.new('RGB', (310, 500), 'white'), {1: reference(1)}), [])
        with patch('star_savior.cards.cached_image', return_value=reference(1)):
            result = resolve_card(screenshot(reference(7)), [card(1)], Path('unused'))
        self.assertEqual(result['status'], 'uncertain')

    def test_missing_competitor_prevents_automatic_selection(self):
        original = reference(1)
        with patch('star_savior.cards.cached_image', side_effect=[original, OSError('Offline')]):
            result = resolve_card(screenshot(original), [card(1), card(2)], Path('unused'))
        self.assertEqual(result['status'], 'unavailable')
        self.assertEqual(result['matches'][0]['card_id'], 1)
        self.assertNotIn('card_id', result)

    def test_download_cache_reuse_and_corruption_recovery(self):
        body = io.BytesIO()
        reference(1).save(body, format='WEBP')
        payload = body.getvalue()

        def response(*args, **kwargs):
            stream = io.BytesIO(payload)
            stream.url = image_url(card(1))
            return stream

        root = Path(__file__).resolve().parents[1] / '.runtime'
        root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as directory:
            with patch('star_savior.cards.urlopen', side_effect=response) as fetch:
                self.assertEqual(cached_image(card(1), directory).size, (224, 418))
                cached_image(card(1), directory)
                self.assertEqual(fetch.call_count, 1)
                target = next(Path(directory).glob('*.webp'))
                target.write_bytes(b'broken')
                cached_image(card(1), directory)
                self.assertEqual(fetch.call_count, 2)
            self.assertEqual(list(Path(directory).glob('*.part')), [])

    def test_invalid_download_is_never_published(self):
        root = Path(__file__).resolve().parents[1] / '.runtime'
        with tempfile.TemporaryDirectory(dir=root) as directory:
            stream = io.BytesIO(b'not an image')
            stream.url = image_url(card(1))
            with patch('star_savior.cards.urlopen', return_value=stream), self.assertRaises(OSError):
                cached_image(card(1), directory)
            self.assertEqual(list(Path(directory).iterdir()), [])
        with self.assertRaises(ValueError):
            verified_image(b'')
