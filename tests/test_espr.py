"""Source conversion, complete streaming payloads, and independent atomic caches."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from star_savior.espr import EsprStore, convert, parse_page
from star_savior.website import WebsiteStore


def fixture():
    return json.loads((Path(__file__).parents[1] / 'shared/fixtures/espr.json').read_text())


class EsprTests(unittest.TestCase):
    def test_difficulty_changes_only_gate_and_potential_points(self):
        hard = convert(fixture(), 'en-US', 'Hard')[0]
        self.assertIn('Strength >=500', hard.options[0].effect)
        self.assertIn('Focus +20', hard.options[0].effect)
        self.assertIn('Potential Point +50', hard.options[0].effect)
        self.assertIn('Stamina -5', hard.options[0].effect)
        self.assertIn('Vitality +20 / +30', hard.options[1].effect)
        self.assertIn('Protection +10 (A temporary bonus)', hard.options[1].effect)
        self.assertIn('Possible outcome 2', hard.options[1].effect)

    def test_complete_payload_is_assembled_across_script_chunks(self):
        stream = '1:["component",' + json.dumps(fixture()) + ']\n'
        midpoint = len(stream) // 2
        page = ''.join('<script>self.__next_f.push(' + json.dumps([1, chunk]) + ')</script>'
                       for chunk in (stream[:midpoint], stream[midpoint:]))
        self.assertEqual(parse_page(page), fixture())
        with self.assertRaises(ValueError):
            parse_page(page[:len(page) // 2])

    def test_failed_sync_and_other_locale_preserve_existing_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = WebsiteStore(root / 'website.sqlite3')
            legacy_before = (root / 'website.sqlite3').read_bytes()
            store = EsprStore(root / 'espr.sqlite3', legacy.cards)
            store.replace({'language': 'en-US', 'data': fixture()})
            store.language = 'en-US'
            before = store.updated()
            malformed = copy.deepcopy(fixture())
            malformed['events'][0]['choices'][0]['success'][0]['chips'][0]['label'] = ''
            with self.assertRaises(ValueError):
                store.replace({'language': 'en-US', 'data': malformed})
            self.assertEqual(store.updated(), before)
            self.assertEqual(len(store.load()), 1)
            self.assertEqual(store.load('ja-JP'), [])
            self.assertEqual((root / 'website.sqlite3').read_bytes(), legacy_before)
            store.db.close(); legacy.db.close()
