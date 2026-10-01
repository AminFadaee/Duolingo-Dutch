import hashlib
import html
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import genanki

from duolingo_anki.cards import (
    article_twins,
    display_text,
    forms_html,
    highlight,
    merged_translations,
    spoken_text,
    word_tags,
)

DECK_NAME = "Duolingo Dutch"
MODEL_ID = 1_759_241_381
MEDIA_PREFIX = "dd"
REPOSITORY_URL = "https://github.com/AminFadaee/Duolingo-Dutch"
FIELDS = (
    "Id",
    "Dutch",
    "English",
    "Forms",
    "WordAudio",
    "Sentence",
    "SentenceTranslation",
    "SentenceAudio",
    "Source",
    "TypeAnswer",
)
SOURCE_NAMES = {
    "tatoeba": "Tatoeba",
    "opus/wikimedia": "Wikimedia (OPUS)",
    "opus/GlobalVoices": "Global Voices (OPUS)",
    "nl.wiktionary": "Wiktionary",
    "nl.wikipedia": "Wikipedia",
}

SENTENCE_PLAYER = (
    '<button class="play" onclick="var a = this.nextElementSibling; a.currentTime = 0; a.play()">▶</button>'
    '<audio src="{{SentenceAudio}}" preload="none"></audio>'
)
SENTENCE_LINE = f'<div class="sentence">{SENTENCE_PLAYER}<span>{{{{Sentence}}}}</span></div>'
SENTENCE_DETAILS = '<div class="translation">{{SentenceTranslation}}</div><div class="source">{{Source}}</div>'
SENTENCE = f"{SENTENCE_LINE}{SENTENCE_DETAILS}"
DUTCH = '<div class="dutch">{{Dutch}}</div>'
ENGLISH = '<div class="english">{{English}}</div>'
FORMS = '{{#Forms}}<div class="forms">{{Forms}}</div>{{/Forms}}'
DIVIDER = '<hr id="answer">'
TYPE_ANSWER = '{{#TypeAnswer}}<div class="typed">{{type:TypeAnswer}}</div>{{/TypeAnswer}}'


@dataclass(frozen=True)
class Template:
    name: str
    front: str
    back: str

    def as_genanki(self) -> dict:
        return {"name": self.name, "qfmt": self.front, "afmt": self.back}


TEMPLATES = (
    Template(
        "Dutch to English",
        f"{DUTCH}{{{{WordAudio}}}}{SENTENCE_LINE}",
        f"{{{{FrontSide}}}}{DIVIDER}{ENGLISH}{FORMS}{SENTENCE_DETAILS}",
    ),
    Template(
        "English to Dutch",
        f"{ENGLISH}{TYPE_ANSWER}",
        f"{{{{FrontSide}}}}{DIVIDER}{DUTCH}{{{{WordAudio}}}}{FORMS}{SENTENCE}",
    ),
    Template(
        "Listening",
        f'{{{{#WordAudio}}}}<div class="prompt">Listen</div>{{{{WordAudio}}}}{TYPE_ANSWER}'
        f'<div class="hint">{SENTENCE_PLAYER} sentence</div>{{{{/WordAudio}}}}',
        f"{{{{FrontSide}}}}{DIVIDER}{DUTCH}{ENGLISH}{FORMS}{SENTENCE}",
    ),
)

CSS = """
.card {
  --text: #1d1d1f; --muted: #8a8a8e; --accent: #0a66c2; --line: #d8d8dd; --soft: #505055; --background: #fdfdfd;
  font-family: -apple-system, "Segoe UI", Roboto, sans-serif; text-align: center;
  color: var(--text); background: var(--background); padding: 12px 8px;
}
.nightMode.card, .night_mode .card, .card.night_mode {
  --text: #e8e8ea; --muted: #9a9aa0; --accent: #6cb2ff; --line: #3a3a3f; --soft: #bdbdc2; --background: #1e1e20;
}
.dutch { font-size: 32px; font-weight: 600; }
.english { font-size: 26px; color: var(--accent); font-weight: 600; margin: 6px 0; }
.forms { font-size: 16px; color: var(--soft); margin-top: 6px; }
.prompt { font-size: 14px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); margin-bottom: 8px; }
hr#answer { border: none; border-top: 1px solid var(--line); width: min(60%, 360px); margin: 16px auto; }
.sentence { font-size: 20px; margin: 22px auto 4px; max-width: 32em; line-height: 1.45; }
.sentence b { color: var(--accent); }
.translation { font-size: 16px; color: var(--soft); max-width: 32em; margin: 0 auto; }
.english + .translation, .forms + .translation { margin-top: 22px; }
.source { font-size: 12px; color: var(--muted); margin-top: 14px; }
.source a { color: var(--muted); }
.hint { font-size: 14px; color: var(--muted); margin-top: 18px; }
.typed { margin-top: 16px; }
input#typeans {
  width: min(90%, 420px); font-size: 22px; padding: 6px 10px; text-align: center;
  border: 1px solid var(--line); border-radius: 8px; background: transparent; color: var(--text);
}
code#typeans { font-family: inherit; font-size: 22px; }
button.play {
  font-size: 14px; line-height: 1; padding: 6px 9px; margin-right: 8px; border-radius: 50%;
  border: 1px solid var(--line); background: transparent; color: var(--accent); cursor: pointer; vertical-align: 2px;
}
"""


def stable_id(name: str) -> int:
    return int(hashlib.sha256(name.encode()).hexdigest()[:12], 16) % (1 << 40) + (1 << 30)


