import re
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass

INFLECTIONS = (
    ({"participle", "past"}, "past participle"),
    ({"participle", "present"}, "present participle"),
    ({"past", "plural"}, "past, plural"),
    ({"past"}, "past"),
    ({"diminutive"}, "diminutive"),
    ({"attributive"}, "inflected"),
    ({"partitive"}, "inflected"),
    ({"comparative"}, "comparative"),
    ({"superlative"}, "superlative"),
    ({"plural"}, "plural"),
    ({"present"}, "present"),
)
PARTS_OF_SPEECH = {
    "noun": "noun", "name": "name", "verb": "verb", "adj": "adjective", "adv": "adverb", "pron": "pronoun",
    "det": "determiner", "article": "determiner", "prep": "preposition", "conj": "conjunction",
    "intj": "interjection", "num": "number",
}
ARTICLE = re.compile(r"^(de|het) ")
SENSE_END = re.compile(r"[;,(]")
REFLEXIVE = "zich "


@dataclass(frozen=True)
class Note:
    dutch: str
    display: str
    english: str
    headwords: list[dict]


def inflection(note: Note) -> str | None:
    if note.dutch.startswith(REFLEXIVE):
        return "reflexive"
    if len(note.headwords) != 1 or not note.headwords[0].get("inflection"):
        return None
    tags = set(note.headwords[0]["inflection"])
    return next((label for required, label in INFLECTIONS if required <= tags), "inflected")


def register(note: Note) -> str | None:
    return next((headword["register"] for headword in note.headwords if headword.get("register")), None)


def part_of_speech(note: Note) -> str:
    labels = dict.fromkeys(PARTS_OF_SPEECH.get(headword.get("pos"), "phrase") for headword in note.headwords)
    return "/".join(labels) or "phrase"


def article(note: Note) -> str | None:
    match = ARTICLE.match(note.display)
    return f"{match.group(1)} …" if match else None


def sense(note: Note) -> str | None:
    found = next((headword["sense"] for headword in note.headwords if headword.get("sense")), None)
    return SENSE_END.split(found)[0].strip() if found else None


def contrast_register(values: dict[str, str | None]) -> dict[str, str | None]:
    if "formal" in values.values():
        return {dutch: value or "informal" for dutch, value in values.items()}
    return values


FEATURES: tuple[Callable[[Note], str | None], ...] = (inflection, register, part_of_speech, article)


def distinct(hints: dict[str, list[str]]) -> bool:
    return len({tuple(hint) for hint in hints.values()}) == len(hints)


def prefix(note: Note, length: int) -> str:
    word = ARTICLE.sub("", note.display)
    match = ARTICLE.match(note.display)
    return f"{match.group(1) + ' ' if match else ''}{word[:length]}…"


def group_hints(notes: list[Note]) -> dict[str, list[str]]:
    hints = {note.dutch: [] for note in notes}
    for feature in FEATURES:
        values = {note.dutch: feature(note) for note in notes}
        if feature is register:
            values = contrast_register(values)
        if len(set(values.values())) > 1:
            for dutch, value in values.items():
                if value:
                    hints[dutch].append(value)
        if distinct(hints):
            return hints
    if distinct(lettered := {note.dutch: [*hints[note.dutch], prefix(note, 1)] for note in notes}):
        return lettered
    senses = {note.dutch: sense(note) for note in notes}
    if all(senses.values()):
        sensed = {
            note.dutch: [*hints[note.dutch], senses[note.dutch]] if senses[note.dutch].lower() != note.english.lower() else hints[note.dutch]
            for note in notes
        }
        if distinct(sensed):
            return sensed
    longest = max(len(ARTICLE.sub("", note.display)) for note in notes)
    for length in range(2, longest + 1):
        if distinct(lettered := {note.dutch: [*hints[note.dutch], prefix(note, length)] for note in notes}):
            return lettered
    return hints


def note_hints(notes: list[Note]) -> dict[str, str]:
    hints = {note.dutch: [value] if (value := inflection(note)) and value != "reflexive" else [] for note in notes}
    groups = defaultdict(list)
    for note in notes:
        groups[note.english.lower()].append(note)
    for group in groups.values():
        if len(group) > 1:
            for dutch, values in group_hints(group).items():
                hints[dutch] = list(dict.fromkeys([*hints[dutch], *values]))
    return {dutch: ", ".join(values) for dutch, values in hints.items()}
