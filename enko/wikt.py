"""English Wiktionary (kaikki.org / Wiktextract) helpers: entry selection, ranking, prompt text."""
import gzip
import hashlib
import json
import re
from collections import Counter

from .paths import DUMP, DUMP_VERSION, ENTRIES, SOURCE, SOURCE_VERSION

TOP_WORDS = 20000  # single words: the wordfreq top N
SKIP_POS = {"name", "character", "symbol"}
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
RULES = {"verb": "v", "noun": "n", "adj": "adj", "adv": "adv"}
HANGUL = re.compile(r"[가-힣]")
MAX_EXAMPLE = 120


def _lemma_senses(entry):
    out = []
    for s in entry.get("senses", []):
        # Wiktextract lists topics from specific to broad (mathematics, sciences); the first is enough.
        tags = list(dict.fromkeys(s.get("tags", []) + s.get("topics", [])[:1]))
        if not s.get("glosses") or s.get("form_of") or s.get("alt_of") or (FORM_TAGS | SKIP_TAGS) & set(tags):
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
    """Read the dump and return the entries worth translating, most useful first."""
    from wordfreq import top_n_list

    rank = {w: i for i, w in enumerate(top_n_list("en", top))}
    out, seen = [], Counter()
    with gzip.open(DUMP, "rt", encoding="utf-8") as f:
        for n, line in enumerate(f):
            e = json.loads(line)
            word, pos = e.get("word", ""), e.get("pos", "")
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
            senses = _lemma_senses(e)
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
            out.append((rec["r"], n, rec))
    return [rec for _, _, rec in sorted(out, key=lambda x: x[:2])]


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
    entries = select(args.top)
    SOURCE.mkdir(exist_ok=True)
    with open(ENTRIES, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    SOURCE_VERSION.write_text(DUMP_VERSION.read_text() if DUMP_VERSION.exists() else "unknown\n")
    phrasal = [e for e in entries if is_phrasal(e)]
    print(f"{len(entries):,} entries, {sum(len(e['s']) for e in entries):,} senses → {ENTRIES}")
    print(f"  single words: {len({e['w'].lower() for e in entries if not is_phrasal(e)}):,} headwords")
    print(f"  phrasal verbs: {len(phrasal):,} entries, {sum(len(e['s']) for e in phrasal):,} senses")
