import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from duolingo_anki.english import content_words, shared_words
from duolingo_anki.scraper import Word

WIKTIONARY_URL = "https://kaikki.org/dictionary/Dutch/kaikki.org-dictionary-Dutch.jsonl"
SHARED_ARTICLE = re.compile(r"^(de|het)/(de|het)\s+", re.IGNORECASE)
ARTICLE = re.compile(r"^(de|het|'t)\s+(?=\S+$)", re.IGNORECASE)
NOTE = re.compile(r"\([^)]*\)")
REFLEXIVE = "zich "
PATTERN_MARKERS = ("+", "...", "…")
GENDER_ARTICLES = {"m": "de", "f": "de", "c": "de", "p": "de", "mf": "de", "mfbysense": "de", "n": "het"}
META_FORM_TAGS = {"table-tags", "inflection-template", "class"}
RARE_FORM_TAGS = {"archaic", "subjunctive", "imperative"}
NOUN_POS = {"noun", "name"}
HEBBEN_DEFAULT_TEMPLATES = {"nl-conj-wk", "nl-conj-wk-cht", "nl-conj-st"}


@dataclass(frozen=True)
class Part:
    word: str
    article: str | None
    lookups: tuple[str, ...]


@dataclass(frozen=True)
class Noun:
    article: str | None
    plural: str | None
    diminutive: str | None


@dataclass(frozen=True)
class Verb:
    infinitive: str
    past_singular: str | None
    past_plural: str | None
    past_participle: str | None
    auxiliary: str | None
    particle: str | None


@dataclass(frozen=True)
class Adjective:
    comparative: str | None
    superlative: str | None


@dataclass(frozen=True)
class Headword:
    word: str
    pos: str | None = None
    lemma: str | None = None
    noun: Noun | None = None
    verb: Verb | None = None
    adjective: Adjective | None = None
    forms: list[str] = field(default_factory=list)


def take_article(text: str) -> tuple[str | None, str]:
    match = ARTICLE.match(text)
    if not match:
        return None, text
    article = match.group(1).lower()
    return ("het" if article == "'t" else article), text[match.end():]


def split_headwords(dutch: str) -> list[Part]:
    if any(marker in dutch for marker in PATTERN_MARKERS):
        return []
    text = " ".join(NOTE.sub("", dutch).split())
    shared = None
    if match := SHARED_ARTICLE.match(text):
        shared, text = "de/het", text[match.end():]
    parts = []
    for chunk in text.split("/"):
        article, word = take_article(chunk.strip())
        shared = shared or article
        word = word.strip(" ?!.,")
        if word:
            parts.append(Part(word.replace("|", ""), article or shared, lookup_keys(word)))
    return parts


def lookup_keys(word: str) -> tuple[str, ...]:
    keys = [word.replace("|", ""), word.replace("|", " ")]
    keys += [key.removeprefix(REFLEXIVE) for key in keys]
    keys += [key.lower() for key in keys]
    return tuple(dict.fromkeys(keys))


def load_entries(path: Path, words: set[str]) -> dict[str, list[dict]]:
    entries = defaultdict(list)
    with path.open(encoding="utf-8") as file:
        for line in file:
            entry = json.loads(line)
            if entry["word"] in words:
                entries[entry["word"]].append(entry)
    return entries


def form_of_targets(entry: dict) -> list[str]:
    senses = entry.get("senses", [])
    if not senses or not all(sense.get("form_of") for sense in senses):
        return []
    return list(dict.fromkeys(target["word"] for sense in senses for target in sense["form_of"]))


def resolve_lemma(entry: dict, entries: dict[str, list[dict]]) -> dict:
    for target in form_of_targets(entry):
        for candidate in entries.get(target, []):
            if candidate["pos"] == entry["pos"]:
                return candidate
    return entry


def gloss_overlap(entry: dict, translation: set[str]) -> int:
    return shared_words(translation, " ".join(gloss for sense in entry.get("senses", []) for gloss in sense.get("glosses", [])))


def choose_entry(part: Part, translation: set[str], entries: dict[str, list[dict]]) -> tuple[dict, dict] | None:
    candidates = next((entries[key] for key in part.lookups if key in entries), [])
    if part.article:
        candidates = [entry for entry in candidates if entry["pos"] in NOUN_POS] or candidates
        candidates = [
            entry for entry in candidates
            if not articles_conflict(part.article, noun_article(resolve_lemma(entry, entries)))
        ] or candidates
    pairs = [(entry, resolve_lemma(entry, entries)) for entry in candidates]
    if not pairs:
        return None
    return max(pairs, key=lambda pair: (gloss_overlap(pair[1], translation), pair[0] is not pair[1]))


