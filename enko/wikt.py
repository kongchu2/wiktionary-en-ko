"""English Wiktionary (kaikki.org / Wiktextract) helpers: entry selection, ranking, prompt text."""
import gzip
import hashlib
import json
import re
from collections import Counter

from .paths import DEFERRED, DUMP, DUMP_VERSION, ENTRIES, SOURCE, SOURCE_VERSION

TOP_WORDS = 20000  # single words: the wordfreq top N
SKIP_POS = {"character", "symbol"}
# Senses a learner's dictionary can do without; dropping them cuts the sense count by about 30%.
SKIP_TAGS = {"obsolete", "archaic", "rare", "dialectal", "dated", "nonstandard", "misspelling"}
FORM_TAGS = {"form-of", "alt-of"}
# Words that can follow a verb in a phrasal verb (Yomitan's particle and preposition lists).
PARTICLES = set(
    "aback aboard about above across after against ahead along alongside among apart around as aside astray at away "
    "back before behind below beneath besides between beyond by close down even for forth forward forwards from home "
    "in inside instead into near of off on onto open opposite out outside over overhead past round since through "
    "throughout to together toward towards under underneath up upon way with within without".split()
)
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


def _lemma_senses(entry, kinds):
    """`kinds` counts the name senses already kept for this spelling, across its entries (Paris has seven)."""
    out = []
    for s in entry.get("senses", []):
        # Wiktextract lists topics from specific to broad (mathematics, sciences); the first is enough.
        tags = list(dict.fromkeys(s.get("tags", []) + s.get("topics", [])[:1]))
        if not s.get("glosses") or s.get("form_of") or s.get("alt_of") or (FORM_TAGS | SKIP_TAGS) & set(tags):
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
    return out


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


def select(top=TOP_WORDS):
    """Read the dump and return (entries worth translating, most useful first; deferred entries)."""
    from wordfreq import top_n_list

    rank = {w: i for i, w in enumerate(top_n_list("en", top))}
    out, seen, name_kinds, lowercase = [], Counter(), {}, set()
    with gzip.open(DUMP, "rt", encoding="utf-8") as f:
        for n, line in enumerate(f):
            e = json.loads(line)
            word, pos = e.get("word", ""), e.get("pos", "")
            if word == word.lower():
                lowercase.add(word)  # every lowercase spelling in the dump, inflected forms included
            if pos in SKIP_POS:
                continue
            toks = word.lower().split()
            if len(toks) == 1:
                r, phrasal = rank.get(toks[0]), False
            elif pos == "verb" and 2 <= len(toks) <= 3 and all(t in PARTICLES for t in toks[1:]):
                r, phrasal = rank.get(toks[0]), True
            else:
                continue
            if r is None:
                continue
            senses = _lemma_senses(e, name_kinds.setdefault(word, Counter()))
            if not senses:
                continue
            key = f"{word}|{pos}|{e.get('etymology_number', 0)}"
            seen[key] += 1
            rec = {
                "id": key if seen[key] == 1 else f"{key}|{seen[key]}",
                "w": word,
                "pos": pos,
                "r": r + top if phrasal else r,  # phrasal verbs come after all single words
                "s": senses,
            }
            hints = _hints(e)
            if hints:
                rec["ko"] = hints
            # A name that is nothing but surnames, given names and places (Grew, Butler, Ripple).
            namesake_only = pos == "name" and all(name_kind(s.get("glosses") or [""]) for s in e["senses"])
            out.append((rec["r"], n, rec, namesake_only))
    out.sort(key=lambda x: x[:2])
    # A capitalised variant borrows the rank of the lowercase word and shows up next to it in Yomitan
    # (She the people on "she", TO the verb, Grew the surname on "grew"). Set these aside.
    # Proper names with a sense of their own (March, Turkey) stay, and so does the pronoun I.
    headwords = {rec["w"] for _, _, rec, _ in out if rec["w"] == rec["w"].lower()}
    keep, deferred = [], []
    for _, _, rec, namesake_only in out:
        w = rec["w"]
        if rec["pos"] == "name":
            variant = namesake_only and w.lower() in lowercase
        else:
            variant = w != w.lower() and w.lower() in headwords and w != "I"
        (deferred if variant else keep).append(rec)
    return keep, deferred


def load():
    with open(ENTRIES, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def is_phrasal(entry):
    return " " in entry["w"]


def rule_of(entry):
    return "v_phr" if is_phrasal(entry) else RULES.get(entry["pos"], "")


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
    entries, deferred = select(args.top)
    SOURCE.mkdir(exist_ok=True)
    for path, recs in ((ENTRIES, entries), (DEFERRED, deferred)):
        with open(path, "w", encoding="utf-8") as f:
            for e in recs:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
    SOURCE_VERSION.write_text(DUMP_VERSION.read_text() if DUMP_VERSION.exists() else "unknown\n")
    phrasal = [e for e in entries if is_phrasal(e)]
    print(f"{len(entries):,} entries, {sum(len(e['s']) for e in entries):,} senses → {ENTRIES}")
    print(f"  single words: {len({e['w'].lower() for e in entries if not is_phrasal(e)}):,} headwords")
    print(f"  phrasal verbs: {len(phrasal):,} entries, {sum(len(e['s']) for e in phrasal):,} senses")
    names = [e for e in entries if e["pos"] == "name"]
    print(f"  proper names: {len(names):,} entries, {sum(len(e['s']) for e in names):,} senses")
    print(f"deferred (capitalised variants of a lowercase word): {len(deferred):,} entries, {sum(len(e['s']) for e in deferred):,} senses → {DEFERRED}")
