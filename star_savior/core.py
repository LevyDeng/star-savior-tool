"""Platform-independent guide storage, import, and conservative matching."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path


@dataclass
class Option:
    order: int
    text: str
    effect: str


@dataclass
class Event:
    title: str
    phase: str
    source: str
    options: list[Option] = field(default_factory=list)
    display_phase: str | None = None
    display_source: str | None = None
    card_id: int | None = None

    @property
    def visible_phase(self):
        return self.phase if self.display_phase is None else self.display_phase

    @property
    def visible_source(self):
        return self.source if self.display_source is None else self.display_source


def normalize(text: str) -> str:
    text = unicodedata.normalize('NFKC', text).casefold()
    text = re.sub(r'^\s*\d+\s*[.、:)]\s*', '', text)
    return ''.join(c for c in text if unicodedata.category(c)[0] not in 'PZC')


def validate(events: list[Event]) -> list[str]:
    issues = []
    seen = set()
    if not events:
        issues.append('未找到事件。请检查是否选择了事件页签，以及列号是否正确。')
    for event in events:
        key = (event.source, event.phase, event.title)
        if key in seen:
            issues.append(f'事件重复：{event.title}（{event.source}）')
        seen.add(key)
        if not event.title or not event.source or not event.options:
            issues.append(f'事件信息不完整：{event.title or "（无标题）"}')
        for index, option in enumerate(event.options, 1):
            if option.order != index or not option.text.strip() or not option.effect.strip():
                issues.append(f'缺少选项文字或效果，或选项编号不连续：{event.title} 第 {option.order} 项')
    return issues






@dataclass
class Candidate:
    event: Event
    score: float
    option_scores: list[float]
    title_score: float = 0.0


def _option_scores(event, normalized):
    cursor, scores = 0, []
    for option in event.options:
        target = normalize(option.text)
        best = (0.0, cursor)
        for start in range(cursor, len(normalized)):
            for end in range(start + 1, min(start + 3, len(normalized)) + 1):
                similarity = SequenceMatcher(None, target, ''.join(normalized[start:end])).ratio()
                if similarity > best[0]:
                    best = similarity, end
        scores.append(best[0])
        cursor = best[1]
    return scores


def match_regions(events: list[Event], title_lines: list[str], option_lines: list[str]):
    """Use a unique title first; choices verify it or provide a fallback.

    A readable but contradictory choice group always requires confirmation.
    Duplicate titles need a complete distinguishing choice group. A missing
    title can be recovered from at least two strongly matched ordered choices.
    """
    titles = [normalize(line) for line in title_lines if normalize(line)]
    choices = [normalize(line) for line in option_lines if normalize(line)]
    title_segments = [''.join(titles[start:end]) for start in range(len(titles))
                      for end in range(start + 1, min(start + 3, len(titles)) + 1)]
    scored = []
    for event in events:
        if not event.options:
            continue
        title_score = max((SequenceMatcher(None, normalize(event.title), line).ratio()
                           for line in title_segments), default=0)
        scores = _option_scores(event, choices)
        option_score = sum(scores) / len(scores)
        scored.append(Candidate(event, option_score, scores, title_score))
    strongest_title = max((c.title_score for c in scored), default=0)
    title_mode = strongest_title >= 0.88
    candidates = []
    for candidate in scored:
        option_score = candidate.score
        if title_mode:
            if candidate.title_score < 0.75 and option_score < 0.90:
                continue
            candidate.score = (0.65 * candidate.title_score + 0.35 * option_score
                               if choices else candidate.title_score)
        elif option_score < 0.55:
            continue
        candidates.append(candidate)
    candidates.sort(key=lambda c: c.score, reverse=True)
    candidates = candidates[:5]
    if not candidates:
        return 'unknown', [], '没有找到匹配的事件标题或选项组合。'
    top = candidates[0]
    margin = top.score - candidates[1].score if len(candidates) > 1 else 1.0
    full_options = min(top.option_scores) >= 0.90 and sum(top.option_scores) / len(top.option_scores) >= 0.93
    if title_mode:
        if top.title_score >= 0.94 and margin >= 0.10:
            if not choices:
                return 'matched', candidates, '标题已匹配；没有读取到选项文字，无法进行二次核对。'
            if full_options:
                return 'matched', candidates, '标题已匹配，选项也已核对。'
        return 'confirm', candidates, '标题或选项模糊、不完整或相互矛盾。请确认正确事件。'
    if full_options and len(top.event.options) >= 2 and margin >= 0.10:
        return 'matched', candidates, '标题无法识别或未匹配，但完整选项组合已匹配。'
    return 'confirm', candidates, '标题无法识别或未匹配，请确认选项匹配出的候选事件。'


def match(events: list[Event], lines: list[str]) -> tuple[str, list[Candidate]]:
    """Rank ordered option groups; ambiguous or partial input requires confirmation."""
    normalized = [normalize(line) for line in lines if normalize(line)]
    candidates = []
    for event in events:
        # Allow line wrapping by joining up to three adjacent OCR lines.
        scores = _option_scores(event, normalized)
        title = normalize(event.title)
        title_score = max((SequenceMatcher(None, title, line).ratio() for line in normalized), default=0)
        score = sum(scores) / len(scores) * 0.85 + title_score * 0.15
        candidates.append(Candidate(event, score, scores))
    candidates.sort(key=lambda c: c.score, reverse=True)
    candidates = [c for c in candidates if c.score >= 0.55][:5]
    if not candidates:
        return 'unknown', []
    top = candidates[0]
    margin = top.score - candidates[1].score if len(candidates) > 1 else 1.0
    # One-option events need a strong title as well as a strong option match.
    auto = top.score >= 0.92 and min(top.option_scores) >= 0.90 and margin >= 0.10
    return ('matched' if auto else 'confirm'), candidates