def first_form(entry: dict, required: set[str], excluded: set[str] = frozenset(), exact: bool = False) -> str | None:
    for form in entry.get("forms", []):
        tags = set(form.get("tags", []))
        if (tags == required if exact else required <= tags) and not tags & (excluded | RARE_FORM_TAGS):
            return form["form"]
    return None


def noun_article(entry: dict) -> str | None:
    for template in entry.get("head_templates", []):
        if template["name"] == "nl-noun":
            genders = template["args"].get("1", "").split(",")
            articles = {GENDER_ARTICLES.get(gender.strip()) for gender in genders} - {None}
            return "/".join(sorted(articles)) or None
    return None


def conjugation_template(entry: dict) -> dict | None:
    for template in entry.get("inflection_templates", []):
        if template["name"].startswith("nl-conj"):
            return template
    return None


def auxiliary(template: dict | None) -> str | None:
    if template is None:
        return None
    default = "hebben" if template["name"] in HEBBEN_DEFAULT_TEMPLATES else None
    return template["args"].get("aux", default)


def verb_parts(entry: dict) -> Verb:
    template = conjugation_template(entry)
    particle = template["args"].get("sep") if template else None
    clause = {"main-clause"} if particle else set()
    return Verb(
        infinitive=entry["word"],
        past_singular=first_form(entry, {"first-person", "past", "singular"} | clause),
        past_plural=first_form(entry, {"past", "plural"} | clause, excluded={"participle"}),
        past_participle=first_form(entry, {"participle", "past"}),
        auxiliary=auxiliary(template),
        particle=particle,
    )


def all_forms(word: str, lemma: dict) -> list[str]:
    forms = {word, lemma["word"]}
    forms.update(form["form"] for form in lemma.get("forms", []) if not set(form.get("tags", [])) & META_FORM_TAGS)
    return sorted(forms)


def describe(part: Part, entry: dict, lemma: dict) -> Headword:
    pos = entry["pos"]
    return Headword(
        word=part.word,
        pos=pos,
        lemma=lemma["word"],
        noun=Noun(
            article=noun_article(lemma),
            plural=first_form(lemma, {"plural"}, exact=True),
            diminutive=first_form(lemma, {"diminutive"}, excluded={"plural"}),
        ) if pos in NOUN_POS else None,
        verb=verb_parts(lemma) if pos == "verb" else None,
        adjective=Adjective(
            comparative=first_form(lemma, {"comparative"}, exact=True),
            superlative=first_form(lemma, {"superlative"}, exact=True),
        ) if pos == "adj" else None,
        forms=all_forms(part.word, lemma),
    )


def articles_conflict(ours: str | None, theirs: str | None) -> bool:
    return bool(ours and theirs) and not set(ours.split("/")) & set(theirs.split("/"))


@dataclass
class Lexicon:
    entries: list[dict] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    unmatched_meaning: list[str] = field(default_factory=list)
    article_conflicts: list[tuple[str, str]] = field(default_factory=list)


def build_lexicon(words: list[Word], wiktionary: Path) -> Lexicon:
    translations = defaultdict(set)
    for word in words:
        translations[word.dutch] |= content_words(word.translation)
    parts = {dutch: split_headwords(dutch) for dutch in translations}
    wanted = {key for ps in parts.values() for part in ps for key in part.lookups}
    entries = load_entries(wiktionary, wanted)
    lemmas = {target for es in entries.values() for entry in es for target in form_of_targets(entry)}
    entries.update(load_entries(wiktionary, lemmas - entries.keys()))

    lexicon = Lexicon()
    for dutch, dutch_parts in parts.items():
        headwords = []
        for part in dutch_parts:
            chosen = choose_entry(part, translations[dutch], entries)
            if chosen is None:
                lexicon.missing.append(part.word)
                headwords.append(Headword(part.word))
                continue
            entry, lemma = chosen
            headword = describe(part, entry, lemma)
            if gloss_overlap(lemma, translations[dutch]) == 0:
                lexicon.unmatched_meaning.append(f"{dutch} -> {lemma['word']} ({entry['pos']})")
            is_base_form = entry is lemma
            if headword.noun and is_base_form and articles_conflict(part.article, headword.noun.article):
                lexicon.article_conflicts.append((dutch, headword.noun.article))
            headwords.append(headword)
        lexicon.entries.append({"dutch": dutch, "headwords": headwords})
    return lexicon
