from duolingo_anki.english import meaning_words
from duolingo_anki.matching import FormMatch, Phrase, build_rules
from duolingo_anki.sentences import Candidate, Example, choose, rank


def candidate(text: str, translation: str, form: FormMatch = FormMatch.TAUGHT, order: int = 0) -> Candidate:
    rule = Phrase("kussen", form, ("kussen",), ("kussen",))
    return Candidate(Example(text, translation, "kussen", "tatoeba"), rule, (order,))


def test_prefers_matching_meaning():
    pillow = candidate("Ik ben geen kussen!", "I am not a pillow.")
    kiss = candidate("Hij wil haar kussen.", "He wants to kiss her.", order=1)
    assert choose([pillow, kiss], {"kiss"}, set()) is kiss


def test_prefers_single_sentences():
    two = candidate("Je moet op deze knop drukken. Dan gaat hij aan.", "")
    one = candidate("Je moet op deze knop drukken.", "", order=1)
    assert rank(one, set(), set()) < rank(two, set(), set())


def test_loose_matches_need_the_meaning():
    (rule,) = build_rules("schoon-", [])
    beauty = Candidate(Example("Dat is schoonheid.", "That is beauty.", "schoon-", "tatoeba"), rule, (0,))
    assert choose([beauty], meaning_words("in-law"), set()) is None


def test_strict_choice_rejects_unrelated_translations():
    unrelated = candidate("Hij wil haar kussen.", "Brussels paid a third of the cost.")
    assert choose([unrelated], {"kiss"}, set(), strict=True) is None