def description() -> str:
    return f"""
<p><b>{DECK_NAME}</b>: the vocabulary of Duolingo's Dutch course, each word with its forms, a real example sentence
and Dutch audio.</p>
<p>Three cards per word: Dutch to English, English to Dutch and listening. Notes are tagged with their Duolingo skill
(<code>DD::Basics_1</code>) and word type (<code>DD::Noun</code>); use a filtered deck to study one tag, and suspend
cards rather than deleting them, because deleted cards come back when you import an update. Sentences tagged
<code>DD::Machine_translated</code> have a machine translation.</p>
<p>Word list from the Duolingo wiki; forms from Wiktionary; sentences from Tatoeba, OPUS, Wiktionary and Wikipedia;
translations of untranslated sentences by Opus-MT; audio by Supertonic. Shared under CC BY-SA 4.0.</p>
<p>Source code, data and new releases: <a href="{REPOSITORY_URL}">{REPOSITORY_URL.removeprefix("https://")}</a>.
Built {date.today().isoformat()}.</p>
"""


def source_html(example: dict) -> str:
    name = html.escape(SOURCE_NAMES.get(example["source"], example["source"]))
    label = f'<a href="{html.escape(example["url"])}">{name}</a>' if example.get("url") else name
    if example.get("translated_by"):
        label += " · machine translation"
    return label


class MissingMediaError(FileNotFoundError):
    pass


class MediaLibrary:
    def __init__(self, audio_dir: Path, build_dir: Path):
        self.audio_dir = audio_dir
        self.build_dir = build_dir
        self.files: set[str] = set()
        self.missing: list[Path] = []

    def copy(self, file: str, name: str) -> str:
        source = self.audio_dir / file
        if not source.exists():
            self.missing.append(source)
            return ""
        target = self.build_dir / name
        if not target.exists():
            self.build_dir.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
        self.files.add(str(target))
        return name

    def sound(self, clip: dict | None) -> str:
        return f"[sound:{name}]" if clip and (name := self.copy(clip["file"], f"{MEDIA_PREFIX}-{clip['file']}")) else ""

    def button_source(self, clip: dict) -> str:
        return self.copy(clip["file"], f"_{MEDIA_PREFIX}-{clip['file']}")


@dataclass(frozen=True)
class Entry:
    dutch: str
    translations: list[str]
    skills: list[str]
    position: int


def entries(words: list[dict]) -> dict[str, Entry]:
    translations, skills, positions = defaultdict(list), defaultdict(list), {}
    for word in words:
        positions.setdefault(word["dutch"], len(positions))
        translations[word["dutch"]].append(word["translation"])
        skills[word["dutch"]].append(word["tag"])
    twins = article_twins(translations)
    folded = defaultdict(list)
    for bare, dutch in twins.items():
        folded[dutch].append(bare)
    result = {}
    for dutch, position in positions.items():
        if dutch in twins:
            continue
        glosses, tags, first = list(dict.fromkeys(translations[dutch])), skills[dutch], position
        for bare in folded[dutch]:
            glosses = merged_translations(glosses, translations[bare])
            tags = tags + skills[bare]
            first = min(first, positions[bare])
        result[dutch] = Entry(dutch, glosses, list(dict.fromkeys(tags)), first)
    return result


def build_deck(data_dir: Path, build_dir: Path, output: Path) -> int:
    read = lambda name: json.loads((data_dir / name).read_text(encoding="utf-8"))
    words = entries(read("words.json"))
    lexicon = {entry["dutch"]: entry.get("headwords", []) for entry in read("lexicon.json")["entries"]}
    audio = {entry["dutch"]: entry for entry in read("audio.json")["entries"]}
    media = MediaLibrary(data_dir / "audio", build_dir / "media")
    model = genanki.Model(
        MODEL_ID,
        DECK_NAME,
        fields=[{"name": field} for field in FIELDS],
        templates=[template.as_genanki() for template in TEMPLATES],
        css=CSS,
        sort_field_index=1,
    )
    deck = genanki.Deck(stable_id(DECK_NAME), DECK_NAME, description())
    examples = sorted(read("sentences.json")["entries"], key=lambda entry: words[entry["dutch"]].position)
    for item in examples:
        entry, example, headwords, clips = words[item["dutch"]], item["example"], lexicon[item["dutch"]], audio[item["dutch"]]
        values = {
            "Id": entry.dutch,
            "Dutch": html.escape(display_text(entry.dutch, headwords)),
            "English": html.escape("; ".join(entry.translations)),
            "Forms": forms_html(headwords),
            "WordAudio": media.sound(clips.get("word")),
            "Sentence": highlight(example["text"], example["match"]),
            "SentenceTranslation": html.escape(example["translation"]),
            "SentenceAudio": media.button_source(clips["sentence"]),
            "Source": source_html(example),
            "TypeAnswer": html.escape(spoken_text(display_text(entry.dutch, headwords)) or ""),
        }
        tags = word_tags(entry.skills, headwords, bool(example.get("translated_by")))
        deck.add_note(genanki.Note(
            model=model,
            fields=[values[field] for field in FIELDS],
            tags=tags,
            guid=genanki.guid_for(entry.dutch),
            due=entry.position,
        ))
    if media.missing:
        raise MissingMediaError(f"{len(media.missing)} audio files are missing, e.g. {media.missing[0]}")
    output.parent.mkdir(parents=True, exist_ok=True)
    genanki.Package(deck, media_files=sorted(media.files)).write_to_file(str(output))
    return len(deck.notes)
