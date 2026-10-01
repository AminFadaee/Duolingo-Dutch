import argparse
import json
import sys
from collections import defaultdict
from dataclasses import asdict, is_dataclass
from pathlib import Path

DATA = Path("data")
CACHE = Path(".cache")
BUILD = Path("build")


def compact(value: object) -> object:
    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, dict):
        return {key: compact(item) for key, item in value.items() if item is not None and item != []}
    if isinstance(value, list):
        return [compact(item) for item in value]
    return value


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(compact(data), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_words(path: Path) -> list:
    from duolingo_anki.scraper import Word

    return [Word(**word) for word in json.loads(path.read_text(encoding="utf-8"))]


def report(title: str, items: list) -> None:
    print(f"{title}: {len(items)}", file=sys.stderr)
    for item in items:
        print(f"  {item}", file=sys.stderr)


def run_scrape(args: argparse.Namespace) -> None:
    from duolingo_anki.scraper import scrape

    write_json(args.output, scrape())


def run_lexicon(args: argparse.Namespace) -> None:
    from duolingo_anki.lexicon import WIKTIONARY_URL, build_lexicon
    from duolingo_anki.sources import download

    source = download(WIKTIONARY_URL, args.cache_dir)
    lexicon = build_lexicon(read_words(args.words), source.path)
    write_json(args.output, {
        "sources": {"wiktionary": {"url": source.url, "last_modified": source.last_modified}},
        "entries": lexicon.entries,
    })
    report("Not in Wiktionary", lexicon.missing)
    report("Chosen entry shares no meaning with the translation", lexicon.unmatched_meaning)
    report("Article differs from Wiktionary", [f"{dutch} (Wiktionary: {article})" for dutch, article in lexicon.article_conflicts])


def run_sentences(args: argparse.Namespace) -> None:
    from duolingo_anki.english import Meaning
    from duolingo_anki.opus import CORPORA, latest_url
    from duolingo_anki.sentences import find_examples
    from duolingo_anki.sources import download
    from duolingo_anki.tatoeba import URLS as TATOEBA_URLS
    from duolingo_anki.tatoeba import Files, Tatoeba
    from duolingo_anki.translation import MODEL, REVISION, Translator
    from duolingo_anki.wikis import Wikis

    lexicon = json.loads(args.lexicon.read_text(encoding="utf-8"))["entries"]
    translations = defaultdict(list)
    for word in read_words(args.words):
        translations[word.dutch].append(word.translation)
    meanings = {dutch: Meaning.of(texts) for dutch, texts in translations.items()}
    downloads = [download(url, args.cache_dir) for url in TATOEBA_URLS]
    corpora = {name: download(latest_url(name), args.cache_dir, f"opus-{name}-en-nl.zip") for name in CORPORA}
    examples = find_examples(
        lexicon,
        meanings,
        Tatoeba(Files(*(item.path for item in downloads))),
        {name: item.path for name, item in corpora.items()},
        Wikis(),
        Translator(),
    )
    write_json(args.output, {
        "sources": {
            "tatoeba": [{"url": item.url, "last_modified": item.last_modified} for item in downloads],
            "opus": [
                {"corpus": name, "url": item.url, "license": CORPORA[name], "last_modified": item.last_modified}
                for name, item in corpora.items()
            ],
            "wikis": {"nl.wiktionary.org": "CC-BY-SA 4.0", "nl.wikipedia.org": "CC-BY-SA 4.0"},
            "translation": {"model": MODEL, "revision": REVISION, "license": "Apache-2.0"},
        },
        "entries": [{"dutch": entry["dutch"], "example": examples[entry["dutch"]]} for entry in lexicon if entry["dutch"] in examples],
    })
    report("Dropped for lack of an example sentence", [entry["dutch"] for entry in lexicon if entry["dutch"] not in examples])


def run_audio(args: argparse.Namespace) -> None:
    from duolingo_anki.audio import MODEL as TTS_MODEL
    from duolingo_anki.audio import VOICES, Speaker, build_audio
    from duolingo_anki.cards import display_text

    entries = json.loads(args.sentences.read_text(encoding="utf-8"))["entries"]
    lexicon = {entry["dutch"]: entry.get("headwords", []) for entry in json.loads(args.lexicon.read_text(encoding="utf-8"))["entries"]}
    displayed = {entry["dutch"]: display_text(entry["dutch"], lexicon[entry["dutch"]]) for entry in entries}
    speaker = Speaker()
    write_json(args.output, {
        "sources": {"tts": {"engine": speaker.name, "model": TTS_MODEL, "voices": list(VOICES), "license": "OpenRAIL-M"}},
        "entries": build_audio(entries, displayed, args.audio_dir, speaker),
    })


def run_deck(args: argparse.Namespace) -> None:
    from duolingo_anki.deck import build_deck

    notes = build_deck(args.data_dir, args.build_dir, args.output)
    print(f"Wrote {notes} notes to {args.output}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(prog="duolingo-anki")
    commands = parser.add_subparsers(required=True)

    scrape_parser = commands.add_parser("scrape", help="scrape vocabulary from the Duolingo wiki")
    scrape_parser.add_argument("--output", type=Path, default=DATA / "words.json")
    scrape_parser.set_defaults(run=run_scrape)

    lexicon_parser = commands.add_parser("lexicon", help="look up forms and base words in Wiktionary")
    lexicon_parser.add_argument("--words", type=Path, default=DATA / "words.json")
    lexicon_parser.add_argument("--output", type=Path, default=DATA / "lexicon.json")
    lexicon_parser.add_argument("--cache-dir", type=Path, default=CACHE)
    lexicon_parser.set_defaults(run=run_lexicon)

    sentences_parser = commands.add_parser("sentences", help="pick example sentences from Tatoeba, OPUS and Dutch wikis")
    sentences_parser.add_argument("--words", type=Path, default=DATA / "words.json")
    sentences_parser.add_argument("--lexicon", type=Path, default=DATA / "lexicon.json")
    sentences_parser.add_argument("--output", type=Path, default=DATA / "sentences.json")
    sentences_parser.add_argument("--cache-dir", type=Path, default=CACHE)
    sentences_parser.set_defaults(run=run_sentences)

    audio_parser = commands.add_parser("audio", help="speak each word and its example sentence with Supertonic")
    audio_parser.add_argument("--sentences", type=Path, default=DATA / "sentences.json")
    audio_parser.add_argument("--lexicon", type=Path, default=DATA / "lexicon.json")
    audio_parser.add_argument("--output", type=Path, default=DATA / "audio.json")
    audio_parser.add_argument("--audio-dir", type=Path, default=DATA / "audio")
    audio_parser.set_defaults(run=run_audio)

    deck_parser = commands.add_parser("deck", help="build the Anki package from the committed data")
    deck_parser.add_argument("--data-dir", type=Path, default=DATA)
    deck_parser.add_argument("--build-dir", type=Path, default=BUILD)
    deck_parser.add_argument("--output", type=Path, default=BUILD / "duolingo_dutch.apkg")
    deck_parser.set_defaults(run=run_deck)

    args = parser.parse_args()
    args.run(args)
