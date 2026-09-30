import pytest

from duolingo_anki.lexicon import (
    Part,
    auxiliary,
    choose_entry,
    content_words,
    noun_article,
    split_headwords,
    verb_parts,
    verb_phrase,
)


def words_and_articles(dutch: str) -> list[tuple[str, str | None]]:
    return [(part.word, part.article) for part in split_headwords(dutch)]


@pytest.mark.parametrize(
    ("dutch", "expected"),
    [
        ("de man", [("man", "de")]),
        ("'t huis", [("huis", "het")]),
        ("de/het drop", [("drop", "de/het")]),
        ("de bon / het bonnetje", [("bon", "de"), ("bonnetje", "het")]),
        ("de brandweerman/brandweervrouw", [("brandweerman", "de"), ("brandweervrouw", "de")]),
        ("de acteur(mas)/actrice(fem)", [("acteur", "de"), ("actrice", "de")]),
        ("(een) beetje", [("beetje", None)]),
        ("het spijt me", [("het spijt me", None)]),
        ("hoe gaat het?", [("hoe gaat het", None)]),
        ("dat/die", [("dat", None), ("die", None)]),
        ("al + P.P.", []),
        ("hoe...hoe...", []),
    ],
)
def test_split_headwords(dutch, expected):
    assert words_and_articles(dutch) == expected


def test_separable_and_reflexive_lookups():
    (separable,) = split_headwords("aan|bieden")
    assert separable.word == "aanbieden"
    assert {"aanbieden", "aan bieden"} <= set(separable.lookups)
    (reflexive,) = split_headwords("zich wassen")
    assert "wassen" in reflexive.lookups


@pytest.mark.parametrize(
    ("gender", "article"),
    [("m", "de"), ("f", "de"), ("n", "het"), ("m,n", "de/het"), ("p", "de"), ("?", None)],
)
def test_noun_article(gender, article):
    entry = {"head_templates": [{"name": "nl-noun", "args": {"1": gender}}]}
    assert noun_article(entry) == article


@pytest.mark.parametrize(
    ("template", "expected"),
    [
        ({"name": "nl-conj-st", "args": {}}, "hebben"),
        ({"name": "nl-conj-wk", "args": {"aux": "zijn"}}, "zijn"),
        ({"name": "nl-conj-irr", "args": {"1": "zijn"}}, None),
        (None, None),
    ],
)
def test_auxiliary(template, expected):
    assert auxiliary(template) == expected


def test_separable_verb_parts():
    entry = {
        "word": "opstaan",
        "inflection_templates": [{"name": "nl-conj-st", "args": {"sep": "op", "aux": "zijn"}}],
        "forms": [
            {"form": "opstond", "tags": ["first-person", "past", "singular", "subordinate-clause"]},
            {"form": "stond op", "tags": ["first-person", "main-clause", "past", "singular"]},
            {"form": "stonde op", "tags": ["archaic", "first-person", "main-clause", "past", "singular", "subjunctive"]},
            {"form": "stonden op", "tags": ["main-clause", "past", "plural"]},
            {"form": "opgestaan", "tags": ["participle", "past"]},
        ],
    }
    verb = verb_parts(entry)
    assert (verb.past_singular, verb.past_plural, verb.past_participle) == ("stond op", "stonden op", "opgestaan")
    assert (verb.particle, verb.auxiliary) == ("op", "zijn")


def test_choose_entry_follows_inflections_and_meaning():
    entries = {
        "leest": [
            {"word": "leest", "pos": "noun", "senses": [{"glosses": ["last (shoemaker's form)"]}]},
            {"word": "leest", "pos": "verb", "senses": [{"form_of": [{"word": "lezen"}], "glosses": ["inflection of lezen"]}]},
        ],
        "lezen": [{"word": "lezen", "pos": "verb", "senses": [{"glosses": ["to read"]}]}],
    }
    part = Part("leest", None, ("leest",))
    entry, lemma = choose_entry(part, content_words("read(s) (2nd and 3rd person singular)"), entries)
    assert (entry["pos"], lemma["word"]) == ("verb", "lezen")


def test_choose_entry_prefers_matching_article():
    entries = {
        "punt": [
            {"word": "punt", "pos": "noun", "head_templates": [{"name": "nl-noun", "args": {"1": "n"}}], "senses": []},
            {"word": "punt", "pos": "noun", "head_templates": [{"name": "nl-noun", "args": {"1": "m"}}], "senses": []},
        ],
    }
    entry, _ = choose_entry(Part("punt", "de", ("punt",)), set(), entries)
    assert noun_article(entry) == "de"


def test_verb_phrase_uses_forms_of_its_last_word():
    entries = {
        "komen": [{
            "word": "komen", "pos": "verb", "senses": [{"glosses": ["to come"]}],
            "inflection_templates": [{"name": "nl-conj-st", "args": {"aux": "zijn"}}],
            "forms": [{"form": "kwamen", "tags": ["past", "plural"]}, {"form": "gekomen", "tags": ["participle", "past"]}],
        }],
    }
    phrase = verb_phrase(Part("in opstand komen", None, ("in opstand komen",)), entries)
    assert phrase.verb.particle == "in opstand"
    assert {"kwamen in opstand", "in opstand gekomen"} <= set(phrase.forms)
