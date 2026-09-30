from duolingo_anki.english import content_words
from duolingo_anki.sentences import Candidate, FormMatch, Sentence, SentenceIndex, candidates, rank

SENTENCES = {
    1: Sentence(1, "Ze staat vroeg op.", ""),
    2: Sentence(2, "Wanneer moet je opstaan?", ""),
    3: Sentence(3, "Ik ben geen kussen!", ""),
    4: Sentence(4, "Hij wil haar kussen.", ""),
    5: Sentence(5, "Zij stonden naast de deur.", ""),
}
INDEX = SentenceIndex(SENTENCES)


def test_split_form_needs_particle_after_verb():
    assert INDEX.find("staat op", "op") == {1}
    assert INDEX.find("stonden op", "op") == set()


def test_phrase_must_be_contiguous():
    assert INDEX.find("haar kussen", None) == {4}
    assert INDEX.find("wil kussen", None) == set()


def test_candidates_rank_split_before_taught_before_other():
    headword = {"word": "opstaan", "forms": ["opstaan", "staat op", "stonden op"], "verb": {"particle": "op"}}
    found = {candidate.sentence.id: candidate.form for candidate in candidates(INDEX, [headword])}
    assert found == {1: FormMatch.SPLIT, 2: FormMatch.TAUGHT}


def test_rank_prefers_matching_meaning():
    meaning = content_words("to kiss")
    pillow = rank(Candidate(SENTENCES[3], "kussen", FormMatch.TAUGHT), "I am not a pillow.", meaning, INDEX, set())
    kiss = rank(Candidate(SENTENCES[4], "kussen", FormMatch.TAUGHT), "He wants to kiss her.", meaning, INDEX, set())
    assert kiss < pillow


def test_rank_prefers_single_sentences():
    index = SentenceIndex({
        1: Sentence(1, "Je moet op deze knop drukken. Dan gaat hij aan.", ""),
        2: Sentence(2, "Je moet op deze knop drukken.", ""),
    })
    two = rank(Candidate(index.sentences[1], "drukken", FormMatch.TAUGHT), "", set(), index, set())
    one = rank(Candidate(index.sentences[2], "drukken", FormMatch.TAUGHT), "", set(), index, set())
    assert one < two
