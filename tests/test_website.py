import copy
import tempfile
import unittest
from pathlib import Path

from star_savior.i18n import LANGUAGES
from star_savior.website import WebsiteStore, convert, localized, localized_phase


def name(value):
    return {language: value for language in LANGUAGES}


def snapshot():
    event = {'id': 1, 'name': name('An afternoon'), 'times': ['March'], 'choices': [
        {'name': name('Rest'), 'condition': {'type': 'RR_STAMINA_USE', 'value': 20},
         'success_rewards': [[{'type': 'RT_STAT', 'reward_stat': 'JST_POWER', 'min': 10, 'max': 20},
                              {'type': 'RT_COIN', 'min': 30, 'max': 30}],
                             [{'type': 'RT_JOURNEY_ITEM', 'reward_id': 1, 'min': 1, 'max': 1}]],
         'failure_rewards': [[{'type': 'RT_CONDITION', 'min': -1, 'max': -1}]]}]}
    reference = {'id': 1, 'name': name('Survey relic'), 'desc': name('Preserved description')}
    return {'journeys': {'Afternoon': [event]},
            'arcanas': [{'id': 99, 'name': name('Card'), 'events': []}],
            **{key: [reference] for key in ('journey_items', 'potentials', 'stat_potentials', 'journey_buffs')}}


