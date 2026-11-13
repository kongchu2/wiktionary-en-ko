"""English Wiktionary (kaikki.org / Wiktextract) helpers: entry selection, ranking, prompt text."""
import gzip
import hashlib
import json
import re
import subprocess
from collections import Counter

from .paths import DEFERRED, DUMP, DUMP_VERSION, ENTRIES, FORMS, ROOT, SOURCE, SOURCE_VERSION

TOP_WORDS = 50000  # single words: the wordfreq top N
SKIP_POS = {"character", "symbol", "prefix", "suffix", "infix", "interfix", "circumfix", "affix", "combining_form"}
# One-character headwords are letter names, numeral symbols and slang (p: "the sixteenth numeral symbol"), and
# with letter-by-letter scanning Yomitan lists them under every word that starts with that letter.
KEEP_LETTERS = {("a", "article"), ("I", "pron")}
# Senses a learner's dictionary can do without; dropping them cuts the sense count by about 30%.
SKIP_TAGS = {"obsolete", "archaic", "rare", "dialectal", "dated", "nonstandard", "misspelling"}
FORM_TAGS = {"form-of", "alt-of"}
# A link costs nothing to translate, so dated and regional spellings may link; Wiktextract also reads
# "Non-Oxford British standard spelling" (recognise) as nonstandard.
LINK_SKIP_TAGS = {"obsolete", "archaic", "misspelling"}
SYMBOL_WORD = re.compile(r"[A-Za-z]{2,}$")  # km, cm, Fe: symbols that are read as words
# "X is short for Y" senses (CIA, it's, Mr) are translated when the entry has no ordinary sense; adding them
# to entries that do would re-translate 900 common words for little gain. Other form-of and alt-of senses
# (went, favorite) become links to the base word instead, see `_links`.
ABBR_TAGS = {"abbreviation", "initialism", "acronym", "contraction", "clipping", "ellipsis"}
MIN_ALT = 3  # other-spelling links from one or two letters (fa → for, u → you) are noise under longer words
# Inflection tags worth showing to the order editor (plural of year, past of go).
FORM_WORDS = {"plural", "past", "participle", "present", "gerund", "third-person", "singular", "comparative", "superlative"}
MAX_ABBR = 2  # per entry: CIA has eight expansions, and the third is already the Culinary Institute of America
KEEP_CAPS = {"I", "US", "IT", "AM", "ID"}  # capitalised variants of a lowercase headword that are kept anyway
# Words that can follow a verb in a phrasal verb (Yomitan's particle and preposition lists).
PARTICLES = set(
    "aback aboard about above across after against ahead along alongside among apart around as aside astray at away "
    "back before behind below beneath besides between beyond by close down even for forth forward forwards from home "
    "in inside instead into near of off on onto open opposite out outside over overhead past round since through "
    "throughout to together toward towards under underneath up upon way with within without".split()
)
# Other multi-word headwords (of course, fall in love, ice cream): two to four words, each in the top N.
# Nouns and names are far too many (98,000) and have no frequency data, so they need translations into at
# least MIN_LANGS languages on Wiktionary, as a sign that the term is in real use.
MAX_WORDS = 4
MIN_LANGS = 3
LISTED_POS = {"noun", "name"}
# The same test for headwords made only of very common words (to the, for you, is it): Yomitan shows the
# longest match first, so a junk entry there sits on top of "to" all the time. "as if" and "at all" pass.
COMMON_RANK = 300
# Headwords with a slot (pull someone's leg) never occur in running text as written.
PLACEHOLDERS = {"one's", "someone", "someone's", "something", "something's", "somebody", "somebody's", "oneself"}
# part of speech -> Yomitan deinflection condition
RULES = {"verb": "v", "noun": "n", "name": "n", "adj": "adj", "adv": "adv"}
HANGUL = re.compile(r"[가-힣]")
MAX_EXAMPLE = 120

