from duolingo_anki.english import Meaning
from duolingo_anki.senses import by_usage, common_senses, other_meanings, split_candidates, trim


def test_common_senses_skip_uncommon_and_form_of_senses():
    entry = {"word": "eng", "senses": [
        {"glosses": ["scary, creepy"]},
        {"glosses": ["narrow"]},
        {"glosses": ["small"], "tags": ["archaic"]},
        {"glosses": ["inflection of eng:", "plural"], "form_of": [{"word": "eng"}]},
        {"glosses": ["free; not imprisoned or enslaved."]},
    ]}
    assert common_senses(entry) == ["scary, creepy", "narrow", "free"]


def test_synonym_only_senses_are_skipped():
    intussen = {"word": "intussen", "senses": [
        {"glosses": ["synonym of ondertussen"], "synonyms": [{"word": "ondertussen", "tags": ["synonym", "synonym-of"]}]},
    ]}
    assert common_senses(intussen) == []


def test_trim_drops_long_notes():
    assert trim("tap, faucet") == "tap, faucet"
    assert trim("button (knob or small disc serving as a fastener)") == "button"


def test_usage_reorders_senses_but_keeps_the_taught_one():
    senses = ["bench", "couch, sofa", "place where seashells are found", "a bank"]
    translations = ["She sat on the couch."] * 3
    assert by_usage(senses, translations, Meaning.of(["bank"])) == ["couch, sofa", "bench", "place where seashells are found", "a bank"]


def test_other_meanings_leave_out_the_word_itself():
    assert other_meanings([{"word": "kroket", "lemma": "kroket", "senses": ["kroket", "croquette"]}], ["snack"]) == ["croquette"]


def test_other_meanings_leave_out_what_duolingo_teaches():
    headwords = [{"word": "vinden", "senses": ["to find (after searching)", "to find, to think, to feel"]}]
    assert other_meanings(headwords, ["to find"]) == ["to think, to feel"]
    assert other_meanings([{"word": "slaan", "senses": ["to hit, to slap", "to beat", "to strike"]}], ["to turn"]) == ["to hit, to slap", "to beat"]


def test_split_candidates_need_glosses_matching_unrelated_senses():
    from duolingo_anki.lexicon import Headword
    entries = [
        {"dutch": "de baan", "headwords": [Headword("baan", senses=["a job", "orbit"])]},
        {"dutch": "de zaak", "headwords": [Headword("zaak", senses=["business, shop", "matter"])]},
    ]
    glosses = {"de baan": ["job; orbit"], "de zaak": ["business"]}
    assert split_candidates(entries, glosses) == ["de baan (job; orbit): a job | orbit"]
