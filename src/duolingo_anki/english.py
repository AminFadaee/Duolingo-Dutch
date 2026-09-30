import re
from dataclasses import dataclass

SUFFIXES = ("ing", "ed", "es", "s", "d")
STOPWORDS = {
    "the", "an", "to", "of", "or", "and", "for", "with", "from", "that", "this", "one", "someone", "something",
    "person", "singular", "plural", "form", "used", "especially",
}
ALTERNATIVES = re.compile(r"[,/;]|\bor\b")
NOTES = re.compile(r"\([^)]*\)")
DUTCH_FUNCTION_WORDS = {"het", "een", "van", "de", "niet", "zijn", "voor", "dat", "ook", "naar"}
FUNCTION_WORDS = {
    "in", "on", "at", "by", "as", "is", "it", "its", "my", "me", "we", "he", "she", "his", "her", "you", "your",
    "they", "them", "our",
}


def variants(token: str) -> set[str]:
    return {token} | {
        token.removesuffix(suffix)
        for suffix in SUFFIXES
        if token.endswith(suffix) and len(token) - len(suffix) >= 2
    }


def content_words(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z]+", text.lower()) if len(token) >= 2 and token not in STOPWORDS}


def meaning_words(text: str) -> set[str]:
    return content_words(text) - FUNCTION_WORDS


def shared_words(words: set[str], text: str) -> int:
    text_variants = {variant for token in content_words(text) for variant in variants(token)}
    return sum(1 for word in words if variants(word) & text_variants)


def looks_english(text: str) -> bool:
    return len(set(re.findall(r"[a-z]+", text.lower())) & DUTCH_FUNCTION_WORDS) < 2


@dataclass(frozen=True)
class Meaning:
    words: frozenset[str] = frozenset()
    alternatives: tuple[frozenset[str], ...] = ()

    @classmethod
    def of(cls, translations: list[str]) -> "Meaning":
        words = frozenset().union(*(meaning_words(translation) for translation in translations))
        alternatives = dict.fromkeys(
            frozenset(found)
            for translation in translations
            for part in ALTERNATIVES.split(NOTES.sub(" ", translation))
            if (found := meaning_words(part))
        )
        return cls(words, tuple(alternatives))

    def carried_by(self, text: str, strict: bool = False) -> bool:
        if not self.words:
            return True
        if strict and self.alternatives:
            return any(shared_words(alternative, text) == len(alternative) for alternative in self.alternatives)
        return bool(shared_words(self.words, text))