# Proper names: most senses are namesakes ("A city in Ohio", "A surname"), so keep only a few per entry.
_PLACE = (
    r"(city|cities|town|village|hamlet|community|communities|suburb|county|counties|river|township|settlement"
    r"|locality|localities|neighbou?rhood|parish|municipality|borough|places?|placename|commune|district|island"
    r"|lake|mountain|province|region|area|ward|creek|barangay)"
)
PLACE_LIST = re.compile(r"^(a |an |any of |the name of )?(number of |several |various |numerous )?(\w+ ){0,2}" + _PLACE + r"\b")
PLACE = re.compile(r"^(a |an |the )?([\w-]+ ){0,3}" + _PLACE + r"\b")
NAME_LIMITS = {"surname": 1, "given": 1, "place": 2}  # per spelling


def name_kind(glosses):
    """Classify a proper-name sense: surname, given, place, namesake (a place inside a list of places) or None."""
    first, last = glosses[0].lower(), glosses[-1].lower()
    if re.search(r"\bsurname\b", first + " " + last):
        return "surname"
    if re.search(r"given name|diminutive of|nickname", first + " " + last):
        return "given"
    if len(glosses) > 1 and PLACE_LIST.search(first):
        return "namesake"
    return "place" if PLACE.search(last) else None


def _is_abbr(sense):
    return bool(sense.get("alt_of")) and bool(ABBR_TAGS & set(sense.get("tags", [])))


def _links(entry):
    """(base word, tags) for each sense that only says "past of go" or "US spelling of favourite"."""
    out = []
    for s in entry.get("senses", []):
        tags = s.get("tags", [])
        if LINK_SKIP_TAGS & set(tags) or _is_abbr(s):
            continue
        kind = "form-of" if s.get("form_of") else "alt-of"
        for target in s.get("form_of") or s.get("alt_of") or []:
            if target.get("word"):
                out.append((target["word"], [kind] + sorted(t for t in tags if t not in FORM_TAGS)))
    return out


def _lemma_senses(entry, kinds):
    """`kinds` counts the name senses already kept for this spelling, across its entries (Paris has seven)."""
    out, abbrs = [], []
    for s in entry.get("senses", []):
        # Wiktextract lists topics from specific to broad (mathematics, sciences); the first is enough.
        tags = list(dict.fromkeys(s.get("tags", []) + s.get("topics", [])[:1]))
        if not s.get("glosses") or SKIP_TAGS & set(tags):
            continue
        if _is_abbr(s):
            if len(abbrs) < MAX_ABBR:
                abbrs.append({"g": " › ".join(g.strip() for g in s["glosses"]), "t": [t for t in tags if t not in FORM_TAGS]})
            continue
        if s.get("form_of") or s.get("alt_of") or FORM_TAGS & set(tags):
            continue
        if entry.get("pos") == "name":
            kind = name_kind(s["glosses"])
            kinds[kind] += 1
            if kind == "namesake" or kinds[kind] > NAME_LIMITS.get(kind, 10**9):
                continue
        ex = next((x.get("text", "") for x in s.get("examples", []) if x.get("type") == "example"), "")
        rec = {"g": " › ".join(g.strip() for g in s["glosses"]), "t": tags}
        if ex and len(ex) <= MAX_EXAMPLE and "\n" not in ex:
            rec["ex"] = ex
        out.append(rec)
    if not out and re.search(r"[A-Za-z]", entry.get("word", "")):
        return abbrs, True
    return out, False


def _languages(entry):
    tables = [entry.get("translations", [])] + [s.get("translations", []) for s in entry.get("senses", [])]
    return len({t.get("code") or t.get("lang_code") for table in tables for t in table})


