from duolingo_anki.english import Meaning
from duolingo_anki.matching import FormMatch, Phrase, build_rules
from duolingo_anki.sentences import (
    Candidate,
    Example,
    Target,
    Vocabulary,
    choose,
    distinct,
    improves,
    needs_example,
    rank,
)

NO_VOCABULARY = Vocabulary([], {})


def candidate(text: str, translation: str, form: FormMatch = FormMatch.TAUGHT, order: int = 0, word: str = "kussen") -> Candidate:
    rule = Phrase(word, form, (word,), (word,))
    return Candidate(Example(text, translation, word, "tatoeba"), rule, (order,))


def target(*glosses: str, **fields) -> Target:
    return Target(Meaning.of(list(glosses)), **fields)


def test_prefers_matching_meaning():
    pillow = candidate("Ik ben geen kussen!", "I am not a pillow.")
    kiss = candidate("Hij wil haar kussen.", "He wants to kiss her.", order=1)
    assert choose([pillow, kiss], target("to kiss"), NO_VOCABULARY) is kiss


def test_prefers_single_sentences():
    two = candidate("Je moet op deze knop drukken. Dan gaat hij aan.", "")
    one = candidate("Je moet op deze knop drukken.", "", order=1)
    assert rank(one, Target(), NO_VOCABULARY) < rank(two, Target(), NO_VOCABULARY)


def test_loose_matches_need_the_meaning():
    (rule,) = build_rules("schoon-", [])
    beauty = Candidate(Example("Dat is schoonheid.", "That is beauty.", "schoon-", "tatoeba"), rule, (0,))
    assert choose([beauty], target("in-law"), NO_VOCABULARY) is None


def test_strict_choice_rejects_unrelated_translations():
    unrelated = candidate("Hij wil haar kussen.", "Brussels paid a third of the cost.")
    assert choose([unrelated], target("to kiss"), NO_VOCABULARY, strict=True) is None


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


def test_bracketed_notes_are_not_meaning():
    assert not Meaning.of(["sample (monster)"]).carried_by("I'm not a monster.")
    assert Meaning.of(["we (stressed)"]) == Meaning()
    assert Meaning.of(["you (formal)"]) == Meaning()


def test_reflexive_entries_prefer_a_reflexive_pronoun():
    passive = candidate("Het moet gewassen worden.", "It needs to be washed.", word="gewassen")
    reflexive = candidate("Hij wast zich elke ochtend.", "He washes every morning.", order=1, word="wast")
    wash = target("to wash oneself", reflexive=True)
    assert choose([passive, reflexive], wash, NO_VOCABULARY) is reflexive


def test_verbs_avoid_a_sentence_initial_infinitive_used_as_a_noun():
    noun = candidate("Aanvragen worden tot morgen aanvaard.", "Applications are accepted until tomorrow.", word="aanvragen")
    verb = candidate("Je moet het visum aanvragen.", "You have to apply for the visa.", order=1, word="aanvragen")
    question = candidate("Aanvragen jullie een visum?", "Are you applying for a visa?", order=2, word="aanvragen")
    apply = target("to apply", infinitives=frozenset({"aanvragen"}))
    assert choose([noun, verb], apply, NO_VOCABULARY) is verb
    assert rank(question, apply, NO_VOCABULARY)[1] is False


def test_known_vocabulary_counts_only_earlier_words():
    lexicon = [{"dutch": "de man"}, {"dutch": "lopen"}, {"dutch": "hond"}]
    vocabulary = Vocabulary(lexicon, {"de man": 0, "lopen": 1, "hond": 2})
    assert vocabulary.known(["de", "man", "hond"], 1) == 2 / 3
    assert vocabulary.known(["de", "man", "hond"], 2) == 1


def test_examples_without_the_meaning_are_replaced_by_ones_with_it():
    gorge = target("gorge")
    gap = Example("Die kloof wordt kleiner.", "That gap is narrowing.", "kloof", "tatoeba")
    canyon = Example("De rivier stroomt door een diepe kloof.", "The river flows through a deep gorge.", "kloof", "opus/wikimedia")
    assert needs_example(gap, gorge)
    assert improves(gap, canyon, gorge)
    assert not improves(canyon, gap, gorge)


