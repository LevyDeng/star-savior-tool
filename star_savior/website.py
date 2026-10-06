"""Public website JSON adapter and transactional multilingual offline cache."""
import html
import http.client
import json
import re
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request

from .core import Event, Option, validate
from .i18n import LANGUAGES, tr
from .network import sync_opener

SOURCE_URL = 'https://star-savior-arcana-db.pages.dev/journey'
BASE_URL = 'https://star-savior-arcana-db.pages.dev/data/'
FILES = ('journeys', 'arcanas', 'journey_items', 'potentials', 'stat_potentials', 'journey_buffs')
DIFFICULTIES = {'Easy': 1, 'Normal': 1.5, 'Hard': 2.5}
REQUEST_TIMEOUT = 60
MAX_DOWNLOAD_ATTEMPTS = 2
RETRYABLE_HTTP_STATUS = {408, 429, 500, 502, 503, 504}


def download(proxy_url='', verify_tls=True):
    opener = sync_opener(proxy_url, verify_tls)
    def read(name):
        url = BASE_URL + name + '.json'
        request = Request(url, headers={'User-Agent': 'StarSaviorGuideDemo/1.0'})
        for attempt in range(1, MAX_DOWNLOAD_ATTEMPTS + 1):
            try:
                with opener.open(request, timeout=REQUEST_TIMEOUT) as response:
                    if response.url != url:
                        raise ValueError(f'{name}.json returned an unexpected redirect')
                    body = response.read(16_000_001)
                    if len(body) > 16_000_000:
                        raise ValueError(f'{name}.json exceeds the 16 MB size limit')
                    return json.loads(body.decode('utf-8'))
            except HTTPError as exc:
                if exc.code not in RETRYABLE_HTTP_STATUS:
                    raise RuntimeError(f'{name}.json returned HTTP {exc.code}') from exc
                error = exc
            except (URLError, OSError, http.client.HTTPException,
                    json.JSONDecodeError, UnicodeDecodeError) as exc:
                error = exc
            if attempt == MAX_DOWNLOAD_ATTEMPTS:
                raise RuntimeError(
                    f'{name}.json download failed after {attempt} attempts: {error}') from error
            time.sleep(attempt * 2)

    with ThreadPoolExecutor(max_workers=3) as pool:
        return dict(zip(FILES, pool.map(read, FILES)))


def localized(value, language, mark_fallback=False):
    if isinstance(value, dict):
        for candidate in dict.fromkeys((language, 'en-US', 'ko-KR')):
            original = value.get(candidate)
            if not isinstance(original, str):
                continue
            text = html.unescape(re.sub(r'<[^>]+>', '', original)).strip()
            if text:
                if mark_fallback and candidate != language:
                    return text + f' [{candidate}]'
                return text
        return ''
    if not isinstance(value, str):
        raise ValueError('Invalid localized text')
    return html.unescape(re.sub(r'<[^>]+>', '', value)).strip()


def localized_phase(value, language):
    """Translate the source's Korean month segments without changing raw data."""
    if not isinstance(value, str):
        return localized(value, language)
    match = re.fullmatch(r'\s*(\d{1,2})\uC6D4\s*(\uCD08\uC21C|\uC0C1\uC21C|\uC911\uC21C|\uD558\uC21C)\s*', value)
    if not match or not 1 <= int(match[1]) <= 12:
        return value
    segments = {'\uCD08\uC21C': 'early', '\uC0C1\uC21C': 'early', '\uC911\uC21C': 'mid', '\uD558\uC21C': 'late'}
    return tr('phase_' + segments[match[2]], language, month=int(match[1]))