def _hints(entry):
    """Korean words from Wiktionary's translation tables, grouped by the table's sense label."""
    groups = {}
    tables = [entry.get("translations", [])] + [s.get("translations", []) for s in entry.get("senses", [])]
    for table in tables:
        for t in table:
            word = t.get("word") or ""
            if (t.get("code") or t.get("lang_code")) != "ko" or not HANGUL.search(word):
                continue
            words = groups.setdefault(t.get("sense") or "", [])
            if word not in words and len(words) < 4:
                words.append(word)
    return [[label, words] for label, words in list(groups.items())[:12]]


def _tokens(word):
    """Hyphens separate words like spaces do: wordfreq has no "long-term", only "long" and "term"."""
    return [t for t in re.split(r"[\s-]+", word.lower()) if t]


def _skip(word, pos):
    if pos == "symbol":
        return not SYMBOL_WORD.match(word)
    return pos in SKIP_POS or word.startswith("-") or word.endswith("-") or (len(word) == 1 and (word, pos) not in KEEP_LETTERS)


def _wanted(rank):
    """Base words that a top-N spelling points at, with that spelling's rank: microorganisms → microorganism,
    socioeconomic → socio-economic, etc → etc. The base word itself is rarer than its form, or has no rank."""
    wanted = {}
    with gzip.open(DUMP, "rt", encoding="utf-8") as f:
        for line in f:
            if '"form_of"' not in line and '"alt_of"' not in line:
                continue
            e = json.loads(line)
            r = rank.get(e.get("word", "").lower())
            if r is None or _skip(e["word"], e.get("pos", "")):
                continue
            for target, tags in _links(e):
                # Inflections always; other spellings only when they differ by hyphens, full stops or spaces
                # ("with" is also an old spelling of withe, which is no reason to add withe).
                if tags[0] == "form-of" or re.sub(r"[\s.-]", "", target).lower() == e["word"].lower():
                    wanted[target] = min(r, wanted.get(target, r))
    return wanted


