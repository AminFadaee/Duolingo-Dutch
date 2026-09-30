import re
import time
from dataclasses import dataclass
from urllib.parse import quote

import httpx

from duolingo_anki.sources import USER_AGENT

WIKTIONARY_API = "https://nl.wiktionary.org/w/api.php"
WIKIPEDIA_API = "https://nl.wikipedia.org/w/api.php"
DUTCH_SECTION = "{{=nld=}}"
EXAMPLE_TEMPLATE = "{{bijv-1|"
SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")
LINK = re.compile(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]")
FORMATTING = re.compile(r"'{2,}")
TEMPLATE = re.compile(r"\{\{[^{}]*\}\}")
SEARCH_RESULTS = 5
RETRIES = 6
RETRY_STATUSES = {429, 503}


@dataclass(frozen=True)
class DutchSentence:
    text: str
    url: str


def template_bodies(text: str, opening: str) -> list[str]:
    bodies = []
    start = text.find(opening)
    while start != -1:
        depth, position = 1, start + len(opening)
        while position < len(text) and depth:
            if text.startswith("{{", position):
                depth, position = depth + 1, position + 2
            elif text.startswith("}}", position):
                depth, position = depth - 1, position + 2
            else:
                position += 1
        bodies.append(text[start + len(opening):position - 2])
        start = text.find(opening, position)
    return bodies


def first_parameter(body: str) -> str:
    depth = 0
    for position, character in enumerate(body):
        depth += {"{": 1, "}": -1, "[": 1, "]": -1}.get(character, 0)
        if character == "|" and depth == 0:
            return body[:position]
    return body


def plain_text(wikitext: str, page: str) -> str:
    text = wikitext.replace("{{pn}}", page)
    text = LINK.sub(r"\1", text)
    while TEMPLATE.search(text):
        text = TEMPLATE.sub("", text)
    return " ".join(FORMATTING.sub("", text).split())


class Wikis:
    def __init__(self):
        self.client = httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=30, follow_redirects=True)

    def query(self, api: str, **params) -> dict:
        for attempt in range(RETRIES):
            response = self.client.get(api, params={"format": "json", "formatversion": 2, **params})
            if response.status_code not in RETRY_STATUSES or attempt == RETRIES - 1:
                break
            time.sleep(float(response.headers.get("retry-after", 2 ** attempt)))
        response.raise_for_status()
        return response.json()

    def wiktionary_examples(self, page: str) -> list[DutchSentence]:
        data = self.query(WIKTIONARY_API, action="parse", page=page, prop="wikitext", redirects=1)
        wikitext = data.get("parse", {}).get("wikitext", "")
        if DUTCH_SECTION not in wikitext:
            return []
        dutch = wikitext.split(DUTCH_SECTION, 1)[1].split("{{=", 1)[0]
        url = f"https://nl.wiktionary.org/wiki/{quote(page)}"
        return [
            DutchSentence(text, url)
            for body in template_bodies(dutch, EXAMPLE_TEMPLATE)
            if (text := plain_text(first_parameter(body), page))
        ]

    def wikipedia_sentences(self, phrase: str) -> list[DutchSentence]:
        search = self.query(WIKIPEDIA_API, action="query", list="search", srsearch=f'"{phrase}"', srlimit=SEARCH_RESULTS)
        sentences = []
        for result in search["query"]["search"]:
            pages = self.query(
                WIKIPEDIA_API, action="query", prop="extracts", explaintext=1, pageids=result["pageid"]
            )["query"]["pages"]
            url = f"https://nl.wikipedia.org/wiki/{quote(result['title'].replace(' ', '_'))}"
            for page in pages:
                sentences += [DutchSentence(text, url) for text in SENTENCE_BREAK.split(page.get("extract", ""))]
        return sentences
