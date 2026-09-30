import bz2
import tarfile
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from duolingo_anki.matching import Rule, tokens

EXPORTS = "https://downloads.tatoeba.org/exports"
DUTCH_URL = f"{EXPORTS}/per_language/nld/nld_sentences_detailed.tsv.bz2"
ENGLISH_URL = f"{EXPORTS}/per_language/eng/eng_sentences_detailed.tsv.bz2"
DUTCH_ENGLISH_LINKS_URL = f"{EXPORTS}/per_language/nld/nld-eng_links.tsv.bz2"
ALL_LINKS_URL = f"{EXPORTS}/links.tar.bz2"
URLS = (DUTCH_URL, ENGLISH_URL, DUTCH_ENGLISH_LINKS_URL, ALL_LINKS_URL)
SENTENCE_PAGE = "https://tatoeba.org/en/sentences/show/{}"


@dataclass(frozen=True)
class Sentence:
    id: int
    text: str
    author: str

    @property
    def url(self) -> str:
        return SENTENCE_PAGE.format(self.id)


@dataclass(frozen=True)
class Files:
    dutch: Path
    english: Path
    dutch_english_links: Path
    all_links: Path


def read_sentences(path: Path, wanted: set[int] | None = None) -> dict[int, Sentence]:
    sentences = {}
    with bz2.open(path, "rt", encoding="utf-8") as file:
        for line in file:
            id_, _, text, author, *_ = line.rstrip("\n").split("\t")
            if wanted is None or int(id_) in wanted:
                sentences[int(id_)] = Sentence(int(id_), text, author if author != "\\N" else "")
    return sentences


def read_sentence_ids(path: Path) -> set[int]:
    with bz2.open(path, "rt", encoding="utf-8") as file:
        return {int(line.split("\t", 1)[0]) for line in file}


def read_pairs(lines: Iterator[str], sources: set[int]) -> dict[int, list[int]]:
    pairs = defaultdict(list)
    for line in lines:
        source, target = line.split("\t")
        if int(source) in sources:
            pairs[int(source)].append(int(target))
    return pairs


def read_all_links(path: Path, sources: set[int]) -> dict[int, list[int]]:
    with tarfile.open(path, "r:bz2") as archive:
        member = next(member for member in archive if member.name.endswith("links.csv"))
        with archive.extractfile(member) as file:
            return read_pairs((line.decode() for line in file), sources)


class SentenceIndex:
    def __init__(self, sentences: dict[int, Sentence]):
        self.sentences = sentences
        self.tokens = {id_: tokens(sentence.text) for id_, sentence in sentences.items()}
        self.by_token = defaultdict(set)
        for id_, sentence_tokens in self.tokens.items():
            for token in sentence_tokens:
                self.by_token[token].add(id_)

    def find(self, rule: Rule) -> set[int]:
        if rule.anchors:
            pool = set.intersection(*(self.by_token.get(token, set()) for token in rule.anchors))
        else:
            pool = self.sentences.keys()
        return {id_ for id_ in pool if rule.matches(self.tokens[id_])}


def direct_translations(path: Path, dutch_ids: set[int], english_ids: set[int]) -> dict[int, int]:
    with bz2.open(path, "rt") as file:
        links = read_pairs(file, dutch_ids)
    return {
        dutch_id: min(targets)
        for dutch_id, all_targets in links.items()
        if (targets := [target for target in all_targets if target in english_ids])
    }


def indirect_translations(path: Path, dutch_ids: set[int], english_ids: set[int]) -> dict[int, int]:
    pivots = read_all_links(path, dutch_ids)
    pivot_targets = read_all_links(path, {pivot for ids in pivots.values() for pivot in ids})
    translations = {}
    for dutch_id, pivot_ids in pivots.items():
        for pivot_id in sorted(pivot_ids):
            if targets := [target for target in pivot_targets.get(pivot_id, []) if target in english_ids]:
                translations[dutch_id] = min(targets)
                break
    return translations


class Tatoeba:
    def __init__(self, files: Files):
        self.files = files
        self.index = SentenceIndex(read_sentences(files.dutch))
        self.english_ids = read_sentence_ids(files.english)
        self.translations = direct_translations(files.dutch_english_links, set(self.index.sentences), self.english_ids)

    def matches(self, rules: list[Rule]) -> dict[int, Rule]:
        found = {}
        for rule in rules:
            for id_ in self.index.find(rule):
                if id_ not in found or rule.form < found[id_].form:
                    found[id_] = rule
        return found

    def add_indirect_translations(self, dutch_ids: set[int]) -> None:
        missing = dutch_ids - self.translations.keys()
        self.translations |= indirect_translations(self.files.all_links, missing, self.english_ids)

    def english(self, dutch_ids: set[int]) -> dict[int, Sentence]:
        wanted = {self.translations[id_] for id_ in dutch_ids if id_ in self.translations}
        english = read_sentences(self.files.english, wanted)
        return {id_: english[self.translations[id_]] for id_ in dutch_ids if id_ in self.translations}
