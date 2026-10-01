from duolingo_anki.cards import display_text, forms, highlight, word_tags

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
