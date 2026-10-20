"""Priority matching never replaces a primary candidate with a backup reward."""
import unittest
from dataclasses import replace
from star_savior.core import match_sources
from star_savior.espr import convert
from tests.test_espr import fixture


class SourceMatchingTests(unittest.TestCase):
    def test_primary_candidate_wins_even_if_backup_title_is_more_precise(self):
        event = convert(fixture(), 'en-US', 'Normal')[0]
        primary = replace(event, title=event.title + '!')
        fallback, (_, candidates, _) = match_sources([primary], [event], [event.title], [])
        self.assertFalse(fallback)
        self.assertIs(candidates[0].event, primary)

    def test_empty_primary_and_unknown_in_both(self):
        event = convert(fixture(), 'en-US', 'Normal')[0]
        fallback, (_, candidates, _) = match_sources([], [event], [event.title], [])
        self.assertTrue(fallback)
        self.assertIs(candidates[0].event, event)
        fallback, (_, candidates, _) = match_sources([event], [event], ['zzzzzzzz'], [])
        self.assertFalse(fallback)
        self.assertFalse(candidates)
