# Duolingo Dutch

Vocabulary from Duolingo's Dutch (Netherlands) course, turned into material for Anki flash cards: each word comes
with its grammatical forms, a real example sentence with an English translation, and Dutch audio for both.

Everything is produced by a reproducible pipeline from public sources. Running it at the same moment gives the
same data; running it later picks up upstream edits.

## Pipeline

| Step | Command | Reads | Writes | Source |
|---|---|---|---|---|
| Scrape | `scrape` | | `words.json` | [Duolingo wiki](https://duolingo.fandom.com/wiki/Dutch_(Netherlands)) skill pages |
| Lexicon | `lexicon` | `words.json` | `lexicon.json` | English Wiktionary via [kaikki.org](https://kaikki.org/dictionary/Dutch/) |
| Sentences | `sentences` | `words.json`, `lexicon.json` | `sentences.json` | Tatoeba, OPUS, Dutch Wiktionary and Wikipedia |
| Audio | `audio` | `sentences.json` | `audio.json`, `audio/` | [Supertonic 3](https://huggingface.co/Supertone/supertonic-3) |

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
synthesis is seeded from a hash of the text, so the same input produces the same MP3 byte for byte. The clips are
not committed; `audio.json` lists them.

## Usage

Requires [uv](https://docs.astral.sh/uv/). It installs Python 3.13 and the dependencies on first run.

```sh
uv run duolingo-anki scrape
uv run duolingo-anki lexicon
uv run duolingo-anki sentences
uv run duolingo-anki audio
```

Each step reads the previous step's file, so any step can be rerun on its own. Every command takes `--help`.

Downloads are cached in `.cache/` (about 550 MB) and fetched again only when the upstream file changes. The models
go to the usual Hugging Face and Supertonic caches (about 700 MB together). On a 6-core laptop CPU the lexicon
takes seconds, the sentences about 5 minutes and the audio a little over an hour. No GPU is needed.

## Development

```sh
uv run pytest
```

## License

The code is under the [MIT license](LICENSE). The generated data and audio are under
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/), as required by the sources they are built from;
see [CREDITS.md](CREDITS.md).
