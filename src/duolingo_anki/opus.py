import re
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import httpx

from duolingo_anki.english import looks_english
from duolingo_anki.matching import Rule, tokens
from duolingo_anki.sources import USER_AGENT

API_URL = "https://opus.nlpl.eu/opusapi"
CORPORA = {
    "wikimedia": "CC-BY-SA 4.0",
    "GlobalVoices": "CC-BY 3.0",
}
CLEAN = re.compile(r"^[A-Z\"'‘“].*[.!?\"'’”]$")
UNWANTED = re.compile(r"==|[()\[\]0-9]")
LENGTH = range(4, 21)
LENGTH_RATIO = (0.5, 2.0)


@dataclass(frozen=True)
class Pair:
    dutch: str
    english: str
    line: int


def latest_url(corpus: str) -> str:
    params = {"source": "en", "target": "nl", "corpus": corpus, "preprocessing": "moses", "version": "latest"}
    response = httpx.get(API_URL, params=params, headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=60)
    response.raise_for_status()
    return response.json()["corpora"][0]["url"]


def clean_pair(dutch: str, english: str, dutch_tokens: list[str]) -> bool:
    if len(dutch_tokens) not in LENGTH or not CLEAN.match(dutch) or not CLEAN.match(english):
        return False
    if UNWANTED.search(dutch) or UNWANTED.search(english) or not looks_english(english):
        return False
    ratio = len(dutch_tokens) / max(1, len(tokens(english)))
    return LENGTH_RATIO[0] <= ratio <= LENGTH_RATIO[1]


def read_lines(archive: zipfile.ZipFile, suffix: str):
    name = next(name for name in archive.namelist() if name.endswith(suffix))
    with archive.open(name) as file:
        for line in file:
            yield line.decode("utf-8").strip()


def find_pairs(path: Path, rules: dict[str, list[Rule]]) -> dict[str, list[tuple[Pair, Rule]]]:
    anchored = defaultdict(list)
    unanchored = []
    for text, text_rules in rules.items():
        for rule in text_rules:
            if rule.anchors:
                anchored[rule.anchors[0]].append((text, rule))
            else:
                unanchored.append((text, rule))
    found = defaultdict(list)
    with zipfile.ZipFile(path) as archive:
        pairs = zip(read_lines(archive, ".nl"), read_lines(archive, ".en"))
        for line, (dutch, english) in enumerate(pairs):
            dutch_tokens = tokens(dutch)
            if not clean_pair(dutch, english, dutch_tokens):
                continue
            possible = [item for token in set(dutch_tokens) for item in anchored.get(token, ())] + unanchored
            for text, rule in possible:
                if rule.matches(dutch_tokens):
                    found[text].append((Pair(dutch, english, line), rule))
    return found
