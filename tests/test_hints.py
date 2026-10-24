from duolingo_anki.hints import Note, note_hints


def note(dutch: str, english: str, display: str | None = None, **headword) -> Note:
    return Note(dutch, display or dutch, english, [{"word": dutch, **headword}] if headword else [])


def test_inflected_notes_name_their_inflection():
    hints = note_hints([note("las", "read", pos="verb", lemma="lezen", inflection=["indicative", "past", "singular"])])
    assert hints == {"las": "past"}


def test_groups_are_told_apart_by_inflection_register_part_of_speech_and_article():
    hints = note_hints([
        note("klein", "small", pos="adj"),
        note("kleine", "small", pos="adj", lemma="klein", inflection=["attributive", "plural"]),
        note("alsjeblieft", "please", pos="adv"),
        note("alstublieft", "please", pos="intj", register="formal"),
        note("licht", "light", pos="adj"),
        note("het licht", "light", pos="noun"),
        note("het kopje", "cup", pos="noun"),
        note("de beker", "cup", pos="noun"),
    ])
    assert hints == {
        "klein": "", "kleine": "inflected",
        "alsjeblieft": "informal", "alstublieft": "formal",
        "licht": "adjective", "het licht": "noun",
        "het kopje": "het …", "de beker": "de …",
    }


def test_synonyms_get_as_many_letters_as_they_need():
    hints = note_hints([note("weer", "again", pos="adv"), note("opnieuw", "again", pos="adv")])
    assert hints == {"weer": "w…", "opnieuw": "o…"}
    hints = note_hints([note("liggen", "to lie", pos="verb"), note("liegen", "to lie", pos="verb")])
    assert hints == {"liggen": "lig…", "liegen": "lie…"}


def test_reflexive_is_only_a_hint_when_it_tells_notes_apart():
    hints = note_hints([note("zich voelen", "to feel", pos="verb", lemma="voelen"), note("voelen", "to feel", pos="verb")])
    assert hints == {"zich voelen": "reflexive", "voelen": ""}
    assert note_hints([note("zich wassen", "to wash oneself", pos="verb", lemma="wassen")]) == {"zich wassen": ""}


def test_a_sense_that_repeats_the_gloss_is_left_out():
    hints = note_hints([
        note("de knop", "button", "de knop", pos="noun", sense="a knob, button"),
        note("de knoop", "button", "de knoop", pos="noun", sense="button (fastener)"),
    ])
    assert hints == {"de knop": "a knob", "de knoop": ""}
