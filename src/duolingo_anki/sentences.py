import math
import re
from collections import defaultdict
from dataclasses import dataclass, field, replace
from difflib import SequenceMatcher
from pathlib import Path

from duolingo_anki.english import Meaning

from duolingo_anki.matching import ARTICLE_BEFORE_PHRASE, FormMatch, Rule, build_rules, tokens
from duolingo_anki.opus import clean_sentence, find_pairs
from duolingo_anki.tatoeba import Tatoeba
from duolingo_anki.translation import Translator
from duolingo_anki.wikis import DutchSentence, Wikis

SENTENCE_END = re.compile(r"[.!?]+(?=\s|$)")
PREFERRED_LENGTH = range(4, 13)
MAX_LENGTH = 20
TRANSLATED_PER_ENTRY = 3
REFLEXIVE = "zich "
REFLEXIVE_PRONOUNS = {"me", "mij", "je", "jou", "zich", "ons", "u", "mezelf", "jezelf", "zichzelf", "onszelf", "uzelf"}
SUBJECT_PRONOUNS = {"ik", "jij", "je", "hij", "zij", "ze", "het", "wij", "we", "jullie", "u", "men", "er"}


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


@dataclass(frozen=True)
class Target:
    meaning: Meaning = Meaning()
    position: int = 0
    reflexive: bool = False
    infinitives: frozenset[str] = frozenset()

    @classmethod
    def of(cls, entry: dict, meaning: Meaning, position: int) -> "Target":
        infinitives = frozenset(
            headword["verb"]["infinitive"].lower() for headword in entry.get("headwords", []) if headword.get("verb")
        )
        return cls(meaning, position, entry["dutch"].startswith(REFLEXIVE), infinitives)

    def misfit(self, sentence_tokens: list[str]) -> bool:
        if self.reflexive and not REFLEXIVE_PRONOUNS & set(sentence_tokens):
            return True
        return len(sentence_tokens) > 1 and sentence_tokens[0] in self.infinitives and sentence_tokens[1] not in SUBJECT_PRONOUNS


class Vocabulary:
    def __init__(self, entries: list[dict], positions: dict[str, int]):
        self.introduced = {}
        for entry in sorted(entries, key=lambda entry: positions[entry["dutch"]]):
            for token in entry_tokens(entry):
                self.introduced.setdefault(token, positions[entry["dutch"]])

    def known(self, sentence_tokens: list[str], position: int) -> float:
        return sum(self.introduced.get(token, math.inf) <= position for token in sentence_tokens) / len(sentence_tokens)


def entry_tokens(entry: dict) -> set[str]:
    words = set(tokens(entry["dutch"]))
    for headword in entry.get("headwords", []):
        for form in headword.get("forms", []):
            words.update(tokens(form))
    return words


def single_sentence(text: str) -> bool:
    return len(SENTENCE_END.findall(text)) <= 1


def well_shaped(text: str) -> bool:
    return len(tokens(text)) in PREFERRED_LENGTH and single_sentence(text)


def too_long(text: str) -> bool:
    return len(tokens(text)) > MAX_LENGTH or not single_sentence(text)


TIER = 3


def rank(candidate: Candidate, target: Target, vocabulary: Vocabulary) -> tuple:
    sentence_tokens = tokens(candidate.example.text)
    return (
        not target.meaning.carried_by(candidate.example.translation),
        target.misfit(sentence_tokens),
        too_long(candidate.example.text),
        candidate.rule.form,
        not well_shaped(candidate.example.text),
        -round(vocabulary.known(sentence_tokens, target.position), 3),
        len(sentence_tokens),
        candidate.order,
    )


def best_tier(candidates: list[Candidate], target: Target, vocabulary: Vocabulary, strict: bool = False) -> list[Candidate]:
    scored = sorted(
        (
            (rank(candidate, target, vocabulary), candidate)
            for candidate in candidates
            if target.meaning.carried_by(candidate.example.translation, strict)
            or not (strict or candidate.rule.form == FormMatch.LOOSE)
        ),
        key=lambda pair: pair[0],
    )
    return [candidate for key, candidate in scored if key[:TIER] == scored[0][0][:TIER]]


def choose(
    candidates: list[Candidate],
    target: Target,
    vocabulary: Vocabulary,
    strict: bool = False,
    used: set[str] = frozenset(),
) -> Candidate | None:
    tier = best_tier(candidates, target, vocabulary, strict)
    return next((candidate for candidate in tier if candidate.example.text not in used), tier[0] if tier else None)


def distinct(tiers: dict[str, list[Candidate]], targets: dict[str, Target]) -> dict[str, Candidate]:
    choice = {text: 0 for text, tier in tiers.items() if tier}
    settled = set()
    moved = True
    while moved:
        moved = False
        holders = defaultdict(list)
        for text, index in choice.items():
            holders[tiers[text][index].example.text].append(text)
        for claimants in list(holders.values()):
            if len(claimants) < 2:
                continue
            winner = min(claimants, key=lambda text: (
                tiers[text][choice[text]].rule.form, len(tiers[text]), targets[text].position,
            ))
            for text in claimants:
                if text == winner or text in settled:
                    continue
                free = next(
                    (index for index in range(choice[text] + 1, len(tiers[text])) if tiers[text][index].example.text not in holders),
                    None,
                )
                if free is None:
                    settled.add(text)
                else:
                    choice[text], moved = free, True
    return {text: tiers[text][index] for text, index in choice.items()}