def select(top=TOP_WORDS):
    """Read the dump and return (entries worth translating, most useful first; deferred entries; forms)."""
    from wordfreq import top_n_list

    rank = {w: i for i, w in enumerate(top_n_list("en", top))}
    wanted = _wanted(rank)
    out, seen, name_kinds, lowercase, links = [], Counter(), {}, set(), {}
    with gzip.open(DUMP, "rt", encoding="utf-8") as f:
        for n, line in enumerate(f):
            e = json.loads(line)
            word, pos = e.get("word", ""), e.get("pos", "")
            if word == word.lower():
                lowercase.add(word)  # every lowercase spelling in the dump, inflected forms included
            if _skip(word, pos):
                continue
            toks, words = _tokens(word), word.lower().split()
            if not toks:
                continue
            if len(toks) <= MAX_WORDS:
                for target, tags in _links(e):
                    # It → it and She → she only repeat what Yomitan's capitalisation handling does.
                    # "has been" is listed as a spelling of has-been, but in text it is nearly always the verb.
                    spaced = tags[0] == "alt-of" and " " in word and target.replace("-", " ") == word
                    # "is" and "as" are also the plurals of the letters i and a.
                    if len(target) == 1:
                        continue
                    if target.lower() != word.lower() and not spaced and not (tags[0] == "alt-of" and len(word) < MIN_ALT):
                        links.setdefault(word, {}).setdefault((target, pos), tags)
            r = None
            if len(toks) == 1:
                r = rank.get(toks[0])
            elif pos == "verb" and 2 <= len(words) <= 3 and all(t in PARTICLES for t in words[1:]):
                r = rank.get(words[0])
                r = None if r is None else r + top  # phrasal verbs come after all single words
            elif len(toks) <= MAX_WORDS and all(t in rank for t in toks) and not PLACEHOLDERS & set(toks):
                common = max(rank[t] for t in toks) < COMMON_RANK
                if not ((pos in LISTED_POS or common) and _languages(e) < MIN_LANGS):
                    r = 2 * top + max(rank[t] for t in toks)  # and other multi-word headwords after those
            if r is None and word in wanted and len(toks) <= MAX_WORDS:
                r = wanted[word] + (0 if len(toks) == 1 else 2 * top)
            if r is None:
                continue
            senses, abbr_only = _lemma_senses(e, name_kinds.setdefault(word, Counter()))
            if not senses:
                continue
            key = f"{word}|{pos}|{e.get('etymology_number', 0)}"
            seen[key] += 1
            rec = {
                "id": key if seen[key] == 1 else f"{key}|{seen[key]}",
                "w": word,
                "pos": pos,
                "r": r,
                "s": senses,
            }
            hints = _hints(e)
            if hints:
                rec["ko"] = hints
            # A name that is nothing but surnames, given names and places (Grew, Butler, Ripple).
            namesake_only = pos == "name" and all(name_kind(s.get("glosses") or [""]) for s in e["senses"])
            out.append((rec["r"], n, rec, namesake_only, abbr_only))
    out.sort(key=lambda x: x[:2])
    # A capitalised variant borrows the rank of the lowercase word and shows up next to it in Yomitan
    # (She the people on "she", TO the verb, Grew the surname on "grew"). Set these aside.
    # Proper names with a sense of their own (March, Turkey) stay, and so does the pronoun I.
    # Abbreviation-only entries follow the same rule (TOLD, BASE and HELP are acronyms too), except KEEP_CAPS.
    headwords = {
        rec["w"] for _, _, rec, _, abbr_only in out
        if rec["w"] == rec["w"].lower() and not abbr_only and rec["pos"] != "symbol"  # fm must not push FM out
    }
    keep, deferred = [], []
    for _, _, rec, namesake_only, abbr_only in out:
        w = rec["w"]
        # "It." (Italian), "So." (south), "Can." (Canada) would match "it." at the end of every sentence.
        if w.endswith(".") and w.count(".") == 1 and w[:-1].lower() in headwords:
            continue
        if abbr_only:
            variant = w != w.lower() and w.lower() in headwords and w not in KEEP_CAPS
        elif rec["pos"] == "name":
            variant = namesake_only and w.lower() in lowercase
        else:
            variant = w != w.lower() and w.lower() in headwords and w not in KEEP_CAPS
        (deferred if variant else keep).append(rec)
    return keep, deferred, _needed(_forms(links, {rec["w"] for rec in keep}), keep) + _case_links(keep)


def _forms(links, headwords):
    """Links whose base word is in the dictionary, following one more link if needed (favored → favoured → favour)."""
    out = []
    for word in sorted(links):
        found = {}
        for (target, pos), tags in links[word].items():
            if target in headwords:
                found.setdefault((target, pos), tags)
                continue
            for target2, _ in links.get(target, {}):
                if target2 in headwords and target2.lower() != word.lower():
                    found.setdefault((target2, pos), tags)
        out.extend({"w": word, "to": target, "p": pos, "t": tags} for (target, pos), tags in found.items())
    return out


def _node(script, payload):
    try:
        done = subprocess.run(["node", str(ROOT / "tools" / script)], input=json.dumps(payload), capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError) as err:
        print(f"warning: tools/{script} failed ({err}); skipping it")
        return None
    return json.loads(done.stdout)


def _case_links(entries):
    """Links "This" → this where Yomitan would otherwise show a capitalised entry first (Thi, by the plural rule).
    The link has no inflection label, so it ranks with the exact matches."""
    caps = {}
    for e in entries:
        if e["w"][:1].isupper() and " " not in e["w"]:
            caps.setdefault(e["w"], set()).add(rule_of(e))
    words = sorted({e["w"] for e in entries if e["w"][:1].islower() and " " not in e["w"]})
    found = _node("case-links.mjs", {"words": words, "entries": {w: sorted(r) for w, r in caps.items()}}) or []
    return [{"w": w[0].upper() + w[1:], "to": w, "p": "", "t": ["case"]} for w in found]


