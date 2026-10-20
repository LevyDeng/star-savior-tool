"""ESPR public page adapter. Each locale is validated and stored independently."""
import html
import json
import re
import sqlite3
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.error import HTTPError
from urllib.request import Request

from .core import Event, Option, validate
from .i18n import tr
from .network import sync_opener
from .website import DIFFICULTIES

SOURCE_URL = 'https://ss.espr.gg/{locale}/database/journey-events'
LOCALES = {'zh-CN': 'zh-CN', 'zh-TW': 'zh-TW', 'en-US': 'en', 'ja-JP': 'ja', 'ko-KR': 'ko'}


def source_url(language):
    return SOURCE_URL.format(locale=LOCALES[language])


def extractor_path():
    from pathlib import Path
    bundled = Path(__file__).with_name('assets') / 'espr-extract.js'
    return bundled if bundled.exists() else Path(__file__).parent.parent / 'shared/assets/espr-extract.js'


class _Scripts(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.inside = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        self.inside = tag == 'script'

    def handle_endtag(self, tag):
        if tag == 'script':
            self.inside = False

    def handle_data(self, value):
        if self.inside:
            self.parts.append(value)


def parse_page(page):
    parser = _Scripts()
    parser.feed(page)
    chunks = []
    for script in parser.parts:
        if script.strip().startswith('self.__next_f.push('):
            value = json.loads(script[script.index('(') + 1:script.rindex(')')])
            if value[0] == 1 and isinstance(value[1], str):
                chunks.append(value[1])
    stream = ''.join(chunks)
    start = stream.find('{"events":')
    if start < 0:
        raise ValueError('ESPR_BROWSER_REQUIRED: Complete event payload is absent; open the source in the sync browser.')
    return json.JSONDecoder().raw_decode(stream[start:])[0]


def download(language, proxy_url='', verify_tls=True):
    url = source_url(language)
    request = Request(url, headers={'User-Agent': 'StarSaviorHelper/1.0', 'Accept': 'text/html'})
    try:
        with sync_opener(proxy_url, verify_tls).open(request, timeout=45) as response:
            if response.url != url:
                raise ValueError('Unexpected ESPR redirect')
            body = response.read(8_000_001)
            if len(body) > 8_000_000:
                raise ValueError('ESPR page exceeds 8 MB')
            data = parse_page(body.decode('utf-8'))
    except HTTPError as error:
        if error.code in (403, 429):
            raise RuntimeError(f'ESPR_BROWSER_REQUIRED: HTTP {error.code}') from error
        raise
    return {'language': language, 'data': data}


def _text(value):
    if value in (None, '$undefined'):
        return ''
    if not isinstance(value, str) or value.startswith('$'):
        raise ValueError('Unsupported ESPR text reference')
    return html.unescape(re.sub('<[^>]+>', '', value)).strip()


def convert(raw, language, difficulty):
    if difficulty not in DIFFICULTIES:
        raise ValueError('Unsupported difficulty')
    entries = raw.get('events')
    if not isinstance(entries, list) or not entries or not isinstance(raw.get('tiers'), list):
        raise ValueError('Incomplete ESPR event payload')
    ids = set()
    tier = list(DIFFICULTIES).index(difficulty)

    def rewards(groups):
        if not isinstance(groups, list):
            raise ValueError('Malformed ESPR reward groups')
        results = []
        for group in groups:
            chips = group['chips']
            if not isinstance(chips, list) or not chips:
                raise ValueError('Empty ESPR reward group')
            labels = []
            for chip in chips:
                label = _text(chip['label'])
                if not label:
                    raise ValueError('ESPR reward label is empty')
                amount = _text(chip.get('amount'))
                # Only potential-point chips receive the game difficulty multiplier.
                if re.search(r'potential\s*points?|[\u6f5c\u6f5b][\u8d28\u8cea]|\u6f5c\u5728.*\u30dd\u30a4\u30f3\u30c8|\uc7a0\uc7ac\ub825', label, re.I):
                    amount = re.sub(r'[+-]\d+(?:\.\d+)?', lambda m: f'{float(m[0]) * DIFFICULTIES[difficulty]:+g}', amount)
                note = _text(chip.get('note'))
                labels.append(label + (' ' + amount if amount else '') + (' (' + note + ')' if note else ''))
            results.append((tr('or', language) if group.get('oneOf') else '; ').join(labels))
        return '; '.join(results) or tr('none', language)

    events = []
    for entry in entries:
        event_id = str(entry['id'])
        if not event_id or event_id in ids:
            raise ValueError('Duplicate ESPR event identity')
        ids.add(event_id)
        title = _text(entry['title'])
        if not title or not isinstance(entry.get('choices'), list) or not entry['choices']:
            raise ValueError('ESPR event has no title or choices')
        cards = [_text(card) for card in entry.get('arcanas', [])]
        options = []
        for index, choice in enumerate(entry['choices'], 1):
            effects = []
            gate = choice.get('gate')
            if isinstance(gate, dict):
                counts = gate.get('counts')
                if isinstance(counts, list) and len(counts) != 3:
                    raise ValueError('Unexpected ESPR difficulty gates')
                count = counts[tier] if isinstance(counts, list) else gate['count']
                consumed = gate['kind'] != 'stat' and gate.get('consumed') is not False
                effects.append(tr('condition', language) + ': ' + _text(gate['name']) + (' -' if consumed else ' >=') + str(count))
                if isinstance(gate.get('convertPP'), (int, float)):
                    effects.append(tr('item_pp_value', language) + ': ' + str(gate['convertPP']))
            variants = choice.get('variants')
            variants = variants if isinstance(variants, list) and variants else [choice]
            for number, variant in enumerate(variants, 1):
                lines = []
                if len(variants) > 1:
                    lines.append('[' + tr('possible_result', language, number=number) + ']')
                lines.append(tr('success', language) + ': ' + rewards(variant['success']))
                if variant.get('failure'):
                    lines.append(tr('failure', language) + ': ' + rewards(variant['failure']))
                effects.append('\n'.join(lines))
            options.append(Option(index, _text(choice.get('label')) or tr('automatic', language), '\n\n'.join(effects)))
        display = 'ESPR.gg / ' + (tr('arcana_source', language, card=' / '.join(cards)) if cards else tr('journey_source', language))
        events.append(Event(title, event_id, 'ESPR.gg / Journey / ' + event_id, options, '', display, None))
    issues = validate(events)
    if issues:
        raise ValueError('\n'.join(issues))
    return events


class EsprStore:
    def __init__(self, path, catalog=None):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute('CREATE TABLE IF NOT EXISTS espr (language TEXT PRIMARY KEY, payload TEXT NOT NULL, updated TEXT NOT NULL)')
        self.db.commit()
        self.language, self.difficulty = 'zh-CN', 'Normal'
        self.cache = {}
        self.catalog = catalog or (lambda: [])

    def load(self, language=None, difficulty=None):
        language, difficulty = language or self.language, difficulty or self.difficulty
        key = language, difficulty
        if key not in self.cache:
            row = self.db.execute('SELECT payload FROM espr WHERE language=?', (language,)).fetchone()
            self.cache[key] = convert(json.loads(row[0]), language, difficulty) if row else []
            # Reuse image identity metadata only; rewards remain exclusively from ESPR.
            card_ids = {str(e['id']): card['id'] for card in self.catalog() for e in card.get('events', [])}
            for event in self.cache[key]:
                event.card_id = card_ids.get(event.phase)
        return self.cache[key]

    def updated(self):
        row = self.db.execute('SELECT updated FROM espr WHERE language=?', (self.language,)).fetchone()
        return row[0] if row else 'Never'

    def cards(self):
        return self.catalog()

    def replace(self, snapshot):
        language, raw = snapshot['language'], snapshot['data']
        if language not in LOCALES:
            raise ValueError('Unsupported ESPR locale')
        for difficulty in DIFFICULTIES:
            convert(raw, language, difficulty)
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO espr VALUES (?, ?, ?)',
                            (language, json.dumps(raw, ensure_ascii=False), datetime.now(timezone.utc).isoformat()))
        self.cache = {key: value for key, value in self.cache.items() if key[0] != language}
        # Identity enrichment is applied on the first load after replacement.