def convert(raw, language, difficulty='Normal'):
    if difficulty not in DIFFICULTIES:
        raise ValueError('Unsupported difficulty')
    if language not in LANGUAGES or set(raw) != set(FILES):
        raise ValueError('Unsupported language or incomplete website snapshot')
    if not isinstance(raw['journeys'], dict) or not raw['journeys']:
        raise ValueError('Journey data is empty or malformed')
    if any(not isinstance(raw[key], list) or not raw[key] for key in FILES[1:]):
        raise ValueError('Reference data is empty or malformed')
    references = {key: {entry['id']: entry for entry in raw[key]} for key in FILES[2:]}
    linked = {'RT_JOURNEY_ITEM': 'journey_items', 'RT_SE_POTEN': 'potentials',
              'RT_STAT_POTEN': 'stat_potentials', 'RT_JOURNEY_BUFF': 'journey_buffs'}

    def number(value):
        return f'{value:+g}'

    def reward(entry):
        kind = entry['type']
        if kind in linked:
            target = references[linked[kind]][entry['reward_id']]
            label = localized(target['name'], language, mark_fallback=True)
            description = target.get('desc') or target.get('description')
            if description:
                translated = localized(description, language, mark_fallback=True)
                if translated:
                    label += ' (' + translated + ')'
        elif kind == 'RT_STAT':
            label = tr(entry['reward_stat'].removeprefix('JST_'), language)
        else:
            label = tr(kind, language)
            if label == kind:
                raise ValueError(f'Unsupported reward type: {kind}')
        if 'min' in entry and kind != 'RT_STAT_POTEN':
            multiplier = DIFFICULTIES[difficulty] if kind == 'RT_POTEN_POINT' else 1
            minimum, maximum = entry['min'] * multiplier, entry['max'] * multiplier
            label += ' ' + (number(minimum) if minimum == maximum
                            else number(minimum) + '~' + number(maximum))
        return label

    def rewards(groups):
        if not isinstance(groups, list):
            raise ValueError('Malformed reward groups')
        return '; '.join(tr('or', language).join(reward(entry) for entry in group) for group in groups) or tr('none', language)

    def condition(entry):
        kind = entry['type']
        labels = {'RR_STAMINA_USE': 'RT_STAMINA', 'RR_COIN_USE': 'RT_COIN', 'RR_PP_USE': 'RT_POTEN_POINT'}
        if kind in labels:
            label = tr(labels[kind], language)
        elif kind in ('RR_ITEM_USE', 'RR_ITEM_CHECK'):
            label = localized(references['journey_items'][int(entry['target'])]['name'], language)
        elif kind == 'RR_STAT':
            label = tr(entry['target'].removeprefix('JST_'), language)
        else:
            raise ValueError(f'Unsupported condition type: {kind}')
        operator = '>=' if kind in ('RR_STAT', 'RR_ITEM_CHECK') else '-'
        return f'{tr("condition", language)}: {label} {operator}{entry.get("value", "")}'

    events = []

    def add(variants, source, display_source, card_id=None):
        grouped = {}
        for variant in variants:
            tiers = [localized(value, 'en-US') for value in variant.get('difficulties') or []]
            if any(tier not in DIFFICULTIES for tier in tiers):
                raise ValueError('Unsupported source difficulty')
            if tiers and difficulty not in tiers:
                continue
            names = tuple(localized(c['name'], language) or tr('automatic', language) for c in variant['choices'])
            if not names:
                raise ValueError('Event has no reward choices')
            grouped.setdefault((localized(variant['name'], language), names), []).append(variant)
        for (title, names), versions in grouped.items():
            options = []
            for index, name in enumerate(names):
                effects = []
                for version_index, variant in enumerate(versions, 1):
                    choice = variant['choices'][index]
                    context = []
                    if len(versions) > 1:
                        context.append(tr('variant', language, number=version_index))
                    context.extend(localized_phase(value, language) for value in variant.get('times') or [])
                    if variant.get('difficulties'):
                        context.append(tr(difficulty, language))
                    context.extend(localized(x, language) for x in variant.get('battle_names') or [])
                    lines = ['[' + ' | '.join(context) + ']'] if context else []
                    if choice.get('condition'):
                        lines.append(condition(choice['condition']))
                    lines.append(tr('success', language) + ': ' + rewards(choice['success_rewards']))
                    if choice.get('failure_rewards') is not None and choice['failure_rewards']:
                        lines.append(tr('failure', language) + ': ' + rewards(choice['failure_rewards']))
                    effects.append('\n'.join(lines))
                options.append(Option(index + 1, name, '\n\n'.join(effects)))
            phase = ' | '.join(str(v['id']) for v in versions)
            visible_phase = ' | '.join(dict.fromkeys(localized_phase(time, language)
                for variant in versions for time in variant.get('times') or []))
            events.append(Event(title, phase, source, options, visible_phase, display_source, card_id))

    for key, variants in raw['journeys'].items():
        add(variants, 'Website / Journey / ' + str(variants[0]['id']), tr('journey_source', language))
    for card in raw['arcanas']:
        for event in card['events']:
            add([event], 'Website / Arcana / ' + localized(card['name'], language) + ' / ' + str(card['id']),
                tr('arcana_source', language, card=localized(card['name'], language)), card['id'])
    issues = validate(events) if events else []
    if issues:
        raise ValueError('\n'.join(issues))
    return events


class WebsiteStore:
    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute('CREATE TABLE IF NOT EXISTS website (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL, updated TEXT NOT NULL)')
        self.db.commit()
        self.language = 'zh-CN'
        self.difficulty = 'Normal'
        self.cache = {}

    def load(self, language=None, difficulty=None):
        language = language or self.language
        difficulty = difficulty or self.difficulty
        key = (language, difficulty)
        if key not in self.cache:
            row = self.db.execute('SELECT payload FROM website WHERE id=1').fetchone()
            self.cache[key] = convert(json.loads(row[0]), language, difficulty) if row else []
        return self.cache[key]

    def updated(self):
        row = self.db.execute('SELECT updated FROM website WHERE id=1').fetchone()
        return row[0] if row else 'Never'

    def cards(self):
        """Return the synchronized card catalog without sharing SQLite across threads."""
        row = self.db.execute('SELECT payload FROM website WHERE id=1').fetchone()
        return json.loads(row[0])['arcanas'] if row else []

    def replace(self, raw):
        converted = {(language, difficulty): convert(raw, language, difficulty)
                     for language in LANGUAGES for difficulty in DIFFICULTIES}
        payload = json.dumps(raw, ensure_ascii=False, sort_keys=True)
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO website VALUES (1, ?, ?)',
                            (payload, datetime.now(timezone.utc).isoformat()))
        self.cache = converted
