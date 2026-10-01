# Duolingo Dutch

An Anki deck of the vocabulary of Duolingo's Dutch (Netherlands) course, and the pipeline that builds it: 2,747
words and phrases from all 117 skills, each with its grammatical forms, a real example sentence with an English
translation, and Dutch audio for both.

**Get the deck:** [on AnkiWeb](https://ankiweb.net/shared/info/400760191), or download `duolingo_dutch.apkg` from the
[latest release](https://github.com/AminFadaee/Duolingo-Dutch/releases/latest).

Everything is produced by a reproducible pipeline from public sources. Running it at the same moment gives the
same data; running it later picks up upstream edits. Not affiliated with Duolingo.

## The deck

Every word has three cards:

| Card | Front | Back |
|---|---|---|
| Dutch to English | the Dutch word, read aloud | the English meaning |
| English to Dutch | the English meaning, and a box to type the Dutch | your spelling checked against the Dutch word, which is read aloud |
| Listening | the Dutch word read aloud, a box to type what you hear, and a button to hear the example sentence as a hint | your spelling checked, the Dutch word and its meaning |

The typed answer is the word as spoken: *opstaan* for *op\|staan*, *de bon, het bonnetje* for *de bon / het
bonnetje*. Grammar patterns and affixes such as *noch…noch* and *schoon-* have no typed answer and no listening card.

Every back also shows the article and forms (*het huis · huizen · huisje*, *opstaan · stond op · opgestaan*) and the
example sentence with its translation, the word highlighted, and a button that plays the sentence. The sentence never
plays on its own.

New cards follow the course, starting with Basics 1. Everything is in one deck with no subdecks; notes are tagged
instead:

- Duolingo skill: `DD::Basics_1`, `DD::Food_2`, …
- word type: `DD::Noun`, `DD::Verb`, `DD::Adjective`, `DD::Separable_verb`, …
- `DD::Machine_translated` for the 2% of sentences whose translation is machine-made

To study one skill, create a filtered deck (Tools → Create Filtered Deck) and search for
`deck:"Duolingo Dutch" tag:DD::Food_1`. To skip cards, suspend them rather than deleting them: deleted cards come
back when you import an update. Updates keep your progress.

## Pipeline

| Step | Command | Reads | Writes | Source |
|---|---|---|---|---|
| Scrape | `scrape` | | `words.json` | [Duolingo wiki](https://duolingo.fandom.com/wiki/Dutch_(Netherlands)) skill pages |
| Lexicon | `lexicon` | `words.json` | `lexicon.json` | English Wiktionary via [kaikki.org](https://kaikki.org/dictionary/Dutch/) |
| Sentences | `sentences` | `words.json`, `lexicon.json` | `sentences.json` | Tatoeba, OPUS, Dutch Wiktionary and Wikipedia |
| Audio | `audio` | `sentences.json`, `lexicon.json` | `audio.json`, `audio/` | [Supertonic 3](https://huggingface.co/Supertone/supertonic-3) |
| Deck | `deck` | all of the above | `build/duolingo_dutch.apkg` | |

All data lives in `data/` and is committed, audio included, so building the deck only packages it. The built
deck in `build/` is not committed.

Duolingo only provides the word list, its English glosses and the skill tags. Grammar (article, plural, verb
forms) comes from Wiktionary, which an official word list check showed to be the more accurate of the two.

### Scrape

Reads the vocabulary listed under each skill's *Lesson* headings through the wiki's MediaWiki API.

### Lexicon

Looks every word up in Wiktionary and records its base word and part of speech, plus the article, plural and
diminutive of nouns; past forms, participle, auxiliary and separable particle of verbs; and the comparative and
superlative of adjectives. Inflected entries such as *leest* point to their base word (*lezen*), and verb phrases
such as *in opstand komen* are treated like separable verbs. When Wiktionary has several entries for a word, the
one whose meaning matches the Duolingo gloss wins.

### Sentences

Finds one example sentence per word, trying these sources in order and stopping at the first that has one:

1. **Tatoeba**, human translation, directly or through a third language.
2. **OPUS** parallel corpora (wikimedia, GlobalVoices), human translation. The English side must contain every
   word of the gloss.
3. **Human-written Dutch** from Tatoeba, the Dutch Wiktionary or Dutch Wikipedia, translated by
   [Opus-MT](https://huggingface.co/Helsinki-NLP/opus-mt-nl-en) at a pinned revision. These examples record the
   model in `translated_by`.

Sentences match any form of the word, including split separable verbs (*Ze staat vroeg op*), grammar patterns
(*noch…noch*, *iets …s*) and prefixes or suffixes (*schoon-*, *-talig*). Among the matches, the pick prefers a
translation that carries the word's meaning, then the form being taught, then a short single sentence made of
words that are also in the deck. Words without any example sentence are dropped.

### Audio

Speaks every word and its example sentence. Each card gets voice F1 or M1, chosen from a hash of the word, and
synthesis is seeded from a hash of the text, so the same input produces the same MP3 byte for byte. Clips are named
after a hash of their voice and text, so an update only adds the clips whose text changed. `audio.json` lists them.

## Usage

Requires [uv](https://docs.astral.sh/uv/). It installs Python 3.13 and the dependencies on first run. The heavy
pipeline packages (PyTorch, transformers, Supertonic) sit in the `pipeline` dependency group, which is installed by
default; `uv sync --no-default-groups` skips them when only packaging the committed data.

```sh
uv run duolingo-anki scrape
uv run duolingo-anki lexicon
uv run duolingo-anki sentences
uv run duolingo-anki audio
uv run duolingo-anki deck
```

Each step reads the previous step's file, so any step can be rerun on its own. Every command takes `--help`.

Downloads are cached in `.cache/` (about 550 MB) and fetched again only when the upstream file changes. The models
go to the usual Hugging Face and Supertonic caches (about 700 MB together). On a 6-core laptop CPU the lexicon
takes seconds, the sentences about 5 minutes, the audio a little over an hour and the deck under a minute. No GPU
is needed.

## Releasing

Releases are built by GitHub Actions from the committed data, so no pipeline step runs in CI.

```sh
uv run duolingo-anki scrape
uv run duolingo-anki lexicon
uv run duolingo-anki sentences
uv run duolingo-anki audio
git add data
git commit -m "Update data"
git push
git tag v$(date +%Y.%m.%d)
git push origin v$(date +%Y.%m.%d)
```

Versions are dates, so the version says how fresh the data is. Pushing the tag builds `duolingo_dutch.apkg` and
publishes it as a release under that tag. The AnkiWeb copy is updated separately by sharing the deck again from Anki.

## Development

```sh
uv run pytest
```

## License

The code is under the [MIT license](LICENSE). The generated data and audio are under
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/), as required by the sources they are built from;
see [CREDITS.md](CREDITS.md).
