import argparse
import json
from dataclasses import asdict
from pathlib import Path

from duolingo_anki.scraper import scrape


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_scrape(args: argparse.Namespace) -> None:
    write_json(args.output, [asdict(word) for word in scrape()])


def main() -> None:
    parser = argparse.ArgumentParser(prog="duolingo-anki")
    commands = parser.add_subparsers(required=True)

    scrape_parser = commands.add_parser("scrape", help="scrape vocabulary from the Duolingo wiki")
    scrape_parser.add_argument("--output", type=Path, default=Path("words.json"))
    scrape_parser.set_defaults(run=run_scrape)

    args = parser.parse_args()
    args.run(args)
