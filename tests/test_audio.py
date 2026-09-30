import pytest

from duolingo_anki.audio import VOICES, file_name, spoken_word, voice_for


@pytest.mark.parametrize(
    ("dutch", "spoken"),
    [
        ("de man", "de man"),
        ("de bon / het bonnetje", "de bon, het bonnetje"),
        ("aan|bieden", "aanbieden"),
        ("de acteur(mas)/actrice(fem)", "de acteur, actrice"),
        ("Zuid-Afrika", "Zuid-Afrika"),
        ("noch...noch", None),
        ("al + P.P.", None),
        ("schoon-", None),
        ("-talig", None),
        ("half-(zus/broer)", None),
    ],
)
def test_spoken_word(dutch, spoken):
    assert spoken_word(dutch) == spoken


def test_voice_depends_only_on_the_text():
    assert voice_for("de man") == voice_for("de man") in VOICES
    assert {voice_for(f"woord {n}") for n in range(20)} == set(VOICES)


def test_file_name_depends_on_voice_and_text():
    assert file_name("de man", "F1") == file_name("de man", "F1")
    assert file_name("de man", "F1") != file_name("de man", "M1")
