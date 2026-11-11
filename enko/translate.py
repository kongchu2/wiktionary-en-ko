"""Translate English Wiktionary senses and tag names into Korean with an LLM."""
import json
import re
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from . import wikt
from .llm import ClaudeCLI, RateLimited
from .paths import TAGS_FILE, TERMS_STORE
from .store import Store

CJK_SCRIPT = re.compile(r"[぀-ヿ㐀-䶿一-鿿]")  # kana and hanja
ENGLISH_WORD = re.compile(r"[a-z]{4,}")  # leaves room for DNA, km, pH, mRNA

TERMS_SYSTEM = """You are a professional English–Korean lexicographer writing the Korean side of an English→Korean learner's dictionary built on English Wiktionary.

Each entry has a number (#n), the headword, its part of speech, and numbered senses. Each sense shows Wiktionary tags in parentheses (grammar, register, topic) and the English definition; sub-senses show the parent definitions first, separated by ›. Some entries end with "ko hints": Korean words from Wiktionary's translation tables, grouped by a short sense label.

For every sense, write the Korean equivalents a Korean speaker would expect in a bilingual dictionary.

Rules:
1. Give Korean equivalents of the headword in that sense. Do not translate the definition sentence itself (serendipity → 뜻밖의 행운, not "우연히 좋은 것을 발견하는 능력을 말한다").
2. Return exactly as many senses as given, in the same order. Never merge, split, skip or reorder senses, even when two senses end up with the same Korean.
3. Give 1–4 short glosses per sense, most natural first. Prefer real equivalent words. Use a short explanatory phrase only when Korean has no equivalent.
4. Match the part of speech. Verbs in dictionary form ending in -다 (run → 달리다). Adjectives in the attributive form Korean 영한사전 use (big → 큰, beautiful → 아름다운, political → 정치적인). Nouns as nouns. Adverbs as adverbs (quickly → 빨리). Prepositions, conjunctions, determiners, affixes and particles: the Korean pattern with ~ (of → ~의, although → ~이긴 하지만, un- → 비~, 불~).
5. Never prefix glosses with grammar labels such as (타동사), (자동사), (명사), (불가산): the dictionary already shows the tags. Words a transitive verb needs may be shown with ~ (give up → ~을 포기하다).
6. Keep register: slang, vulgar or informal senses → equally informal Korean; formal or literary → formal Korean.
7. If Korean normally uses the loanword, give it in standard 외래어 표기법 spelling (computer → 컴퓨터, dock → 도크). Do not transliterate when a native or Sino-Korean word is the normal equivalent (water → 물, not 워터).
8. Technical senses (math, law, medicine, computing, …): use the established Korean term (corollary → 따름정리, tort → 불법행위).
9. Culture-specific terms with no Korean equivalent: Hangul transliteration plus a short explanation in parentheses. Proper names: the standard Korean name (Germany → 독일, London → 런던, Monday → 월요일); for personal names and lesser-known places add what it is in parentheses (John → 존 (남자 이름), Smith → 스미스 (성씨), Salem → 세일럼 (미국 오리건주의 주도)).
10. The ko hints are unreviewed. Use a hint when it is right for the sense; ignore it when it is wrong, belongs to another sense, or is unnatural.
11. Write only Korean (Hangul, with punctuation and ~ allowed): no English words, no romanization, no hanja. Latin letters are allowed only where Korean itself writes them (DNA, CD, km).
12. conf: "low" only when you are unsure of the core meaning of some sense (obscure, rare or ambiguous). Many senses, nuance or register differences alone are not reasons for "low"; otherwise "high"."""

TERMS_SCHEMA = {
    "type": "object",
    "properties": {
        "entries": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "n": {"type": "integer"},
                    "senses": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}},
                    "conf": {"type": "string", "enum": ["high", "low"]},
                },
                "required": ["n", "senses", "conf"],
            },
        }
    },
    "required": ["entries"],
}

TAGS_SYSTEM = """You translate English Wiktionary (Wiktextract) part-of-speech codes and sense tags into Korean for an English→Korean dictionary.
For each tag give:
- short: a compact Korean label as seen in Korean 영한사전, at most 8 characters, no spaces (noun → 명사, verb → 동사, adj → 형용사, adv → 부사, prep → 전치사, intj → 감탄사, transitive → 타동사, intransitive → 자동사, countable → 가산, uncountable → 불가산, slang → 속어, informal → 구어, figuratively → 비유, US → 미국, UK → 영국, mathematics → 수학).
- long: a full Korean description of the tag."""

TAGS_SCHEMA = {
    "type": "object",
    "properties": {
        "tags": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"tag": {"type": "string"}, "short": {"type": "string"}, "long": {"type": "string"}},
                "required": ["tag", "short", "long"],
            },
        }
    },
    "required": ["tags"],
}


