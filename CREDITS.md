# Credits and data license

The generated data (`words.json`, `lexicon.json`, `sentences.json`, `audio.json`) and the audio clips are licensed
under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Several sources below are share-alike, so
anything built from this data must be shared under the same license with attribution.

Each example sentence in `sentences.json` names its `source` and, where the source has one, the `url` of the
sentence or page, the `translation_url` and the `authors`.

## Sources

| Source | Used for | License |
|---|---|---|
| [Duolingo wiki](https://duolingo.fandom.com/wiki/Dutch_(Netherlands)) (Fandom) | word list, English glosses, skill tags | [CC BY-SA](https://www.fandom.com/licensing) |
| [English Wiktionary](https://en.wiktionary.org/), extracted by [kaikki.org](https://kaikki.org/dictionary/Dutch/) | articles, plurals, verb and adjective forms | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) |
| [Tatoeba](https://tatoeba.org/) | example sentences and their translations | [CC BY 2.0 FR](https://creativecommons.org/licenses/by/2.0/fr/), some sentences [CC0](https://creativecommons.org/publicdomain/zero/1.0/) |
| [OPUS](https://opus.nlpl.eu/) wikimedia corpus | example sentences and their translations | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) |
| [OPUS](https://opus.nlpl.eu/) GlobalVoices corpus, from [Global Voices](https://globalvoices.org/) | example sentences and their translations | [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/) |
| [Dutch Wiktionary](https://nl.wiktionary.org/) | Dutch example sentences | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) |
| [Dutch Wikipedia](https://nl.wikipedia.org/) | Dutch example sentences | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) |

OPUS asks users of its corpora to cite J. Tiedemann, 2012, *Parallel Data, Tools and Interfaces in OPUS*, LREC
2012.

## Models

| Model | Used for | License |
|---|---|---|
| [Helsinki-NLP/opus-mt-nl-en](https://huggingface.co/Helsinki-NLP/opus-mt-nl-en) | translating Dutch sentences that have no human translation | [Apache 2.0](https://www.apache.org/licenses/LICENSE-2.0) |
| [Supertone Supertonic 3](https://huggingface.co/Supertone/supertonic-3) | Dutch speech | Model [OpenRAIL-M](https://huggingface.co/Supertone/supertonic-3/blob/main/LICENSE), SDK MIT |

Supertone claims no rights in audio generated with Supertonic, but its license forbids certain uses of the output
(its Attachment A, for example disinformation or impersonation). Those restrictions apply to anyone using the
audio.
