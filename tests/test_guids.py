import json
from pathlib import Path

import genanki
import pytest

from duolingo_anki.guids import GuidError, check_keys, key_changes, note_guid

DATA = Path(__file__).parent.parent / "data"


def test_every_current_note_keeps_its_guid():
    aliases = json.loads((DATA / "guid_aliases.json").read_text(encoding="utf-8"))
    keys = [entry["dutch"] for entry in json.loads((DATA / "sentences.json").read_text(encoding="utf-8"))["entries"]]
    record = json.loads((DATA / "note_keys.json").read_text(encoding="utf-8"))
    assert set(keys) == set(record)
    assert all(note_guid(dutch, aliases) == genanki.guid_for(dutch) for dutch in keys if dutch not in aliases.values())


def test_a_changed_key_with_a_similar_successor_fails_loudly():
    record = {"de man": ["Basics_1"], "de vrouw": ["Basics_1"]}
    current = {"man": ["Basics_1"], "de vrouw": ["Basics_1"]}
    with pytest.raises(GuidError, match='"de man": "man"'):
        check_keys(record, current, {})


def test_an_alias_keeps_the_old_guid():
    record = {"de kalender": ["Calender"]}
    current = {"de kalenders": ["Calender"]}
    aliases = {"de kalender": "de kalenders"}
    assert check_keys(record, current, aliases).successors == []
    assert note_guid("de kalenders", aliases) == genanki.guid_for("de kalender")


def test_aliases_chain_to_the_first_key():
    aliases = {"a": "b", "b": "c"}
    assert note_guid("c", aliases) == genanki.guid_for("a")


def test_removed_words_are_reported_and_stale_aliases_fail():
    changes = key_changes({"de hond": ["Animals"], "de kat": ["Animals"]}, {"de kat": ["Animals"]}, {})
    assert (changes.successors, changes.removed) == ([], ["de hond"])
    with pytest.raises(GuidError, match="no longer apply"):
        check_keys({"de kat": ["Animals"]}, {"de kat": ["Animals"]}, {"de kat": "de poes"})


def test_unrelated_new_words_in_another_skill_are_not_successors():
    changes = key_changes({"de man": ["Basics_1"]}, {"man": ["Food_1"]}, {})
    assert changes.removed == ["de man"]
