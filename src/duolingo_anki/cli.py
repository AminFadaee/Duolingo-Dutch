import argparse
import json
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path

from duolingo_anki.lexicon import WIKTIONARY_URL, build_lexicon
from duolingo_anki.scraper import Word, scrape
from duolingo_anki.sources import download


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


def read_words(path: Path) -> list[Word]:
    return [Word(**word) for word in json.loads(path.read_text(encoding="utf-8"))]


def report(title: str, items: list) -> None:
    print(f"{title}: {len(items)}", file=sys.stderr)
    for item in items:
        print(f"  {item}", file=sys.stderr)


def run_scrape(args: argparse.Namespace) -> None:
    write_json(args.output, scrape())


def run_lexicon(args: argparse.Namespace) -> None:
    source = download(WIKTIONARY_URL, args.cache_dir)
    lexicon = build_lexicon(read_words(args.words), source.path)
    write_json(args.output, {
        "sources": {"wiktionary": {"url": source.url, "last_modified": source.last_modified}},
        "entries": lexicon.entries,
    })
    report("Not in Wiktionary", lexicon.missing)
    report("Chosen entry shares no meaning with the translation", lexicon.unmatched_meaning)
    report("Article differs from Wiktionary", [f"{dutch} (Wiktionary: {article})" for dutch, article in lexicon.article_conflicts])


def main() -> None:
    parser = argparse.ArgumentParser(prog="duolingo-anki")
    commands = parser.add_subparsers(required=True)

    scrape_parser = commands.add_parser("scrape", help="scrape vocabulary from the Duolingo wiki")
    scrape_parser.add_argument("--output", type=Path, default=Path("words.json"))
    scrape_parser.set_defaults(run=run_scrape)

    lexicon_parser = commands.add_parser("lexicon", help="look up forms and base words in Wiktionary")
    lexicon_parser.add_argument("--words", type=Path, default=Path("words.json"))
    lexicon_parser.add_argument("--output", type=Path, default=Path("lexicon.json"))
    lexicon_parser.add_argument("--cache-dir", type=Path, default=Path(".cache"))
    lexicon_parser.set_defaults(run=run_lexicon)

    args = parser.parse_args()
    args.run(args)
