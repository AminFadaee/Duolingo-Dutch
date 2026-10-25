import re
from dataclasses import asdict, replace

from duolingo_anki.english import Meaning
from duolingo_anki.matching import build_rules

UNCOMMON_TAGS = {
    "archaic", "dated", "obsolete", "regional", "dialectal", "Belgium", "Flemish", "Brabant", "Limburg", "Suriname",
    "slang", "rare", "vulgar", "historical", "nonstandard",
}
KEPT = 3
SHOWN = 2
LONG_NOTE = re.compile(r"\s*\([^)]{21,}\)")
LONG_SENSE = 40


def trim(gloss: str) -> str:
    text = LONG_NOTE.sub("", gloss.split(";")[0]).strip().rstrip(".:")
    if len(text) > LONG_SENSE:
        text = text.split(",")[0].strip()
    return text


def common_senses(entry: dict) -> list[str]:
    senses = [
        trim(sense["glosses"][-1])
        for sense in entry.get("senses", [])
        if sense.get("glosses") and not sense.get("form_of") and not sense.get("alt_of")
        and not set(sense.get("tags", [])) & UNCOMMON_TAGS
    ]
    return list(dict.fromkeys(sense for sense in senses if sense))


def usage(sense: str, translations: list[str]) -> int:
    meaning = Meaning.of([sense])
    return sum(meaning.carried_by(translation) for translation in translations) if meaning.words else 0


def by_usage(senses: list[str], translations: list[str], taught: Meaning) -> list[str]:
    scores = {sense: (usage(sense, translations) + 1) / (index + 1) for index, sense in enumerate(senses)}
    ordered = sorted(senses, key=lambda sense: -scores[sense])
    return ordered[:KEPT] + [sense for sense in ordered[KEPT:] if taught.words and taught.carried_by(sense)]


def order_senses(entries: list[dict], tatoeba, glosses: dict[str, list[str]]) -> list[dict]:
    wanted = {}
    for entry in entries:
        for headword in entry["headwords"]:
            if len(headword.senses) > 1:
                wanted[(entry["dutch"], headword.word)] = list(tatoeba.matches(build_rules(headword.word, [asdict(headword)])))
    english = tatoeba.english({id_ for ids in wanted.values() for id_ in ids})
    ordered = []
    for entry in entries:
        headwords = []
        for headword in entry["headwords"]:
            ids = wanted.get((entry["dutch"], headword.word), [])
            translations = [sentence.text for id_ in ids for sentence in english.get(id_, [])]
            taught = Meaning.of(glosses[entry["dutch"]])
            headwords.append(replace(headword, senses=by_usage(headword.senses, translations, taught)))
        ordered.append({**entry, "headwords": headwords})
    return ordered


def matching(senses: list[str], gloss: str) -> list[int]:
    meaning = Meaning.of([gloss])
    return [index for index, sense in enumerate(senses) if meaning.words and meaning.carried_by(sense)]


def other_meanings(headwords: list[dict], glosses: list[str]) -> list[str]:
    meaning = Meaning.of(glosses)
    others = []
    for headword in headwords:
        for sense in headword.get("senses", []):
            untaught = [part.strip() for part in sense.split(",") if part.strip() and not (meaning.words and meaning.carried_by(part))]
            if untaught and (other := ", ".join(untaught)) not in others:
                others.append(other)
    return others[:SHOWN]


def gloss_parts(glosses: list[str]) -> list[str]:
    return [part.strip() for gloss in glosses for part in gloss.split(";") if part.strip()]


def taught_sense_report(entries: list[dict], glosses: dict[str, list[str]]) -> tuple[list[str], list[str]]:
    unmatched, secondary = [], []
    for entry in entries:
        if not any(Meaning.of([gloss]).words for gloss in glosses[entry["dutch"]]):
            continue
        for headword in entry["headwords"]:
            if not headword.senses or headword.inflection:
                continue
            found = [index for gloss in glosses[entry["dutch"]] for index in matching(headword.senses, gloss)]
            label = f"{entry['dutch']} ({'; '.join(glosses[entry['dutch']])}): {' | '.join(headword.senses)}"
            if not found:
                unmatched.append(label)
            elif min(found) > 0:
                secondary.append(label)
    return unmatched, secondary


def split_candidates(entries: list[dict], glosses: dict[str, list[str]]) -> list[str]:
    candidates = []
    for entry in entries:
        parts = gloss_parts(glosses[entry["dutch"]])
        for headword in entry["headwords"]:
            matched = [set(matching(headword.senses, part)) for part in parts]
            if any(first and second and not first & second for i, first in enumerate(matched) for second in matched[i + 1:]):
                candidates.append(f"{entry['dutch']} ({'; '.join(parts)}): {' | '.join(headword.senses)}")
    return list(dict.fromkeys(candidates))