class WebsiteTests(unittest.TestCase):
    def test_card_identity_and_catalog_survive_cache_reload(self):
        raw = snapshot()
        raw['arcanas'][0]['events'] = [copy.deepcopy(raw['journeys']['Afternoon'][0])]
        for language in LANGUAGES:
            events = convert(raw, language)
            self.assertIsNone(events[0].card_id)
            self.assertEqual(events[1].card_id, 99)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'website.sqlite3'
            store = WebsiteStore(path)
            self.assertEqual(store.cards(), [])
            store.replace(raw)
            store.db.close()
            reopened = WebsiteStore(path)
            self.assertEqual(reopened.cards(), raw['arcanas'])
            self.assertEqual(reopened.load()[1].card_id, 99)
            reopened.db.close()

    def test_difficulty_filters_conditions_and_scales_only_potential_points(self):
        raw = snapshot()
        template = raw['journeys']['Afternoon'][0]
        variants = []
        for index, (tier, threshold) in enumerate((('Easy', 200), ('Normal', 300), ('Hard', 500)), 1):
            variant = copy.deepcopy(template)
            variant.update(id=index, difficulties=[name(tier)])
            choice = variant['choices'][0]
            choice['condition'] = {'type': 'RR_STAT', 'target': 'JST_POWER', 'value': threshold}
            choice['success_rewards'] = [
                [{'type': 'RT_STAT', 'reward_stat': 'JST_FOCUS', 'min': 20, 'max': 20},
                 {'type': 'RT_STAT', 'reward_stat': 'JST_FOCUS', 'min': 30, 'max': 30}],
                [{'type': 'RT_POTEN_POINT', 'min': 20, 'max': 20}]]
            variants.append(variant)
        raw['journeys']['Afternoon'] = variants
        for tier, threshold, points in [('Easy', 200, 20), ('Normal', 300, 30), ('Hard', 500, 50)]:
            effect = convert(raw, 'en-US', tier)[0].options[0].effect
            self.assertIn(f'Strength >={threshold}', effect)
            self.assertIn('Focus +20 OR Focus +30', effect)
            self.assertIn(f'Potential Point +{points}', effect)
            self.assertNotIn('Variant', effect)
            self.assertNotIn('×', effect)
            for other in {'Easy', 'Normal', 'Hard'} - {tier}:
                self.assertNotIn(other, effect)

    def test_unrestricted_events_ranges_and_costs(self):
        raw = snapshot()
        choice = raw['journeys']['Afternoon'][0]['choices'][0]
        choice['condition'] = {'type': 'RR_PP_USE', 'value': 20}
        choice['success_rewards'] = [[{'type': 'RT_POTEN_POINT', 'min': 10, 'max': 20}],
                                     [{'type': 'RT_STAMINA', 'min': -20, 'max': -20}]]
        effect = convert(raw, 'en-US', 'Hard')[0].options[0].effect
        self.assertIn('Potential Point +25~+50', effect)
        self.assertIn('Requirement/cost: Potential Point -20', effect)
        self.assertIn('Stamina -20', effect)
        self.assertIn('Failure: Condition -1', effect)
        self.assertEqual(len(convert(raw, 'en-US', 'Easy')), 1)

    def test_multi_difficulty_variants_and_cache_switch_without_sync(self):
        raw = snapshot()
        raw['journeys']['Afternoon'][0]['difficulties'] = [name('Easy'), name('Hard')]
        self.assertEqual(convert(raw, 'en-US', 'Normal'), [])
        self.assertIn('Hard', convert(raw, 'en-US', 'Hard')[0].options[0].effect)
        with tempfile.TemporaryDirectory() as directory:
            store = WebsiteStore(Path(directory) / 'website.sqlite3')
            store.replace(raw)
            updated = store.updated()
            self.assertEqual(store.load(), [])
            store.difficulty = 'Hard'
            self.assertEqual(len(store.load()), 1)
            store.difficulty = 'Normal'
            self.assertEqual(store.load(), [])
            self.assertEqual(store.updated(), updated)
            invalid = copy.deepcopy(raw)
            invalid['journeys']['Afternoon'][0]['difficulties'] = [name('Expert')]
            with self.assertRaises(ValueError):
                store.replace(invalid)
            self.assertEqual(store.updated(), updated)
            self.assertEqual(len(store.load(difficulty='Hard')), 1)
            store.db.close()

    def test_arcana_ids_are_internal_and_effects_have_human_source(self):
        raw = snapshot()
        arcana_event = copy.deepcopy(raw['journeys']['Afternoon'][0])
        arcana_event['id'] = 710250102
        arcana_event.pop('times')
        raw['arcanas'] = [{'id': 7102501, 'name': name('Custom Training'), 'events': [arcana_event]}]
        event = convert(raw, 'en-US')[-1]
        self.assertEqual(event.phase, '710250102')
        self.assertIn('7102501', event.source)
        self.assertEqual(event.visible_phase, '')
        self.assertEqual(event.visible_source, 'Arcana: Custom Training')
        self.assertNotIn('710250102', event.options[0].effect)

    def test_raw_korean_phase_is_localized_without_text_fallback(self):
        from star_savior.i18n import tr
        raw = snapshot()
        source_phase = '3\uC6D4 \uCD08\uC21C'
        raw['journeys']['Afternoon'][0]['times'] = [source_phase]
        for language in LANGUAGES:
            self.assertEqual(localized_phase(source_phase, language), tr('phase_early', language, month=3))
            effect = convert(raw, language)[0].options[0].effect
            self.assertIn(tr('phase_early', language, month=3), effect)
            if language != 'ko-KR':
                self.assertNotIn(source_phase, effect)
        self.assertEqual(raw['journeys']['Afternoon'][0]['times'], [source_phase])
        self.assertEqual(localized_phase('11\uC6D4 \uC911\uC21C', 'en-US'), 'Mid 11')
        self.assertEqual(localized_phase('5\uC6D4 \uD558\uC21C', 'en-US'), 'Late 5')
        self.assertEqual(localized_phase('Unknown stage', 'zh-CN'), 'Unknown stage')

    def test_blank_translation_falls_back_after_markup_cleanup(self):
        text = {'zh-CN': '<b> </b>', 'en-US': 'Complete English description', 'ko-KR': 'Korean description'}
        self.assertEqual(localized(text, 'zh-CN'), 'Complete English description')
        self.assertEqual(localized(text, 'zh-CN', mark_fallback=True), 'Complete English description [en-US]')
        text['en-US'] = '  '
        self.assertEqual(localized(text, 'zh-CN', mark_fallback=True), 'Korean description [ko-KR]')

    def test_missing_reference_translation_preserves_description_and_numbers(self):
        raw = snapshot()
        raw['journey_items'][0]['name']['zh-CN'] = ''
        raw['journey_items'][0]['desc']['zh-CN'] = '  '
        effect = convert(raw, 'zh-CN')[0].options[0].effect
        self.assertIn('Survey relic [en-US]', effect)
        self.assertIn('Preserved description [en-US]', effect)
        self.assertIn('+10~+20', effect)
        self.assertIn('+30', effect)

    def test_effect_labels_use_type_codes_without_source_translations(self):
        raw = snapshot()
        raw['journeys']['Afternoon'][0]['choices'][0]['success_rewards'] = [
            [{'type': 'RT_CONDITION', 'min': -1, 'max': -1}],
            [{'type': 'RT_STAMINA', 'min': 5, 'max': 5}],
            [{'type': 'RT_STAT', 'reward_stat': 'JST_POWER', 'min': 15, 'max': 15}]]
        from star_savior.i18n import tr
        effect = convert(raw, 'zh-CN')[0].options[0].effect
        for key, value in [('RT_CONDITION', '-1'), ('RT_STAMINA', '+5'), ('POWER', '+15')]:
            self.assertIn(tr(key, 'zh-CN') + ' ' + value, effect)

    def test_conditions_alternatives_failure_ranges_and_references(self):
        effect = convert(snapshot(), 'en-US')[0].options[0].effect
        for text in ('Stamina -20', 'Strength +10~+20 OR Old Coin +30', 'Survey relic', 'Failure: Condition -1'):
            self.assertIn(text, effect)

    def test_identical_choices_preserve_variant_effects(self):
        raw = snapshot()
        second = copy.deepcopy(raw['journeys']['Afternoon'][0])
        second['id'] = 2
        second['choices'][0]['success_rewards'][0][0]['max'] = 40
        raw['journeys']['Afternoon'].append(second)
        events = convert(raw, 'en-US')
        self.assertEqual(len(events), 1)
        self.assertIn('+10~+20', events[0].options[0].effect)
        self.assertIn('+10~+40', events[0].options[0].effect)

    def test_five_languages_persist_and_invalid_sync_preserves_previous(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'website.sqlite3'
            store = WebsiteStore(path)
            store.replace(snapshot())
            previous = store.updated()
            invalid = snapshot()
            invalid['journey_items'] = []
            with self.assertRaises(ValueError):
                store.replace(invalid)
            self.assertEqual(store.updated(), previous)
            self.assertEqual(len(store.load()), 1)
            store.db.close()
            reopened = WebsiteStore(path)
            for language in LANGUAGES:
                self.assertEqual(len(reopened.load(language)), 1)
            reopened.db.close()

    def test_missing_reference_is_not_silently_dropped(self):
        raw = snapshot()
        raw['journeys']['Afternoon'][0]['choices'][0]['success_rewards'][1][0]['reward_id'] = 42
        with self.assertRaises(KeyError):
            convert(raw, 'en-US')
