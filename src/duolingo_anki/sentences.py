import re
from dataclasses import dataclass, field, replace

from duolingo_anki.english import Meaning
from pathlib import Path

from duolingo_anki.matching import ARTICLE_BEFORE_PHRASE, FormMatch, Rule, build_rules, tokens
from duolingo_anki.opus import clean_sentence, find_pairs
from duolingo_anki.tatoeba import Tatoeba
from duolingo_anki.translation import Translator
from duolingo_anki.wikis import DutchSentence, Wikis

SENTENCE_END = re.compile(r"[.!?]+(?=\s|$)")
PREFERRED_LENGTH = range(4, 13)
MAX_LENGTH = 20
TRANSLATED_PER_ENTRY = 3


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


def matching_candidates(
    sentences: list[DutchSentence], rules: list[Rule], source: str, relaxed: bool
) -> list[Candidate]:
    candidates = []
    for position, sentence in enumerate(sentences):
        sentence_tokens = tokens(sentence.text)
        if not clean_sentence(sentence.text, sentence_tokens, relaxed):
            continue
        if rule := min((rule for rule in rules if rule.matches(sentence_tokens)), key=lambda r: r.form, default=None):
            candidates.append(Candidate(Example(sentence.text, "", rule.label, source, url=sentence.url), rule, (position,)))
    return candidates


def untranslated_tatoeba(tatoeba: Tatoeba, rules: list[Rule], relaxed: bool) -> list[Candidate]:
    candidates = []
    for id_, rule in tatoeba.matches(rules).items():
        sentence = tatoeba.index.sentences[id_]
        if id_ not in tatoeba.translations and clean_sentence(sentence.text, tatoeba.index.tokens[id_], relaxed):
            example = Example(sentence.text, "", rule.label, "tatoeba", url=sentence.url, authors=[sentence.author] if sentence.author else [])
            candidates.append(Candidate(example, rule, (id_,)))
    return candidates


def wiki_pages(headwords: list[dict]) -> list[str]:
    return list(dict.fromkeys(page for headword in headwords for page in (headword["word"], headword.get("lemma")) if page))


def dutch_candidates(
    tatoeba: Tatoeba, wikis: Wikis, rules: list[Rule], headwords: list[dict], relaxed: bool
) -> list[Candidate]:
    if candidates := untranslated_tatoeba(tatoeba, rules, relaxed):
        return candidates
    if not headwords:
        return []
    examples = [sentence for page in wiki_pages(headwords) for sentence in wikis.wiktionary_examples(page)]
    if candidates := matching_candidates(examples, rules, "nl.wiktionary", relaxed):
        return candidates
    phrase = ARTICLE_BEFORE_PHRASE.sub("", headwords[0]["word"])
    return matching_candidates(wikis.wikipedia_sentences(phrase), rules, "nl.wikipedia", relaxed)


def from_dutch_sources(
    tatoeba: Tatoeba,
    wikis: Wikis,
    translator: Translator,
    rules: dict[str, list[Rule]],
    headwords: dict[str, list[dict]],
    meanings: dict[str, Meaning],
    known: set[str],
    examples: dict[str, Example],
    relaxed: bool = False,
) -> None:
    shortlists = {}
    for text, text_rules in rules.items():
        if needs_example(examples.get(text)):
            found = dutch_candidates(tatoeba, wikis, text_rules, headwords[text], relaxed)
            shortlists[text] = sorted(found, key=lambda candidate: rank(candidate, Meaning(), known))[:TRANSLATED_PER_ENTRY]
    originals = [candidate.example.text for shortlist in shortlists.values() for candidate in shortlist]
    translations = iter(translator.translate(originals))
    for text, shortlist in shortlists.items():
        translated = [
            Candidate(
                replace(candidate.example, translation=next(translations), translated_by=translator.name),
                candidate.rule,
                candidate.order,
            )
            for candidate in shortlist
        ]
        chosen = choose(translated, meanings.get(text, Meaning()), known)
        if chosen and improves(examples.get(text), chosen.example):
            examples[text] = chosen.example


def find_examples(
    lexicon: list[dict],
    meanings: dict[str, Meaning],
    tatoeba: Tatoeba,
    corpora: dict[str, Path],
    wikis: Wikis,
    translator: Translator,
) -> dict[str, Example]:
    rules = {entry["dutch"]: build_rules(entry["dutch"], entry.get("headwords", [])) for entry in lexicon}
    headwords = {entry["dutch"]: entry.get("headwords", []) for entry in lexicon}
    known = vocabulary(lexicon)
    examples = from_tatoeba(tatoeba, rules, meanings, known)
    from_opus(corpora, rules, meanings, known, examples)
    for relaxed in (False, True):
        from_dutch_sources(tatoeba, wikis, translator, rules, headwords, meanings, known, examples, relaxed)
    return examples
