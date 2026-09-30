import re
from dataclasses import dataclass, field

from duolingo_anki.english import Meaning
from pathlib import Path

from duolingo_anki.matching import FormMatch, Rule, build_rules, tokens
from duolingo_anki.opus import find_pairs
from duolingo_anki.tatoeba import Tatoeba

SENTENCE_END = re.compile(r"[.!?]+(?=\s|$)")
PREFERRED_LENGTH = range(4, 13)
MAX_LENGTH = 20


@dataclass(frozen=True)
class Example:
    text: str
    translation: str
    match: str
    source: str
    url: str | None = None
    translation_url: str | None = None
    authors: list[str] = field(default_factory=list)
    translated_by: str | None = None


@dataclass(frozen=True)
class Candidate:
    example: Example
    rule: Rule
    order: tuple


def single_sentence(text: str) -> bool:
    return len(SENTENCE_END.findall(text)) <= 1


def well_shaped(text: str) -> bool:
    return len(tokens(text)) in PREFERRED_LENGTH and single_sentence(text)


def too_long(text: str) -> bool:
    return len(tokens(text)) > MAX_LENGTH or not single_sentence(text)


def rank(candidate: Candidate, meaning: Meaning, vocabulary: set[str]) -> tuple:
    sentence_tokens = tokens(candidate.example.text)
    known = sum(token in vocabulary for token in sentence_tokens) / len(sentence_tokens)
    return (
        not meaning.carried_by(candidate.example.translation),
        too_long(candidate.example.text),
        candidate.rule.form,
        not well_shaped(candidate.example.text),
        -round(known, 3),
        len(sentence_tokens),
        candidate.order,
    )


def choose(candidates: list[Candidate], meaning: Meaning, vocabulary: set[str], strict: bool = False) -> Candidate | None:
    allowed = [
        candidate for candidate in candidates
        if meaning.carried_by(candidate.example.translation, strict)
        or not (strict or candidate.rule.form == FormMatch.LOOSE)
    ]
    return min(allowed, key=lambda candidate: rank(candidate, meaning, vocabulary), default=None)


def vocabulary(entries: list[dict]) -> set[str]:
    words = set()
    for entry in entries:
        words.update(tokens(entry["dutch"]))
        for headword in entry.get("headwords", []):
            for form in headword.get("forms", []):
                words.update(tokens(form))
    return words


def from_tatoeba(
    tatoeba: Tatoeba, rules: dict[str, list[Rule]], meanings: dict[str, Meaning], known: set[str]
) -> dict[str, Example]:
    matches = {text: tatoeba.matches(text_rules) for text, text_rules in rules.items()}
    tatoeba.add_indirect_translations({
        id_
        for found in matches.values()
        if not any(id_ in tatoeba.translations for id_ in found)
        for id_ in found
    })
    english = tatoeba.english({id_ for found in matches.values() for id_ in found})
    examples = {}
    for text, found in matches.items():
        candidates = []
        for id_, rule in found.items():
            if id_ not in english:
                continue
            dutch, translation = tatoeba.index.sentences[id_], english[id_]
            example = Example(
                text=dutch.text,
                translation=translation.text,
                match=rule.label,
                source="tatoeba",
                url=dutch.url,
                translation_url=translation.url,
                authors=list(dict.fromkeys(author for author in (dutch.author, translation.author) if author)),
            )
            candidates.append(Candidate(example, rule, (id_,)))
        if chosen := choose(candidates, meanings.get(text, Meaning()), known):
            examples[text] = chosen.example
    return examples


def needs_example(example: Example | None) -> bool:
    return example is None or too_long(example.text)


def improves(current: Example | None, new: Example) -> bool:
    return current is None or (too_long(current.text) and not too_long(new.text))


def from_opus(
    corpora: dict[str, Path],
    rules: dict[str, list[Rule]],
    meanings: dict[str, Meaning],
    known: set[str],
    examples: dict[str, Example],
) -> None:
    for name, path in corpora.items():
        pending = {text: text_rules for text, text_rules in rules.items() if needs_example(examples.get(text))}
        for text, pairs in find_pairs(path, pending).items():
            candidates = [
                Candidate(Example(pair.dutch, pair.english, rule.label, f"opus/{name}"), rule, (pair.line,))
                for pair, rule in pairs
            ]
            chosen = choose(candidates, meanings.get(text, Meaning()), known, strict=True)
            if chosen and improves(examples.get(text), chosen.example):
                examples[text] = chosen.example


def find_examples(
    lexicon: list[dict], meanings: dict[str, Meaning], tatoeba: Tatoeba, corpora: dict[str, Path]
) -> dict[str, Example]:
    rules = {entry["dutch"]: build_rules(entry["dutch"], entry.get("headwords", [])) for entry in lexicon}
    known = vocabulary(lexicon)
    examples = from_tatoeba(tatoeba, rules, meanings, known)
    from_opus(corpora, rules, meanings, known, examples)
    return examples
