import re
from dataclasses import dataclass
from enum import IntEnum

TOKEN = re.compile(r"[\w'-]+")
ARTICLE_BEFORE_PHRASE = re.compile(r"^(?:de|het) (?=\S+ \S)", re.IGNORECASE)
AFFIX_ALTERNATIVES = re.compile(r"^(\w+)-\(([^)]*)\)$")
PATTERN_PARTS = re.compile(r"(\.\.\.|\+)")
GAP = r"(?: \S+)+?"
PRESENT_PARTICIPLE = r" \S+ende?"
MIN_AFFIX_REST = 3


def tokens(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


class FormMatch(IntEnum):
    SPLIT = 0
    TAUGHT = 1
    OTHER = 2
    LOOSE = 3


@dataclass(frozen=True)
class Rule:
    label: str
    form: FormMatch
    anchors: tuple[str, ...]

    def matches(self, sentence: list[str]) -> bool:
        raise NotImplementedError


@dataclass(frozen=True)
class Phrase(Rule):
    head: tuple[str, ...]
    tail: tuple[str, ...] = ()

    def matches(self, sentence: list[str]) -> bool:
        size = len(self.head)
        for start in range(len(sentence) - size + 1):
            if tuple(sentence[start:start + size]) == self.head:
                if not self.tail or contains(sentence[start + size:], self.tail):
                    return True
        return False


@dataclass(frozen=True)
class Pattern(Rule):
    regex: re.Pattern

    def matches(self, sentence: list[str]) -> bool:
        return self.regex.search(f" {' '.join(sentence)} ") is not None


@dataclass(frozen=True)
class Affix(Rule):
    prefix: str = ""
    suffix: str = ""

    def matches(self, sentence: list[str]) -> bool:
        return any(
            token.startswith(self.prefix) and token.endswith(self.suffix)
            and len(token) >= len(self.prefix) + len(self.suffix) + MIN_AFFIX_REST
            for token in sentence
        )


def contains(sentence: list[str], phrase: tuple[str, ...]) -> bool:
    return any(tuple(sentence[i:i + len(phrase)]) == phrase for i in range(len(sentence) - len(phrase) + 1))


def pattern_rule(dutch: str) -> Pattern:
    regex, anchors, previous, before = "", [], "", ""
    for chunk in PATTERN_PARTS.split(dutch):
        if chunk in ("...", "+"):
            previous = chunk
            continue
        word_ending = previous == "..." and before.endswith(" ") and chunk and not chunk[0].isspace()
        before = chunk
        if word_ending:
            suffix, _, chunk = chunk.partition(" ")
            regex += rf" \S{{{MIN_AFFIX_REST},}}{re.escape(suffix)}"
        elif previous == "...":
            regex += GAP
        if chunk.strip() == "P.P.":
            regex += PRESENT_PARTICIPLE
        else:
            words = tokens(chunk)
            anchors += words
            regex += "".join(f" {re.escape(word)}" for word in words)
        previous = ""
    if previous == "...":
        regex += GAP
    return Pattern(dutch, FormMatch.LOOSE, tuple(anchors), re.compile(regex + "(?= )"))


def affix_rule(dutch: str) -> Rule | None:
    if match := AFFIX_ALTERNATIVES.match(dutch):
        words = tuple(match.group(1) + alternative for alternative in match.group(2).split("/"))
        return Pattern(dutch, FormMatch.TAUGHT, (), re.compile("|".join(f" {re.escape(word)} " for word in words)))
    if " " in dutch:
        return None
    if dutch.endswith("-"):
        return Affix(dutch, FormMatch.LOOSE, (), prefix=dutch[:-1].lower())
    if dutch.startswith("-"):
        return Affix(dutch, FormMatch.LOOSE, (), suffix=dutch[1:].lower())
    return None


def phrase_rule(form: str, particle: tuple[str, ...], rank: FormMatch) -> Phrase | None:
    form_tokens = tuple(tokens(form))
    if not form_tokens:
        return None
    if rank == FormMatch.SPLIT:
        head, tail = form_tokens[:-len(particle)], particle
        return Phrase(form, rank, form_tokens, head, tail)
    return Phrase(form, rank, form_tokens, form_tokens)


def build_rules(dutch: str, headwords: list[dict]) -> list[Rule]:
    if "..." in dutch or "+" in dutch:
        return [pattern_rule(dutch)]
    if affix := affix_rule(dutch):
        return [affix]
    rules = {}
    for headword in headwords:
        word = headword["word"]
        particle = tuple(tokens(headword.get("verb", {}).get("particle", "")))
        forms = [word, *headword.get("forms", []), ARTICLE_BEFORE_PHRASE.sub("", word)]
        for form in dict.fromkeys(forms):
            form_tokens = tuple(tokens(form))
            if particle and len(form_tokens) > len(particle) and form_tokens[-len(particle):] == particle:
                rank = FormMatch.SPLIT
            elif form.lower() == word.lower():
                rank = FormMatch.TAUGHT
            else:
                rank = FormMatch.OTHER
            rule = phrase_rule(form, particle, rank)
            if rule and (rule.label not in rules or rank < rules[rule.label].form):
                rules[rule.label] = rule
    return list(rules.values())