def test_choose_avoids_sentences_other_words_use():
    shared = candidate("Hij wil haar kussen.", "He wants to kiss her.")
    own = candidate("Ze kussen elkaar.", "They kiss each other.", order=1)
    assert choose([shared, own], target("to kiss"), NO_VOCABULARY, used={shared.example.text}) is own
    assert choose([shared], target("to kiss"), NO_VOCABULARY, used={shared.example.text}) is shared


def test_distinct_gives_each_word_its_own_sentence():
    stressed = "Voel je je gestrest?"
    tiers = {
        "gestrest": [candidate(stressed, "", word="gestrest")],
        "je": [candidate(stressed, "", word="je"), candidate("Heb je honger?", "", order=1, word="je")],
        "jij": [candidate(stressed, "", form=FormMatch.OTHER, word="je")],
    }
    targets = {"gestrest": Target(position=5), "je": Target(position=1), "jij": Target(position=2)}
    chosen = distinct(tiers, targets)
    assert chosen["gestrest"].example.text == stressed
    assert chosen["je"].example.text == "Heb je honger?"
    assert chosen["jij"].example.text == stressed


def test_a_meaning_only_replaces_a_short_sentence_with_a_short_one():
    trait = target("trait, quality")
    short = Example("Deze vloeistof bezit één vreemde eigenschap.", "This liquid possesses one strange property.", "eigenschap", "tatoeba")
    long = Example(
        "De oogkleur bleek dominant te zijn toen zij werd gefokt met katers zonder deze eigenschap.",
        "The eye colour proved dominant when she was bred to males without the trait.", "eigenschap", "opus/wikimedia",
    )
    assert needs_example(short, trait)
    assert not improves(short, long, trait)


def test_hyphens_do_not_split_words():
    assert Meaning.of(["co-operation"]).carried_by("Thank you for your cooperation.")


class FakeTatoeba:
    def __init__(self, dutch: dict[int, str], links: dict[int, list[tuple[int, str]]]):
        from duolingo_anki.matching import tokens
        from duolingo_anki.tatoeba import Sentence

        self.index = type("Index", (), {})()
        self.index.sentences = {id_: Sentence(id_, text, "author") for id_, text in dutch.items()}
        self.index.tokens = {id_: tokens(text) for id_, text in dutch.items()}
        self.links = {id_: [Sentence(target, text, "translator") for target, text in targets] for id_, targets in links.items()}

    def add_indirect_translations(self, ids):
        pass

    def english(self, ids):
        return {id_: self.links[id_] for id_ in ids if id_ in self.links}


def test_a_chosen_sentence_is_used_as_given():
    from duolingo_anki.sentences import chosen_sentence
    tatoeba = FakeTatoeba({1: "Hij wast zich."}, {1: [(2, "He washes himself.")]})
    rules = build_rules("zich wassen", [{"word": "zich wassen", "forms": ["wassen", "wast"]}])
    candidate = chosen_sentence(tatoeba, "zich wassen", rules, {"tatoeba": 1, "translation": 2})
    assert (candidate.example.text, candidate.example.translation, candidate.example.match) == ("Hij wast zich.", "He washes himself.", "wast")


def test_a_chosen_sentence_must_contain_the_word_and_its_translation():
    import pytest
    from duolingo_anki.sentences import SentenceOverrideError, chosen_sentence
    tatoeba = FakeTatoeba({1: "Ik ging naar bed."}, {1: [(2, "I went to bed.")]})
    rules = build_rules("ging", [{"word": "ging", "forms": ["ging"]}])
    with pytest.raises(SentenceOverrideError, match="not a translation"):
        chosen_sentence(tatoeba, "ging", rules, {"tatoeba": 1, "translation": 3})
    with pytest.raises(SentenceOverrideError, match="does not contain"):
        chosen_sentence(tatoeba, "zing", build_rules("zing", [{"word": "zing", "forms": ["zing"]}]), {"tatoeba": 1, "translation": 2})


def test_chosen_sentences_win_their_sentence():
    shared = candidate("Hij wast zich.", "", word="wast")
    tiers = {"zich wassen": [shared], "wassen": [shared, candidate("Ik was de auto.", "", order=1, word="was")]}
    chosen = distinct(tiers, {"zich wassen": Target(position=9), "wassen": Target(position=1)}, {"zich wassen"})
    assert (chosen["zich wassen"].example.text, chosen["wassen"].example.text) == ("Hij wast zich.", "Ik was de auto.")
