import json
import sys
from dataclasses import asdict, dataclass
from urllib.parse import unquote

import httpx
from lxml import html

API_URL = "https://duolingo.fandom.com/api.php"
COURSE_PAGE = "Dutch_(Netherlands)"
SKILL_PAGE = "Dutch_(NL)_Skill:{}"
USER_AGENT = "duolingo-anki (+https://github.com/AminFadaee/Duolingo-Dutch)"
LESSON_ITEMS = '//ul/li[preceding::h2[1]/span[@class="mw-headline"][starts-with(normalize-space(), "Lesson")]]'
NESTED_LISTS = {"ul", "ol"}


@dataclass(frozen=True)
class Word:
    dutch: str
    translation: str
    tag: str


def fetch(client: httpx.Client, page: str) -> html.HtmlElement | None:
    params = {"action": "parse", "page": page, "prop": "text", "format": "json", "formatversion": 2}
    try:
        response = client.get(API_URL, params=params)
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError) as error:
        print(f"Fetching {page} failed: {error}", file=sys.stderr)
        return None
    if "error" in data:
        print(f"Fetching {page} failed: {data['error']['info']}", file=sys.stderr)
        return None
    return html.fromstring(data["parse"]["text"])


def skill_tags(client: httpx.Client) -> list[str]:
    page = fetch(client, COURSE_PAGE)
    if page is None:
        return []
    return [unquote(href.split(":", 1)[1]) for href in page.xpath('//div[@class="hlist"]/a/@href')]


def own_text(item: html.HtmlElement) -> str:
    parts = [item.text or ""]
    for child in item:
        if isinstance(child.tag, str) and child.tag not in NESTED_LISTS:
            parts.append(child.text_content())
        parts.append(child.tail or "")
    return " ".join("".join(parts).split())


def skill_words(client: httpx.Client, tag: str) -> list[Word]:
    page = fetch(client, SKILL_PAGE.format(tag))
    if page is None:
        return []
    words = []
    for item in page.xpath(LESSON_ITEMS):
        text = own_text(item)
        if "=" in text:
            dutch, translation = text.split("=", 1)
            words.append(Word(dutch.strip(), translation.strip(), tag))
    return words


def main() -> None:
    headers = {"User-Agent": USER_AGENT}
    with httpx.Client(headers=headers, follow_redirects=True, timeout=10) as client:
        words = [word for tag in skill_tags(client) for word in skill_words(client, tag)]
    json.dump([asdict(word) for word in words], sys.stdout, ensure_ascii=False, indent=2)
    print()
