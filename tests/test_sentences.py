from duolingo_anki.english import Meaning
from duolingo_anki.matching import FormMatch, Phrase, build_rules
from duolingo_anki.sentences import Candidate, Example, choose, rank


def candidate(text: str, translation: str, form: FormMatch = FormMatch.TAUGHT, order: int = 0) -> Candidate:
    rule = Phrase("kussen", form, ("kussen",), ("kussen",))
    return Candidate(Example(text, translation, "kussen", "tatoeba"), rule, (order,))


def test_prefers_matching_meaning():
    pillow = candidate("Ik ben geen kussen!", "I am not a pillow.")
    kiss = candidate("Hij wil haar kussen.", "He wants to kiss her.", order=1)
    assert choose([pillow, kiss], Meaning.of(["to kiss"]), set()) is kiss


def test_prefers_single_sentences():
    two = candidate("Je moet op deze knop drukken. Dan gaat hij aan.", "")
    one = candidate("Je moet op deze knop drukken.", "", order=1)
    assert rank(one, Meaning(), set()) < rank(two, Meaning(), set())


def test_loose_matches_need_the_meaning():
    (rule,) = build_rules("schoon-", [])
    beauty = Candidate(Example("Dat is schoonheid.", "That is beauty.", "schoon-", "tatoeba"), rule, (0,))
    assert choose([beauty], Meaning.of(["in-law"]), set()) is None


def test_strict_choice_rejects_unrelated_translations():
    unrelated = candidate("Hij wil haar kussen.", "Brussels paid a third of the cost.")
    assert choose([unrelated], Meaning.of(["to kiss"]), set(), strict=True) is None


def test_strict_meaning_needs_every_word_of_one_alternative():
    meaning = Meaning.of(["the Eighty Years' War"])
    assert not meaning.carried_by("This conflict is known as the Eleven Years War.", strict=True)
    assert meaning.carried_by("This conflict is known as the Eighty Years' War.", strict=True)
    assert Meaning.of(["commemoration, remembrance"]).carried_by("A day of remembrance.", strict=True)


def test_translation_closest_to_the_machine_one_wins():
    from duolingo_anki.sentences import closest_to_machine
    from duolingo_anki.tatoeba import Sentence

    options = [Sentence(1, "Search me.", ""), Sentence(2, "I don't know.", "")]
    assert closest_to_machine(options, "I don't know.", Meaning()).id == 2
