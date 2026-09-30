import pytest

from duolingo_anki.matching import FormMatch, build_rules, tokens


def matching_rules(dutch: str, sentence: str, headwords: list[dict] | None = None) -> set[str]:
    return {rule.label for rule in build_rules(dutch, headwords or []) if rule.matches(tokens(sentence))}


@pytest.mark.parametrize(
    ("pattern", "sentence"),
    [
        ("noch...noch", "Hij drinkt noch rookt noch vloekt."),
        ("hoe...hoe...", "Hoe meer, hoe beter."),
        ("iets ...s", "Ik zag iets moois."),
        ("al + P.P.", "Hij liep al zingend naar huis."),
        ("net zo...als", "Hij is net zo groot als ik."),
    ],
)
def test_patterns_match(pattern, sentence):
    assert matching_rules(pattern, sentence) == {pattern}


def test_word_ending_pattern_needs_adjacent_word():
    assert not matching_rules("iets ...s", "Iets is altijd beter dan niets.")


@pytest.mark.parametrize(
    ("affix", "sentence", "expected"),
    [
        ("schoon-", "Mijn schoonmoeder komt morgen.", True),
        ("schoon-", "Dat is schoon.", False),
        ("-talig", "Ze is tweetalig opgevoed.", True),
        ("stief-(zus/broer)", "Ik heb een stiefzus.", True),
        ("stief-(zus/broer)", "Ik heb een stiefvader.", False),
    ],
)
def test_affixes(affix, sentence, expected):
    assert bool(matching_rules(affix, sentence)) == expected


def test_loose_rules_are_marked():
    (rule,) = build_rules("schoon-", [])
    assert rule.form == FormMatch.LOOSE


def test_separable_split_form_ranks_first():
    headword = {"word": "opstaan", "forms": ["opstaan", "staat op"], "verb": {"particle": "op"}}
    rules = {rule.label: rule.form for rule in build_rules("op|staan", [headword])}
    assert rules == {"opstaan": FormMatch.TAUGHT, "staat op": FormMatch.SPLIT}
    assert matching_rules("op|staan", "Ze staat vroeg op.", [headword]) == {"staat op"}


def test_verb_phrase_with_fixed_part_after_verb():
    headword = {"word": "in opstand komen", "forms": ["kwamen in opstand"], "verb": {"particle": "in opstand"}}
    assert matching_rules("in opstand komen", "De mensen kwamen tegen de koning in opstand.", [headword]) == {"kwamen in opstand"}


def test_article_is_optional_before_phrases():
    headword = {"word": "de vrije tijd"}
    assert matching_rules("de vrije tijd", "Wat doe je in je vrije tijd?", [headword]) == {"vrije tijd"}


def test_dutch_is_not_mistaken_for_english():
    from duolingo_anki.english import looks_english
    assert not looks_english("Het geheim van Gouda.")
    assert looks_english("Just like Manneken Pis in Brussels.")
