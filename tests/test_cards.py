from duolingo_anki.cards import article_twins, display_text, forms, highlight, merged_translations, word_tags

NOUN = {"word": "handboek", "lemma": "handboek", "pos": "noun", "noun": {"article": "het", "plural": "handboeken"}}
SEPARABLE = {
    "word": "opstaan", "lemma": "opstaan", "pos": "verb",
    "verb": {"infinitive": "opstaan", "past_singular": "stond op", "past_participle": "opgestaan", "auxiliary": "zijn", "particle": "op"},
}
PHRASE = {
    "word": "in opstand komen", "lemma": "komen", "pos": "verb",
    "verb": {"infinitive": "komen", "past_singular": "kwam", "past_participle": "gekomen", "auxiliary": "zijn", "particle": "in opstand"},
}


def test_display_uses_wiktionary_article_for_base_form_nouns():
    assert display_text("de handboek", [NOUN]) == "het handboek"
    assert display_text("de handboeken", [{**NOUN, "word": "handboeken"}]) == "de handboeken"


def test_forms():
    assert forms(NOUN) == "het handboek · handboeken"
    assert forms(SEPARABLE) == "opstaan · stond op · opgestaan (zijn)"
    assert forms(PHRASE) == "in opstand komen · kwam in opstand · in opstand gekomen (zijn)"


def test_highlight_marks_matched_words_and_escapes():
    assert highlight("Ze staat vroeg op & weg.", "staat op") == "Ze <b>staat</b> vroeg <b>op</b> &amp; weg."


def test_tags():
    assert word_tags(["Verbs: Present"], [SEPARABLE], True) == [
        "DD::Machine_translated", "DD::Separable_verb", "DD::Verb", "DD::Verbs_Present",
    ]
    assert "DD::Separable_verb" not in word_tags([], [PHRASE], False)


def test_article_twins_need_a_the_gloss():
    translations = {
        "man": ["man"], "de man": ["the man"],
        "eten": ["eat (plural)"], "het eten": ["the food, meal"],
        "geheim": ["secret"], "het geheim": ["secret"],
    }
    assert article_twins(translations) == {"man": "de man"}


def test_merged_translations_drop_the_bare_duplicate():
    assert merged_translations(["the man", "husband"], ["man"]) == ["the man", "husband"]
    assert merged_translations(["the light"], ["lamp"]) == ["the light", "lamp"]


def test_distinct_glosses_drop_repeats_from_later_glosses():
    from duolingo_anki.cards import distinct_glosses
    assert distinct_glosses(["see (plural), to see", "to see"]) == ["see (plural), to see"]
    assert distinct_glosses(["go (plural), to go", "going"]) == ["go (plural), to go"]
    assert distinct_glosses(["to swim", "swimming"]) == ["to swim"]
    assert distinct_glosses(["that", "that, which"]) == ["that", "which"]
    assert distinct_glosses(["the glass", "glass"]) == ["the glass"]
    assert distinct_glosses(["books", "to book"]) == ["books", "to book"]


def test_gloss_overrides_replace_and_fail_when_stale():
    import pytest
    from duolingo_anki.cards import corrected
    words = [{"dutch": "de kalender", "translation": "calender", "tag": "Calender"}]
    assert corrected(words, {"de kalender": {"calender": "calendar"}})[0]["translation"] == "calendar"
    with pytest.raises(ValueError, match="calender"):
        corrected([{**words[0], "translation": "calendar"}], {"de kalender": {"calender": "calendar"}})
