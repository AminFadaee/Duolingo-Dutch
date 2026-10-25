import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

import genanki

SIMILAR = 0.8
NOTE = re.compile(r"\([^)]*\)")
ARTICLE = re.compile(r"^(?:de|het|'t)\s+")
SEPARATORS = re.compile(r"[|/]+|\s+")


class GuidError(ValueError):
    pass


@dataclass
class KeyChanges:
    successors: list[tuple[str, str]] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    stale: list[str] = field(default_factory=list)


def normalized(dutch: str) -> str:
    text = ARTICLE.sub("", NOTE.sub("", dutch).strip().lower())
    return SEPARATORS.sub(" ", text).strip(" ?!.,")


def similarity(first: str, second: str) -> float:
    return SequenceMatcher(None, normalized(first), normalized(second)).ratio()


def origins(aliases: dict[str, str]) -> dict[str, str]:
    found = {}
    for old in aliases.keys() - set(aliases.values()):
        current = old
        while current in aliases:
            current = aliases[current]
        found[current] = old
    return found


def note_guid(dutch: str, aliases: dict[str, str]) -> str:
    return genanki.guid_for(origins(aliases).get(dutch, dutch))


def key_changes(record: dict[str, list[str]], current: dict[str, list[str]], aliases: dict[str, str]) -> KeyChanges:
    changes = KeyChanges()
    changes.stale = [old for old in aliases if old in current]
    changes.stale += [old for target, old in origins(aliases).items() if target not in current]
    covered = set(aliases)
    added = [dutch for dutch in current if dutch not in record and dutch not in origins(aliases)]
    for old, skills in record.items():
        if old in current or old in covered:
            continue
        candidates = [
            (similarity(old, new), new) for new in added
            if set(skills) & set(current[new]) and similarity(old, new) >= SIMILAR
        ]
        if candidates:
            changes.successors.append((old, max(candidates)[1]))
        else:
            changes.removed.append(old)
    return changes


def check_keys(record: dict[str, list[str]], current: dict[str, list[str]], aliases: dict[str, str]) -> KeyChanges:
    changes = key_changes(record, current, aliases)
    problems = []
    if changes.successors:
        problems.append(
            "Notes whose key changed would lose their progress; add these to guid_aliases.json:\n"
            + "\n".join(f'  "{old}": "{new}",' for old, new in changes.successors)
        )
    if changes.stale:
        problems.append("Aliases that no longer apply:\n" + "\n".join(f"  {alias}" for alias in changes.stale))
    if problems:
        raise GuidError("\n".join(problems))
    return changes
