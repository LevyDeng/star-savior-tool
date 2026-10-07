"""Export portable vocabulary and parity fixtures from the desktop reference."""
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from star_savior.core import Event, Option, match_regions
from star_savior.i18n import LANGUAGES, _rows
from star_savior.layout import DEFAULT_REGIONS
from star_savior.website import DIFFICULTIES, FILES, convert


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    codes = list(LANGUAGES)
    write(ROOT / 'shared/assets/vocabulary.json', {
        code: {key: row[index] for key, row in _rows.items()}
        for index, code in enumerate(codes)})
    write(ROOT / 'shared/assets/contract.json', {
        'schema_version': 1, 'files': FILES, 'languages': LANGUAGES,
        'difficulties': DIFFICULTIES, 'regions': DEFAULT_REGIONS})
    training = Event('Training direction', '1', 'Fixture', [
        Option(1, 'Attack training', 'Strength +10'),
        Option(2, 'Survival training', 'Vitality +10')])
    duplicate = Event(training.title, '2', 'Other card', training.options, card_id=2)
    cases = []
    for name, events, title, choices in (
            ('exact', [training], ['Training direction'], ['Attack training', 'Survival training']),
            ('title_only', [training], ['Training direction'], []),
            ('wrapped', [training], ['Training', 'direction'], ['Attack', 'training', 'Survival training']),
            ('typo', [training], ['Training direktion'], ['Attack training', 'Survival training']),
            ('unknown', [training], ['Beach party'], ['Eat lunch']),
            ('duplicate_cards', [training, duplicate], ['Training direction'], ['Attack training', 'Survival training']),
            ('reversed', [training], ['Training direction'], ['Survival training', 'Attack training'])):
        state, candidates, _ = match_regions(events, title, choices)
        cases.append({'name': name, 'events': [asdict(event) for event in events],
                      'title': title, 'choices': choices, 'state': state,
                      'candidates': [{'phase': c.event.phase, 'score': c.score} for c in candidates]})
    write(ROOT / 'shared/fixtures/matching.json', cases)
    label = lambda text: {code: text for code in codes}
    reference = {'id': 1, 'name': label('Survey relic'), 'desc': label('Reference description')}
    event = {'id': 1, 'name': label('An afternoon'), 'times': ['March'], 'choices': [{
        'name': label('Train'), 'condition': {'type': 'RR_STAT', 'target': 'JST_POWER', 'value': 200},
        'success_rewards': [[{'type': 'RT_POTEN_POINT', 'min': 20, 'max': 20}],
                            [{'type': 'RT_STAT', 'reward_stat': 'JST_FOCUS', 'min': 20, 'max': 30}],
                            [{'type': 'RT_JOURNEY_ITEM', 'reward_id': 1, 'min': 1, 'max': 1}]],
        'failure_rewards': [[{'type': 'RT_STAMINA', 'min': -5, 'max': -5}]]}]}
    raw = {'journeys': {'Afternoon': [event]},
           'arcanas': [{'id': 99, 'name': label('Card'), 'events': [dict(event, id=2)]}],
           **{key: [reference] for key in FILES[2:]}}
    write(ROOT / 'shared/fixtures/conversion.json', {'raw': raw, 'expected': {
        f'{language}/{difficulty}': [asdict(event) for event in convert(raw, language, difficulty)]
        for language in codes for difficulty in DIFFICULTIES}})


if __name__ == '__main__':
    main()