def _chunk(items, max_items, weight=lambda x: 1, max_weight=None):
    batch, w = [], 0
    for it in items:
        iw = weight(it)
        if batch and (len(batch) >= max_items or (max_weight and w + iw > max_weight)):
            yield batch
            batch, w = [], 0
        batch.append(it)
        w += iw
    if batch:
        yield batch


def _run(batches, worker, workers):
    """Run worker(batch) -> (ok_count, failed_items) in parallel; stop cleanly on rate limits."""
    stop = threading.Event()
    failed, done, total, t0 = [], 0, len(batches), time.time()

    def guarded(b):
        if stop.is_set():
            return 0, []
        try:
            return worker(b)
        except RateLimited as e:
            stop.set()
            print(f"\n!! rate/usage limit reached, stopping: {e}", file=sys.stderr)
            return 0, []
        except Exception as e:  # keep going; the batch stays untranslated and is retried next run
            print(f"\n!! batch failed: {e}", file=sys.stderr)
            return 0, []

    ok = 0
    with ThreadPoolExecutor(workers) as pool:
        for fut in as_completed([pool.submit(guarded, b) for b in batches]):
            n, f = fut.result()
            ok += n
            failed += f
            done += 1
            print(f"[{done}/{total}] ok={ok} failed={len(failed)} {time.time() - t0:.0f}s", flush=True)
    return ok, failed, stop.is_set()


def _valid_senses(senses, expected):
    return len(senses) == expected and all(
        s and all(g.strip() and not CJK_SCRIPT.search(g) and not ENGLISH_WORD.search(g) for g in s) for s in senses
    )


def translate_terms(args):
    store = Store(Path(args.store) if args.store else TERMS_STORE)
    llm = ClaudeCLI(args.model)

    entries = wikt.load()  # already in rank order
    if args.max_rank:
        entries = [e for e in entries if e["r"] < args.max_rank]
    todo = [e for e in entries if (store.get(e["id"]) or {}).get("h") != wikt.source_hash(e)]
    if args.limit:
        todo = todo[: args.limit]
    print(f"{len(todo)} entries to translate with {args.model}")

    def worker(batch):
        by_n = dict(enumerate(batch, 1))
        prompt = "\n\n".join(wikt.entry_prompt(e, n) for n, e in by_n.items())
        out = llm.call(TERMS_SYSTEM, prompt, TERMS_SCHEMA)
        recs = []
        for item in out.get("entries", []):
            e = by_n.get(item.get("n"))
            if e is None:
                continue
            senses = [[g.strip() for g in s if g.strip()] for s in item["senses"]]
            if not _valid_senses(senses, len(e["s"])):
                continue
            del by_n[item["n"]]
            recs.append({"id": e["id"], "h": wikt.source_hash(e), "s": senses, "c": item["conf"], "m": args.model})
        store.add_many(recs)
        return len(recs), list(by_n.values())

    batches = list(_chunk(todo, args.batch, weight=lambda e: len(e["s"]), max_weight=args.batch * 3))
    ok, failed, stopped = _run(batches, worker, args.workers)
    if failed and not stopped:
        print(f"retrying {len(failed)} entries in small batches")
        ok2, failed, stopped = _run(list(_chunk(failed, 3)), worker, args.workers)
        ok += ok2
    store.compact()
    print(f"translated {ok}, still failing {len(failed)}: {', '.join(e['id'] for e in failed[:50])}")
    if stopped:
        sys.exit(75)  # EX_TEMPFAIL: usage limit, run again after it resets


def used_tags(entries):
    """Part-of-speech codes and sense tags, most used first."""
    count = Counter(e["pos"] for e in entries)
    count.update(t for e in entries for s in e["s"] for t in s["t"])
    return [t for t, _ in count.most_common()]


def translate_tags(args):
    tags = json.loads(TAGS_FILE.read_text()) if TAGS_FILE.exists() else {}
    todo = [t for t in used_tags(wikt.load()) if t not in tags]
    if args.limit:
        todo = todo[: args.limit]
    if not todo:
        print("tags up to date")
        return
    llm = ClaudeCLI(args.model)
    for batch in _chunk(todo, 80):
        for t in llm.call(TAGS_SYSTEM, "\n".join(batch), TAGS_SCHEMA)["tags"]:
            if t["tag"] in batch:
                tags[t["tag"]] = {"short": t["short"].replace(" ", ""), "long": t["long"]}
        TAGS_FILE.parent.mkdir(exist_ok=True)
        TAGS_FILE.write_text(json.dumps(dict(sorted(tags.items())), ensure_ascii=False, indent=1) + "\n")
    print(f"{len(tags)} tags translated, missing: {[t for t in todo if t not in tags]}")


def main(args):
    {"terms": translate_terms, "tags": translate_tags}[args.what](args)
