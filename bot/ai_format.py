from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Tuple


# --- словарик для "псевдо-перевода" игровых новостей ---
TRANSLATE = {
    "patch": "патч",
    "update": "обновление",
    "major": "мейджор",
    "tournament": "турнир",
    "championship": "чемпионат",
    "qualifier": "квалификация",
    "announced": "анонсировали",
    "announce": "анонс",
    "release": "релиз",
    "released": "вышло",
    "new": "новый",
    "season": "сезон",
    "ranked": "ранговый",
    "skins": "скины",
    "skin": "скин",
    "battle pass": "боевой пропуск",
    "event": "ивент",
    "map": "карта",
    "maps": "карты",
    "operation": "операция",
    "esports": "киберспорт",
    "leak": "слив",
    "leaked": "слили",
    "rumor": "слух",
    "rumours": "слухи",
    "devs": "разработчики",
    "developers": "разработчики",
    "dev": "разраб",
    "studio": "студия",
    "valve": "Valve",
    "activision": "Activision",
    "blizzard": "Blizzard",
}

STOPWORDS = [
    "breaking", "exclusive", "report:", "reports:", "rumor:", "rumour:", "watch:",
    "trailer", "teaser", "official", "update:", "news:",
]

GAME_EMOJI = [
    (re.compile(r"\b(cs2|counter[- ]?strike|counterstrike)\b", re.I), "💣", "CS2"),
    (re.compile(r"\b(dota\s*2|dota2)\b", re.I), "🧙", "Dota 2"),
    (re.compile(r"\b(warface)\b", re.I), "🔫", "Warface"),
    (re.compile(r"\b(call of duty|cod|warzone)\b", re.I), "🎖", "Call of Duty"),
]

CATEGORY_EMOJI = [
    (re.compile(r"\b(patch|update|hotfix|balance)\b", re.I), "🛠", "Патч/обновление"),
    (re.compile(r"\b(announce|announced|reveal|unveil|анонс)\b", re.I), "📢", "Анонс"),
    (re.compile(r"\b(major|tournament|qualifier|championship|esports|киберспорт)\b", re.I), "🏆", "Киберспорт"),
    (re.compile(r"\b(release|released|launch|out now)\b", re.I), "🆕", "Релиз"),
    (re.compile(r"\b(leak|leaked|datamine|rumou?r)\b", re.I), "🕵️", "Сливы/слухи"),
]


def _clean_title(title: str) -> str:
    t = (title or "").strip()
    # убираем мусорные префиксы
    for w in STOPWORDS:
        t = re.sub(rf"^\s*{re.escape(w)}\s*", "", t, flags=re.I)
    # нормализуем пробелы
    t = re.sub(r"\s+", " ", t).strip()
    # иногда заголовки с " | site"
    t = re.sub(r"\s*\|\s*[^|]{2,40}$", "", t).strip()
    return t


def _detect_game(title: str) -> Tuple[str, str]:
    for rx, emoji, name in GAME_EMOJI:
        if rx.search(title):
            return emoji, name
    return "🎮", "Игры"


def _detect_category(title: str) -> Tuple[str, str]:
    for rx, emoji, name in CATEGORY_EMOJI:
        if rx.search(title):
            return emoji, name
    return "📰", "Новости"


def _pseudo_translate_en_ru(text: str) -> str:
    # Очень лёгкий "перевод" по словарю + сохранение брендов
    t = text

    # устойчивые фразы сначала
    pairs = sorted(TRANSLATE.items(), key=lambda x: -len(x[0]))
    for en, ru in pairs:
        t = re.sub(rf"\b{re.escape(en)}\b", ru, t, flags=re.I)

    # косметика
    t = t.replace("’", "'")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _make_summary(title_ru: str) -> str:
    # делаем 1 строку "суть" простым правилом
    # если есть ключевое слово — добавим "Коротко: ..."
    lower = title_ru.lower()
    if any(k in lower for k in ["патч", "обновление", "hotfix", "фикс"]):
        return "Коротко: вышло обновление/фиксы."
    if any(k in lower for k in ["анонс", "анонсировали", "reveal"]):
        return "Коротко: появился анонс/подробности."
    if any(k in lower for k in ["турнир", "мейджор", "квалификация", "чемпионат"]):
        return "Коротко: новости по киберспорту."
    if any(k in lower for k in ["релиз", "вышло", "launch"]):
        return "Коротко: релиз/выход контента."
    if any(k in lower for k in ["слив", "слух"]):
        return "Коротко: инсайд/слухи (проверяй официально)."
    return "Коротко: подробности по ссылке."


@dataclass
class FreeAIFormatter:
    """
    Бесплатное "AI-похожее" форматирование без API.
    """

    def format_post(self, kind: str, title: str, url: str) -> str:
        title = _clean_title(title)
        game_emoji, game_name = _detect_game(title)
        cat_emoji, cat_name = _detect_category(title)

        # если заголовок англ — сделаем псевдо-ru
        title_ru = _pseudo_translate_en_ru(title)

        # укоротим слишком длинное
        if len(title_ru) > 110:
            title_ru = title_ru[:107].rstrip() + "…"

        summary = _make_summary(title_ru)

        # вид поста
        header = f"{cat_emoji}{game_emoji} {game_name} — {title_ru}"
        body = f"{summary}\n{url}"
        return f"{header}\n{body}"