def _needed(forms, entries):
    """Drop the links Yomitan resolves by itself (plans → plan). Its own deinflection knows the part of speech,
    so "grumbled" shows only the verb; a link row cannot say that and brings up every entry of the headword."""
    rules = {}
    for e in entries:
        rules.setdefault(e["w"], set()).add(rule_of(e))
    payload = {
        "forms": [{"w": f["w"], "to": f["to"], "rule": rule_of({"w": f["to"], "pos": f["p"]})} for f in forms],
        "rules": {w: sorted(r) for w, r in rules.items()},
    }
    drop = _node("redundant-forms.mjs", payload)
    if drop is None:
        return forms  # keep every link
    drop = set(drop)
    # A spelling linked to the same headword by a form Yomitan cannot resolve keeps that one link.
    return [f for i, f in enumerate(forms) if i not in drop]


def load():
    with open(ENTRIES, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def is_multiword(entry):
    return " " in entry["w"]


def is_phrasal(entry):
    """A verb followed only by particles (give up, look forward to)."""
    toks = entry["w"].lower().split()
    return entry["pos"] == "verb" and 2 <= len(toks) <= 3 and all(t in PARTICLES for t in toks[1:])


def rule_of(entry):
    # Multi-word verbs all get the phrasal rule, so that Yomitan inflects the first word (fell in love).
    return "v_phr" if is_multiword(entry) and entry["pos"] == "verb" else RULES.get(entry["pos"], "")


def source_hash(entry):
    """Fingerprint of everything the translation depends on; a change means re-translate."""
    payload = [entry["pos"], [[s["g"], s["t"]] for s in entry["s"]]]
    return hashlib.sha1(json.dumps(payload, ensure_ascii=False).encode()).hexdigest()[:12]


def entry_prompt(entry, n):
    """`n` is the entry's number inside the batch; ids contain spaces and bars, so the model echoes `n`."""
    lines = [f"#{n} {entry['w']} ({entry['pos']})"]
    for i, s in enumerate(entry["s"], 1):
        lines.append(f"{i}. " + (f"({', '.join(s['t'])}) " if s["t"] else "") + s["g"])
    if entry.get("ko"):
        lines.append("ko hints: " + " | ".join((f"{label} → " if label else "") + ", ".join(words) for label, words in entry["ko"]))
    return "\n".join(lines)


def main(args):
    from .fetch import fetch_dump

    fetch_dump()
    entries, deferred, forms = select(args.top)
    SOURCE.mkdir(exist_ok=True)
    for path, recs in ((ENTRIES, entries), (DEFERRED, deferred), (FORMS, forms)):
        with open(path, "w", encoding="utf-8") as f:
            for e in recs:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
    SOURCE_VERSION.write_text(DUMP_VERSION.read_text() if DUMP_VERSION.exists() else "unknown\n")
    phrasal = [e for e in entries if is_phrasal(e)]
    multi = [e for e in entries if is_multiword(e) and not is_phrasal(e)]
    print(f"{len(entries):,} entries, {sum(len(e['s']) for e in entries):,} senses → {ENTRIES}")
    print(f"  single words: {len({e['w'].lower() for e in entries if not is_multiword(e)}):,} headwords")
    print(f"  phrasal verbs: {len(phrasal):,} entries, {sum(len(e['s']) for e in phrasal):,} senses")
    print(f"  other multi-word headwords: {len(multi):,} entries, {sum(len(e['s']) for e in multi):,} senses")
    names = [e for e in entries if e["pos"] == "name"]
    print(f"  proper names: {len(names):,} entries, {sum(len(e['s']) for e in names):,} senses")
    print(f"deferred (capitalised variants of a lowercase word): {len(deferred):,} entries, {sum(len(e['s']) for e in deferred):,} senses → {DEFERRED}")
    print(f"forms linked to a headword (went → go, favorite → favourite): {len(forms):,} → {FORMS}")
