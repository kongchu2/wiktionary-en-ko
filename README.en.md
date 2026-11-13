# Wiktionary-en-ko: an English→Korean dictionary for Yomitan

[한국어](README.md) · English

An **English→Korean** dictionary for [Yomitan](https://github.com/yomidevs/yomitan).
It keeps the headwords, parts of speech and sense divisions of the [English Wiktionary](https://en.wiktionary.org/) (through the [kaikki.org](https://kaikki.org/) extraction) and translates each sense into Korean with an LLM.

> 107,824 entries (219,495 senses), translated by Claude Haiku.

## Coverage

| Scope | Headwords | Entries | Senses |
|---|---|---|---|
| Single words: the top 50,000 by [wordfreq](https://github.com/rspeer/wordfreq) frequency, hyphenated compounds (`long-term`) included | 47,096 | 69,760 | 165,748 |
| Phrasal verbs: one of those verbs + particles (`give up`, `look forward to`) | — | 4,523 | 10,040 |
| Other multi-word headwords (`of course`, `fall in love`, `ice cream`) | — | 33,541 | 43,707 |
| Total | | 107,824 | 219,495 |

- Inflected forms (`went`, `children`, `years`) and other spellings (`favorite` → favourite) are not translated separately; they link to the base entry (`source/forms.jsonl`, 59,321 links, including `fell in love` → fall in love). Regular forms that Yomitan resolves by itself (`plans`) are not in there.
- Where only an inflected form is inside the top 50,000 (`relegated` → relegate, `microorganisms` → microorganism), the base word is included.
- Abbreviations and contractions (`it's`, `Mr`, `CIA`) are included only where the entry has no ordinary sense, with at most 2 expansions each.
- Character, symbol and affix entries are left out, one-letter headwords too (only the article `a` and the pronoun `I` stay), and so are senses marked obsolete, archaic, rare, dialectal, dated, nonstandard or misspelling.
- Proper names (`London`, `March`, `English`) are included, but each spelling keeps at most 1 surname sense, 1 given-name sense and 2 place senses. Namesake places listed under "a number of places in …" are dropped.
- Capitalised variants of a lowercase word (`She` the ethnic group, `TO` the verb, `Grew` the surname) are set aside in `source/deferred.jsonl` (8,783 entries). They are neither translated nor built. `I`, `US`, `IT`, `AM`, `ID` and proper names with a meaning of their own (`March`, `Turkey`) stay.
- Multi-word headwords and hyphenated compounds have two to four words, each inside the top 50,000. Nouns and proper names are too many, so only those with translations into at least 3 languages on Wiktionary are included. The same test applies to headwords made only of very common words (`to the`, `for you`), and headwords with a slot (`pull someone's leg`) are left out.
- Senses with an example sentence on Wiktionary (22% of all, 47% for the top 3,000 words) show one English example under the gloss. Examples are not translated.
- The selection is stored in `source/entries.jsonl`, and the build reads only that file.

## Install

1. Download `wiktionary-en-ko.zip` from [Releases](../../releases/latest).
2. In Yomitan → Settings → General, set the language to English.
3. In Yomitan → Settings → Dictionaries → Import, load the zip.

Inflected forms and phrasal verbs are found too (`running` → run, `pick it up` → pick up).

Setting Yomitan → Settings → Lookup resolution to Word is recommended. With the default (Letter), prefix matches such as `wen` and `we` are listed under `went`.

## Translation quality

- The Korean glosses are machine-translated by an LLM (Claude Haiku), so some are wrong. Each entry has the English original from Wiktionary folded underneath; use it to check.
- Wiktionary lists senses in historical order, so the first sense is often an old one (`with` "against", `team` "draught animals"). For the 20,000 most frequent spellings (11,147 of them), Claude Sonnet reordered parts of speech and senses by how common they are in modern English (`translations/order.jsonl`, hand-editable). Minor entries of spellings that are normally read as an inflected form (`years` "a very long time", `goals` "admirable") are hidden, so that the base word (year, goal) comes first.
- Entries the model was unsure about carry the note `※ 자동 번역 신뢰도 낮음` (low confidence). That is 7,261 entries, 6.7%.
- The only quality check so far was a blind test of 300 entries (883 senses), also graded by Claude: about 2% of the senses had a problem, most of them an imprecise gloss and a few a wrong meaning. Because a model graded a model, the real rate is probably higher. Entries with more than 12 senses were not in the test.
- To fix a translation, edit the `s` field (the list of Korean glosses per sense) on that entry's line in `translations/terms.jsonl`.

## Building it yourself

You need Python 3.9 or later, and for translating, the [Claude Code](https://claude.com/claude-code) CLI (`claude`).

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

.venv/bin/python -m enko fetch                         # download the Yomitan schemas
.venv/bin/python -m enko translate tags                # Korean labels for part-of-speech and usage tags
.venv/bin/python -m enko translate terms --limit 1000  # translate untranslated entries in frequency order (resumable)
.venv/bin/python -m enko translate order --model sonnet --max-rank 20000  # order the parts of speech and senses of the top spellings
.venv/bin/python -m enko build                         # dist/wiktionary-en-ko.zip
.venv/bin/python -m enko validate                      # check against the Yomitan schemas and the deinflection rules
.venv/bin/python -m enko review -n 200                 # write a review sample to review/sample.md
.venv/bin/python -m enko status                        # progress
node tools/lookup.mjs went "fell in love"                # look the zip up with Yomitan's own lookup code
node tools/lookup.mjs --text article.txt --word         # hover every word of a text, collect what is not found
```

- The two scripts in `tools/` need the [Yomitan](https://github.com/yomidevs/yomitan) source in `data/yomitan` (`git clone --depth 1`; no npm install). `select` uses it too, to tell which inflected forms Yomitan resolves by itself; without it, every link is kept.

- `build --include-untranslated` also includes untranslated entries, with their English definitions.
- To redo the selection, run `python -m enko select`. It downloads the kaikki English dump (about 530 MB) into `data/raw/` if it is not there. Entries whose senses changed are re-translated on the next `translate` run and are left out of the build until then.
- GitHub Actions (`.github/workflows/release.yml`) rebuilds when `translations/`, `source/` or `enko/` changes, and creates a release only when the content changed. Translation runs locally; commit `translations/`.

## License

- Code (`enko/`, `.github/`): [MIT](LICENSE).
- Dictionary data (`source/`, `translations/`, the built zip): [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
  It is a derivative of the English Wiktionary, and the machine-readable data comes from [Wiktextract](https://kaikki.org/).
- Frequency data used to pick the entries: [wordfreq](https://github.com/rspeer/wordfreq) (CC BY-SA 4.0). It is not part of the built dictionary.
