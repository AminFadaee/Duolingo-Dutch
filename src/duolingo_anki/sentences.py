import bz2
import re
import tarfile
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path

from duolingo_anki.english import shared_words

TATOEBA = "https://downloads.tatoeba.org/exports"
DUTCH_URL = f"{TATOEBA}/per_language/nld/nld_sentences_detailed.tsv.bz2"
ENGLISH_URL = f"{TATOEBA}/per_language/eng/eng_sentences_detailed.tsv.bz2"
DUTCH_ENGLISH_LINKS_URL = f"{TATOEBA}/per_language/nld/nld-eng_links.tsv.bz2"
ALL_LINKS_URL = f"{TATOEBA}/links.tar.bz2"
TOKEN = re.compile(r"[\w'-]+")
SENTENCE_END = re.compile(r"[.!?]+(?=\s|$)")
PREFERRED_LENGTH = range(4, 13)


def tokens(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


@dataclass(frozen=True)
class Sentence:
    id: int
    text: str
    author: str


@dataclass(frozen=True)
class Example:
    text: str
    translation: str
    match: str
    tatoeba_id: int
    translation_id: int
    authors: list[str]
    via_id: int | None = None


class FormMatch(IntEnum):
    SPLIT = 0
    TAUGHT = 1
    OTHER = 2


@dataclass(frozen=True)
class Candidate:
    sentence: Sentence
    match: str
    form: FormMatch


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

    def find(self, form: str, particle: str | None) -> set[int]:
        form_tokens = tokens(form)
        if not form_tokens:
            return set()
        pool = set.intersection(*(self.by_token.get(token, set()) for token in form_tokens))
        split = particle is not None and len(form_tokens) > 1 and form_tokens[-1] == particle
        match = self.contains_split if split else self.contains
        return {id_ for id_ in pool if match(self.tokens[id_], form_tokens)}

    @staticmethod
    def contains(sentence: list[str], phrase: list[str]) -> bool:
        return any(sentence[i:i + len(phrase)] == phrase for i in range(len(sentence) - len(phrase) + 1))

    @staticmethod
    def contains_split(sentence: list[str], form: list[str]) -> bool:
        head, particle = form[:-1], form[-1]
        return any(
            sentence[i:i + len(head)] == head and particle in sentence[i + len(head):]
            for i in range(len(sentence) - len(head) + 1)
        )


def candidates(index: SentenceIndex, headwords: list[dict]) -> list[Candidate]:
    found = {}
    for headword in headwords:
        particle = headword.get("verb", {}).get("particle")
        for form in dict.fromkeys([headword["word"], *headword.get("forms", [])]):
            if particle is not None and form.endswith(f" {particle}"):
                match = FormMatch.SPLIT
            elif form.lower() == headword["word"].lower():
                match = FormMatch.TAUGHT
            else:
                match = FormMatch.OTHER
            for id_ in index.find(form, particle):
                if id_ not in found or match < found[id_].form:
                    found[id_] = Candidate(index.sentences[id_], form, match)
    return list(found.values())


def rank(candidate: Candidate, translation: str, meaning: set[str], index: SentenceIndex, vocabulary: set[str]) -> tuple:
    sentence_tokens = index.tokens[candidate.sentence.id]
    known = sum(token in vocabulary for token in sentence_tokens) / len(sentence_tokens)
    well_shaped = len(sentence_tokens) in PREFERRED_LENGTH and len(SENTENCE_END.findall(candidate.sentence.text)) <= 1
    return (
        bool(meaning) and not shared_words(meaning, translation),
        candidate.form,
        not well_shaped,
        -round(known, 3),
        len(sentence_tokens),
        candidate.sentence.id,
    )


def vocabulary(entries: list[dict]) -> set[str]:
    words = set()
    for entry in entries:
        words.update(tokens(entry["dutch"]))
        for headword in entry.get("headwords", []):
            for form in headword.get("forms", []):
                words.update(tokens(form))
    return words


@dataclass
class Sources:
    dutch: Path
    english: Path
    dutch_english_links: Path
    all_links: Path


def direct_translations(path: Path, dutch_ids: set[int], english_ids: set[int]) -> dict[int, tuple[int, None]]:
    with bz2.open(path, "rt") as file:
        links = read_pairs(file, dutch_ids)
    return {
        dutch_id: (min(targets), None)
        for dutch_id, all_targets in links.items()
        if (targets := [target for target in all_targets if target in english_ids])
    }


def indirect_translations(path: Path, dutch_ids: set[int], english_ids: set[int]) -> dict[int, tuple[int, int]]:
    pivots = read_all_links(path, dutch_ids)
    pivot_targets = read_all_links(path, {pivot for ids in pivots.values() for pivot in ids})
    translations = {}
    for dutch_id, pivot_ids in pivots.items():
        for pivot_id in sorted(pivot_ids):
            targets = [target for target in pivot_targets.get(pivot_id, []) if target in english_ids]
            if targets:
                translations[dutch_id] = (min(targets), pivot_id)
                break
    return translations


def find_examples(lexicon: list[dict], meanings: dict[str, set[str]], sources: Sources) -> dict[str, Example]:
    dutch = read_sentences(sources.dutch)
    index = SentenceIndex(dutch)
    known = vocabulary(lexicon)
    options = {entry["dutch"]: candidates(index, entry.get("headwords", [])) for entry in lexicon}

    english_ids = read_sentence_ids(sources.english)
    translations = direct_translations(sources.dutch_english_links, set(dutch), english_ids)
    untranslated = {
        option.sentence.id
        for found in options.values()
        if not any(option.sentence.id in translations for option in found)
        for option in found
    }
    translations |= indirect_translations(sources.all_links, untranslated, english_ids)
    wanted = {
        translations[option.sentence.id][0]
        for found in options.values()
        for option in found
        if option.sentence.id in translations
    }
    english = read_sentences(sources.english, wanted)

    examples = {}
    for text, found in options.items():
        translated = [option for option in found if option.sentence.id in translations]
        if not translated:
            continue
        english_of = {option.sentence.id: english[translations[option.sentence.id][0]] for option in translated}
        chosen = min(
            translated,
            key=lambda option: rank(option, english_of[option.sentence.id].text, meanings.get(text, set()), index, known),
        )
        translation = english_of[chosen.sentence.id]
        examples[text] = Example(
            text=chosen.sentence.text,
            translation=translation.text,
            match=chosen.match,
            tatoeba_id=chosen.sentence.id,
            translation_id=translation.id,
            authors=list(dict.fromkeys(author for author in (chosen.sentence.author, translation.author) if author)),
            via_id=translations[chosen.sentence.id][1],
        )
    return examples
