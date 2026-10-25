import json

from duolingo_anki.cli import read_words


def test_words_are_read_with_their_gloss_overrides(tmp_path):
    (tmp_path / "words.json").write_text(json.dumps([{"dutch": "slaan", "translation": "to turn", "tag": "Verbs"}]))
    (tmp_path / "gloss_overrides.json").write_text(json.dumps({"glosses": {"slaan": {"to turn": "to hit"}}, "articles": {}}))
    assert [word.translation for word in read_words(tmp_path / "words.json")] == ["to hit"]
