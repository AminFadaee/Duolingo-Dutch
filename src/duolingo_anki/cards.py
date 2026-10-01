import html
import re

LEADING_ARTICLE = re.compile(r"^(de|het) (?=\S+$)")
ARTICLE = re.compile(r"^(?:de|het) ")
NOTE = re.compile(r"\([^)]*\)")
ALTERNATIVES = re.compile(r"\s*/\s*")
AFFIX = re.compile(r"^-|\w-(\(|$)")
PATTERN_MARKERS = ("...", "…", "+")
WORD = re.compile(r"[\w'-]+")
TAG_UNSAFE = re.compile(r"[^\w-]+")
TAG_PREFIX = "DD"
PARTS_OF_SPEECH = {
    "noun": "Noun",
    "name": "Name",
    "verb": "Verb",
    "adj": "Adjective",
    "adv": "Adverb",
    "pron": "Pronoun",
    "num": "Number",
    "det": "Determiner",
    "article": "Determiner",
    "prep": "Preposition",
    "prep_phrase": "Phrase",
    "circumpos": "Preposition",
    "conj": "Conjunction",
    "intj": "Interjection",
    "phrase": "Phrase",
}


def display_text(dutch: str, headwords: list[dict]) -> str:
    match = LEADING_ARTICLE.match(dutch)
    if not match or len(headwords) != 1:
        return dutch
    headword = headwords[0]
    article = headword.get("noun", {}).get("article")
    if article in ("de", "het") and headword.get("lemma") == headword["word"] and article != match.group(1):
        return f"{article} {dutch[match.end():]}"
    return dutch


def is_separable(headword: dict) -> bool:
    particle = headword.get("verb", {}).get("particle")
    return bool(particle) and " " not in headword["word"] and headword["word"].startswith(particle)


def is_verb_phrase(headword: dict) -> bool:
    return bool(headword.get("verb", {}).get("particle")) and not is_separable(headword)


def article_twins(translations: dict[str, list[str]]) -> dict[str, str]:
    twins = {}
    for dutch, glosses in translations.items():
        if match := ARTICLE.match(dutch):
            bare = dutch[match.end():]
            if {f"the {gloss.lower()}" for gloss in translations.get(bare, [])} & {gloss.lower() for gloss in glosses}:
                twins[bare] = dutch
    return twins


def merged_translations(glosses: list[str], twin_glosses: list[str]) -> list[str]:
    known = {gloss.lower() for gloss in glosses}
    extra = [gloss for gloss in twin_glosses if f"the {gloss.lower()}" not in known]
    return list(dict.fromkeys(glosses + extra))


def spoken_text(dutch: str) -> str | None:
    if any(marker in dutch for marker in PATTERN_MARKERS) or AFFIX.search(dutch):
        return None
    text = " ".join(NOTE.sub("", dutch).replace("|", "").split())
    return ", ".join(part for part in ALTERNATIVES.split(text) if part) or None


def forms(headword: dict) -> str:
    if noun := headword.get("noun"):
        base = " ".join(part for part in (noun.get("article"), headword["lemma"]) if part)
        return " · ".join(part for part in (base, noun.get("plural"), noun.get("diminutive")) if part)
    if verb := headword.get("verb"):
        infinitive, past, participle = verb["infinitive"], verb.get("past_singular"), verb.get("past_participle")
        if is_verb_phrase(headword):
            fixed = verb["particle"]
            infinitive = headword["word"]
            past = past and f"{past} {fixed}"
            participle = participle and f"{fixed} {participle}"
        if participle and verb.get("auxiliary"):
            participle = f"{participle} ({verb['auxiliary']})"
        return " · ".join(part for part in (infinitive, past, participle) if part)
    if adjective := headword.get("adjective"):
        return " · ".join(part for part in (headword["lemma"], adjective.get("comparative"), adjective.get("superlative")) if part)
    if headword.get("lemma") and headword["lemma"] != headword["word"]:
        return headword["lemma"]
    return ""


def forms_html(headwords: list[dict]) -> str:
    lines = dict.fromkeys(line for headword in headwords if (line := forms(headword)))
    return "<br>".join(html.escape(line) for line in lines)


def highlight(sentence: str, match: str) -> str:
    wanted = {word.lower() for word in WORD.findall(match)}
    parts = []
    position = 0
    for found in WORD.finditer(sentence):
        parts.append(html.escape(sentence[position:found.start()]))
        word = html.escape(found.group())
        parts.append(f"<b>{word}</b>" if found.group().lower() in wanted else word)
        position = found.end()
    parts.append(html.escape(sentence[position:]))
    return "".join(parts)


def tag(*parts: str) -> str:
    return "::".join([TAG_PREFIX, *(TAG_UNSAFE.sub("_", part).strip("_") for part in parts)])


def word_tags(skills: list[str], headwords: list[dict], machine_translated: bool) -> list[str]:
    tags = [tag(skill) for skill in skills]
    tags += [tag(PARTS_OF_SPEECH[pos]) for headword in headwords if (pos := headword.get("pos")) in PARTS_OF_SPEECH]
    if any(is_separable(headword) for headword in headwords):
        tags.append(tag("Separable_verb"))
    if machine_translated:
        tags.append(tag("Machine_translated"))
    return sorted(set(tags))