def similarity(first: str, second: str) -> float:
    return SequenceMatcher(None, first.lower(), second.lower()).ratio()


def closest_to_machine(options: list, machine: str, meaning: Meaning):
    return min(options, key=lambda option: (not meaning.carried_by(option.text), -similarity(option.text, machine), option.id))


def from_tatoeba(
    tatoeba: Tatoeba,
    rules: dict[str, list[Rule]],
    targets: dict[str, Target],
    vocabulary: Vocabulary,
    translator: Translator,
) -> dict[str, Example]:
    matches = {text: tatoeba.matches(text_rules) for text, text_rules in rules.items()}
    tatoeba.add_indirect_translations({
        id_
        for found in matches.values()
        if not any(id_ in tatoeba.translations for id_ in found)
        for id_ in found
    })
    english = tatoeba.english({id_ for found in matches.values() for id_ in found})
    tiers = {}
    for text, found in matches.items():
        meaning, candidates = targets[text].meaning, []
        for id_, rule in found.items():
            if id_ not in english:
                continue
            dutch = tatoeba.index.sentences[id_]
            translation = next((option for option in english[id_] if meaning.carried_by(option.text)), english[id_][0])
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
        tiers[text] = best_tier(candidates, targets[text], vocabulary)
    chosen = distinct(tiers, targets)
    examples = {text: candidate.example for text, candidate in chosen.items()}
    chosen_ids = {text: candidate.order[0] for text, candidate in chosen.items()}
    ambiguous = [text for text, id_ in chosen_ids.items() if len(english[id_]) > 1]
    machine = translator.translate([examples[text].text for text in ambiguous])
    for text, machine_translation in zip(ambiguous, machine):
        best = closest_to_machine(english[chosen_ids[text]], machine_translation, targets[text].meaning)
        examples[text] = replace(examples[text], translation=best.text, translation_url=best.url, authors=list(dict.fromkeys(
            author for author in (tatoeba.index.sentences[chosen_ids[text]].author, best.author) if author
        )))
    return examples


def quality(example: Example, target: Target) -> tuple[bool, ...]:
    carried, shaped = target.meaning.carried_by(example.translation), well_shaped(example.text)
    return not target.misfit(tokens(example.text)), carried and shaped, shaped, not too_long(example.text), carried


def needs_example(example: Example | None, target: Target) -> bool:
    return (
        example is None
        or too_long(example.text)
        or not target.meaning.carried_by(example.translation)
        or target.misfit(tokens(example.text))
    )


def improves(current: Example | None, new: Example, target: Target) -> bool:
    return current is None or quality(new, target) > quality(current, target)


def taken_by_others(examples: dict[str, Example], text: str) -> set[str]:
    return {example.text for other, example in examples.items() if other != text}


def from_opus(
    corpora: dict[str, Path],
    rules: dict[str, list[Rule]],
    targets: dict[str, Target],
    vocabulary: Vocabulary,
    examples: dict[str, Example],
) -> None:
    for name, path in corpora.items():
        pending = {text: text_rules for text, text_rules in rules.items() if needs_example(examples.get(text), targets[text])}
        for text, pairs in find_pairs(path, pending).items():
            candidates = [
                Candidate(Example(pair.dutch, pair.english, rule.label, f"opus/{name}"), rule, (pair.line,))
                for pair, rule in pairs
            ]
            chosen = choose(candidates, targets[text], vocabulary, strict=True, used=taken_by_others(examples, text))
            if chosen and improves(examples.get(text), chosen.example, targets[text]):
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
    targets: dict[str, Target],
    vocabulary: Vocabulary,
    examples: dict[str, Example],
    relaxed: bool = False,
) -> None:
    shortlists = {}
    for text, text_rules in rules.items():
        if needs_example(examples.get(text), targets[text]):
            found = dutch_candidates(tatoeba, wikis, text_rules, headwords[text], relaxed)
            untranslated = replace(targets[text], meaning=Meaning())
            shortlists[text] = sorted(found, key=lambda candidate: rank(candidate, untranslated, vocabulary))[:TRANSLATED_PER_ENTRY]
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
        chosen = choose(translated, targets[text], vocabulary, used=taken_by_others(examples, text))
        if chosen and improves(examples.get(text), chosen.example, targets[text]):
            examples[text] = chosen.example


def find_examples(
    lexicon: list[dict],
    meanings: dict[str, Meaning],
    positions: dict[str, int],
    tatoeba: Tatoeba,
    corpora: dict[str, Path],
    wikis: Wikis,
    translator: Translator,
) -> dict[str, Example]:
    rules = {entry["dutch"]: build_rules(entry["dutch"], entry.get("headwords", [])) for entry in lexicon}
    headwords = {entry["dutch"]: entry.get("headwords", []) for entry in lexicon}
    targets = {
        entry["dutch"]: Target.of(entry, meanings.get(entry["dutch"], Meaning()), positions[entry["dutch"]])
        for entry in lexicon
    }
    vocabulary = Vocabulary(lexicon, positions)
    examples = from_tatoeba(tatoeba, rules, targets, vocabulary, translator)
    from_opus(corpora, rules, targets, vocabulary, examples)
    for relaxed in (False, True):
        from_dutch_sources(tatoeba, wikis, translator, rules, headwords, targets, vocabulary, examples, relaxed)
    return examples
