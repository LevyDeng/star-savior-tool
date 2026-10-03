import tempfile
import unittest
from pathlib import Path


from star_savior.core import Event, Option, match, match_regions, validate
from star_savior.layout import DEFAULT_REGIONS, crop_regions, valid_regions


def example(title='Quiet afternoon', source='Journey'):
    return Event(title, 'March', source, [Option(1, 'Choose a soft pillow', 'Health +10'),
                                         Option(2, 'Choose spicy food', 'Power +10 or +20; cost 20')])


class CoreTests(unittest.TestCase):



    def test_full_group_matches(self):
        state, candidates = match([example()], ['Quiet afternoon', '1. Choose a soft pillow', '2. Choose spicy food'])
        self.assertEqual(state, 'matched')
        self.assertEqual(candidates[0].event.title, 'Quiet afternoon')

    def test_wrapped_text_and_small_typo(self):
        state, _ = match([example()], ['Quiet afternoon', 'Choose a soft', 'pillow', 'Choose spicy foof'])
        self.assertEqual(state, 'matched')

    def test_same_options_different_event_requires_confirmation(self):
        state, candidates = match([example(), example('Another afternoon', 'Other sheet')],
                                   ['Choose a soft pillow', 'Choose spicy food'])
        self.assertEqual(state, 'confirm')
        self.assertEqual(len(candidates), 2)

    def test_partial_or_reordered_text_never_auto_matches(self):
        for lines in [['Quiet afternoon', 'Choose a soft pillow'],
                      ['Quiet afternoon', 'Choose spicy food', 'Choose a soft pillow']]:
            state, _ = match([example()], lines)
            self.assertNotEqual(state, 'matched')

    def test_unknown_and_empty_input(self):
        self.assertEqual(match([example()], [])[0], 'unknown')
        self.assertEqual(match([example()], ['Unrelated screen settings'])[0], 'unknown')

    def test_invalid_order_and_duplicates(self):
        event = example()
        event.options[1].order = 3
        self.assertTrue(validate([event]))
        self.assertTrue(validate([example(), example()]))

    def test_unique_title_without_choices_is_sufficient(self):
        state, _, reason = match_regions([example()], ['Journey event', 'Quiet afternoon'], [])
        self.assertEqual(state, 'matched')
        self.assertIn('没有读取到选项文字', reason)

    def test_title_and_choice_cross_check(self):
        state, _, reason = match_regions([example()], ['Quiet afternoon'],
                                         ['Choose a soft pillow', 'Choose spicy food'])
        self.assertEqual(state, 'matched')
        self.assertIn('选项也已核对', reason)

    def test_title_contradiction_or_partial_choices_requires_confirmation(self):
        for choices in [['Open the shop', 'Buy a ticket'], ['Choose a soft pillow'],
                        ['Choose spicy food', 'Choose a soft pillow']]:
            self.assertEqual(match_regions([example()], ['Quiet afternoon'], choices)[0], 'confirm')

    def test_missing_title_falls_back_to_full_choice_group(self):
        state, _, reason = match_regions([example()], [], ['Choose a soft pillow', 'Choose spicy food'])
        self.assertEqual(state, 'matched')
        self.assertIn('选项组合已匹配', reason)
        self.assertNotEqual(match_regions([example()], [], ['Choose a soft pillow'])[0], 'matched')

    def test_duplicate_title_requires_choices(self):
        other = example(source='Other sheet')
        other.options = [Option(1, 'Open the shop', 'Money -10'), Option(2, 'Buy a ticket', 'Money -20')]
        self.assertEqual(match_regions([example(), other], ['Quiet afternoon'], [])[0], 'confirm')
        state, candidates, _ = match_regions([example(), other], ['Quiet afternoon'],
                                             ['Choose a soft pillow', 'Choose spicy food'])
        self.assertEqual(state, 'matched')
        self.assertEqual(candidates[0].event.source, 'Journey')

    def test_shared_choices_without_title_remain_ambiguous(self):
        self.assertEqual(match_regions([example(), example('Other event', 'Other sheet')], [],
                                      ['Choose a soft pillow', 'Choose spicy food'])[0], 'confirm')

    def test_wrapped_title_and_unknown_screen(self):
        self.assertEqual(match_regions([example()], ['Quiet', 'afternoon'], [])[0], 'matched')
        self.assertEqual(match_regions([example()], [], [])[0], 'unknown')
        self.assertEqual(match_regions([example()], ['Settings'], ['Audio', 'Video'])[0], 'unknown')

    def test_region_crops_scale_and_validate(self):
        from PIL import Image
        self.assertTrue(valid_regions(DEFAULT_REGIONS))
        crops = crop_regions(Image.new('RGB', (2000, 1250)), DEFAULT_REGIONS)
        self.assertEqual(crops['title'].size, (270, 94))
        self.assertEqual(crops['options'].size, (680, 444))
        with self.assertRaises(ValueError):
            crop_regions(Image.new('RGB', (100, 100)), {'title': (0, 0, 1, 1)})


if __name__ == '__main__':
    unittest.main()
