import re

SUFFIXES = ("ing", "ed", "es", "s", "d")
STOPWORDS = {
    "the", "an", "to", "of", "or", "and", "for", "with", "from", "that", "this", "one", "someone", "something",
    "person", "singular", "plural", "form", "used", "especially",
}


def variants(token: str) -> set[str]:
    return {token} | {
        token.removesuffix(suffix)
        for suffix in SUFFIXES
        if token.endswith(suffix) and len(token) - len(suffix) >= 2
    }


def content_words(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z]+", text.lower()) if len(token) >= 2 and token not in STOPWORDS}


def shared_words(words: set[str], text: str) -> int:
    text_variants = {variant for token in content_words(text) for variant in variants(token)}
    return sum(1 for word in words if variants(word) & text_variants)
