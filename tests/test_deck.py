import json
import sqlite3
import zipfile

import genanki
import pytest

from duolingo_anki.deck import FIELDS, build_deck
from duolingo_anki.guids import GuidError

WORDS = [
    {"dutch": "de man", "translation": "the man", "tag": "Basics_1"},
    {"dutch": "kleine", "translation": "small", "tag": "Adjectives"},
    {"dutch": "klein", "translation": "small", "tag": "Adjectives"},
    {"dutch": "Gent", "translation": "Ghent", "tag": "Belgium"},
    {"dutch": "de winterkleren", "translation": "winter clothes", "tag": "Clothing"},
]
LEXICON = {
    "de man": [{"word": "man", "pos": "noun", "lemma": "man", "noun": {"article": "de", "plural": "mannen"}, "forms": ["man", "mannen"], "senses": ["man", "husband"]}],
    "kleine": [{"word": "kleine", "pos": "adj", "lemma": "klein", "forms": ["klein", "kleine"], "inflection": ["attributive", "plural"]}],
    "klein": [{"word": "klein", "pos": "adj", "lemma": "klein", "forms": ["klein", "kleine"]}],
    "Gent": [{"word": "Gent", "pos": "name", "lemma": "Gent"}],
    "de winterkleren": [{"word": "winterkleren"}],
}
EXAMPLES = {
    "de man": {"text": "Kleren maken de man.", "translation": "Clothes make the man.", "match": "man", "source": "tatoeba", "url": "https://tatoeba.org/en/sentences/show/375962"},
    "kleine": {"text": "Ik heb een kleine auto.", "translation": "I have a small car.", "match": "kleine", "source": "tatoeba"},
    "klein": {"text": "Het huis is klein.", "translation": "The house is small.", "match": "klein", "source": "tatoeba"},
    "Gent": {"text": "Gent is mooi.", "translation": "Ghent is beautiful.", "match": "gent", "source": "tatoeba"},
}


def write_data(directory):
    (directory / "audio").mkdir(parents=True)
    audio = []
    for number, dutch in enumerate(LEXICON):
        clips = {"word": {"text": dutch, "file": f"w{number}.mp3"}}
        if dutch in EXAMPLES:
            clips["sentence"] = {"text": EXAMPLES[dutch]["text"], "file": f"s{number}.mp3"}
        for clip in clips.values():
            (directory / "audio" / clip["file"]).write_bytes(b"mp3")
        audio.append({"dutch": dutch, "voice": "F1", **clips})
    files = {
        "words.json": WORDS,
        "lexicon.json": {"entries": [{"dutch": dutch, "headwords": headwords} for dutch, headwords in LEXICON.items()]},
        "sentences.json": {"entries": [{"dutch": dutch, **({"example": EXAMPLES[dutch]} if dutch in EXAMPLES else {})} for dutch in LEXICON]},
        "audio.json": {"entries": audio},
        "word_overrides.json": {"glosses": {}, "articles": {}, "removed": []},
        "guid_aliases.json": {},
    }
    for name, content in files.items():
        (directory / name).write_text(json.dumps(content), encoding="utf-8")


def notes(package):
    with zipfile.ZipFile(package) as archive:
        archive.extract("collection.anki2", package.parent)
    database = sqlite3.connect(package.parent / "collection.anki2")
    rows = database.execute("select guid, flds from notes").fetchall()
    return {fields.split("\x1f")[0]: (guid, dict(zip(FIELDS, fields.split("\x1f")))) for guid, fields in rows}


@pytest.fixture
def built(tmp_path):
    write_data(tmp_path / "data")
    build_deck(tmp_path / "data", tmp_path / "build", tmp_path / "deck.apkg")
    return notes(tmp_path / "deck.apkg")


def test_guids_follow_the_dutch_key(built):
    assert {dutch: guid for dutch, (guid, _) in built.items()} == {dutch: genanki.guid_for(dutch) for dutch in LEXICON}


def test_field_values(built):
    man = built["de man"][1]
    assert (man["Dutch"], man["English"], man["TypeAnswer"]) == ("de man", "the man", "de man")
    assert man["Sentence"] == "Kleren maken de <b>man</b>."
    assert man["OtherMeanings"] == "husband"
    assert man["Listen"] == "1"
    assert man["SentenceAudio"] == '<audio src="_dd-s0.mp3" preload="none"></audio>'
    assert built["kleine"][1]["Hint"] == "inflected"
    assert built["klein"][1]["Hint"] == ""
    assert built["Gent"][1]["Listen"] == ""


def test_words_without_a_sentence_are_kept(built):
    clothes = built["de winterkleren"][1]
    assert (clothes["Sentence"], clothes["SentenceAudio"], clothes["Source"]) == ("", "", "")
    assert clothes["WordAudio"].startswith("[sound:")


def test_a_renamed_word_needs_an_alias(tmp_path):
    data = tmp_path / "data"
    write_data(data)
    build_deck(data, tmp_path / "build", tmp_path / "deck.apkg")
    words = [{**word, "dutch": "man"} if word["dutch"] == "de man" else word for word in WORDS]
    (data / "words.json").write_text(json.dumps(words), encoding="utf-8")
    for name, key in (("lexicon.json", "entries"), ("sentences.json", "entries"), ("audio.json", "entries")):
        content = json.loads((data / name).read_text(encoding="utf-8"))
        content[key] = [{**item, "dutch": "man"} if item["dutch"] == "de man" else item for item in content[key]]
        (data / name).write_text(json.dumps(content), encoding="utf-8")
    with pytest.raises(GuidError, match='"de man": "man"'):
        build_deck(data, tmp_path / "build", tmp_path / "deck.apkg")
    (data / "guid_aliases.json").write_text(json.dumps({"de man": "man"}), encoding="utf-8")
    build_deck(data, tmp_path / "build", tmp_path / "deck.apkg")
    assert notes(tmp_path / "deck.apkg")["man"][0] == genanki.guid_for("de man")


def test_source_line_names_written_sentences_and_translations():
    from duolingo_anki.deck import source_html
    assert source_html({"source": "deck", "written": "sentence"}) == "Written for this deck"
    assert source_html({"source": "tatoeba", "url": "https://t/1", "written": "translation"}) == '<a href="https://t/1">Tatoeba</a> · translation written for this deck'
