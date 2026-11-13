"""Build the Yomitan English→Korean term dictionary."""
import hashlib
import json
import re
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from . import wikt
from .paths import DIST, FORMS, NAME, ORDER_STORE, RELEASE_URL, REPO, SOURCE_VERSION, TAGS_FILE, TERMS_STORE
from .store import Store

BANK_SIZE = 10000
AUTHOR = "kongchu2"
TITLE = "Wiktionary-en-ko"

STYLES = """\
[data-sc-enko="tag"] {
  font-size: 0.75em; font-weight: bold; padding: 0.1em 0.35em; margin-right: 0.3em;
  border-radius: 0.3em; background-color: #5a5a5a; color: #fff; vertical-align: text-bottom;
}
[data-sc-kind="misc"] { background-color: #8a5a00; }
[data-sc-enko="note"] { font-size: 0.85em; opacity: 0.8; }
[data-sc-enko="en"] { font-size: 0.85em; opacity: 0.75; margin-top: 0.3em; }
[data-sc-enko="en"] ol { margin: 0; }
[data-sc-enko="ex"] { font-size: 0.85em; opacity: 0.7; font-style: italic; }
"""


def _index(description):
    return {
        "title": TITLE,
        "revision": datetime.now(timezone.utc).strftime("%Y.%m.%d.%H%M"),
        "format": 3,
        "sequenced": True,
        "author": AUTHOR,
        "url": f"https://github.com/{REPO}",
        "description": description,
        "attribution": "English Wiktionary contributors, CC BY-SA 4.0, extracted by Wiktextract (kaikki.org). "
        "Korean translations derived from Wiktionary, CC BY-SA 4.0.",
        "sourceLanguage": "en",
        "targetLanguage": "ko",
        "isUpdatable": True,
        "indexUrl": f"{RELEASE_URL}/{NAME}-index.json",
        "downloadUrl": f"{RELEASE_URL}/{NAME}.zip",
    }


def _write_zip(index, rows):
    """Returns the sha256 of the content (index excluded, since its revision changes every build)."""
    DIST.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    with zipfile.ZipFile(DIST / f"{NAME}.zip", "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("index.json", json.dumps(index, ensure_ascii=False, indent=1))
        for n in range(0, max(len(rows), 1), BANK_SIZE):
            body = json.dumps(rows[n : n + BANK_SIZE], ensure_ascii=False, separators=(",", ":"))
            z.writestr(f"term_bank_{n // BANK_SIZE + 1}.json", body)
            digest.update(body.encode())
        z.writestr("styles.css", STYLES)
        digest.update(STYLES.encode())
    (DIST / f"{NAME}-index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1))
    return digest.hexdigest()


class TagNames:
    """Wiktextract tag -> Korean label."""

    def __init__(self):
        self.ko = json.loads(TAGS_FILE.read_text()) if TAGS_FILE.exists() else {}

    def span(self, code, kind=None):
        ko = self.ko.get(code, {})
        data = {"enko": "tag", "kind": kind} if kind else {"enko": "tag"}
        return {"tag": "span", "data": data, "title": ko.get("long") or code, "content": ko.get("short") or code}


def _render(entry, tr, tags):
    items = []
    for i, s in enumerate(entry["s"]):
        parts = [tags.span(t, "misc") for t in s["t"]]
        if tr:
            parts.append({"tag": "span", "lang": "ko", "content": "; ".join(tr["s"][i])})
        else:
            parts.append({"tag": "span", "lang": "en", "content": s["g"]})
        if s.get("ex"):
            parts.append({"tag": "div", "lang": "en", "data": {"enko": "ex"}, "content": s["ex"]})
        items.append(parts)

    content = [{"tag": "div", "content": [tags.span(entry["pos"])]}]
    if len(items) == 1:
        content[0]["content"] += items[0]
    else:
        content.append({"tag": "ol", "content": [{"tag": "li", "content": p} for p in items]})
    if tr is None:
        content.append({"tag": "div", "data": {"enko": "note"}, "content": "※ 아직 번역되지 않은 항목 (영어 원문)"})
    elif tr["c"] == "low":
        content.append({"tag": "div", "data": {"enko": "note"}, "content": "※ 자동 번역 신뢰도 낮음 — 영어 원문을 확인하세요"})
    if tr:
        content.append({
            "tag": "details",
            "data": {"enko": "en"},
            "content": [
                {"tag": "summary", "content": "영어 원문 (Wiktionary)"},
                {"tag": "ol", "lang": "en", "content": [{"tag": "li", "content": s["g"]} for s in entry["s"]]},
            ],
        })
    return {"type": "structured-content", "content": content}


# Wiktextract tags on a form-of sense -> the label Yomitan shows next to the headword.
FORM_LABELS = [
    ("third-person", "3인칭"), ("singular", "단수"), ("plural", "복수"), ("present", "현재"), ("past", "과거"),
    ("participle", "분사"), ("gerund", "동명사"), ("comparative", "비교급"), ("superlative", "최상급"),
]
ALT_LABELS = [("pronunciation-spelling", "발음대로 쓴 철자"), ("misconstruction", "잘못 분석된 형태"), ("US", "미국식 철자"), ("UK", "영국식 철자")]


def form_label(tags):
    """None for a capitalisation link, which must carry no label: an inflection label would rank it lower."""
    if tags[0] == "case":
        return None
    if tags[0] == "form-of":
        return " ".join(ko for tag, ko in FORM_LABELS if tag in tags) or "활용형"
    return next((ko for tag, ko in ALT_LABELS if tag in tags), "다른 철자")


def _form_rows(headwords, seq, alts=None):
    """Rows that only point at a headword: Yomitan looks up the target and shows the label as the inflection."""
    rows, seen = [], set()
    if not FORMS.exists():
        return rows
    with open(FORMS, encoding="utf-8") as f:
        forms = [json.loads(line) for line in f]
    links = {}
    for form in forms:
        links.setdefault(form["w"], []).append(form)

    def add(word, target, label):
        nonlocal seq
        if target in headwords and (word, target) not in seen:
            seen.add((word, target))
            seq += 1
            rows.append([word, "", "", "", 0, [[target, [label] if label else []]], seq, ""])

    for form in forms:
        if form["to"] in headwords:
            add(form["w"], form["to"], form_label(form["t"]))
        elif alts and form["to"] in alts and " " not in form["w"] and form["w"] != alts[form["to"]]:
            # headmen → "head man" (hidden) → headman, the one-word spelling that kept the entry
            add(form["w"], alts[form["to"]], form_label(form["t"]))
        elif form["t"][0] == "case":
            # "Is" → is, but every entry of "is" is hidden: point at what "is" links to (be), without a label.
            for nxt in links.get(form["to"], []):
                add(form["w"], nxt["to"], None)
    return rows


def _shadow_rows(shadow, headwords):
    """A hidden phrase ("back pass") only hides the spaced spelling, which could swallow the next word.
    Its one-word alternative spellings (backpass, bloodhorse) cannot, so they get the entry itself."""
    rows, seen, alts = [], set(), {}
    if not FORMS.exists():
        return rows, alts
    with open(FORMS, encoding="utf-8") as f:
        for line in f:
            form = json.loads(line)
            word, target = form["w"], form["to"]
            if (target not in shadow or target in headwords or word in headwords or " " in word
                    or "alt-of" not in form["t"] or not re.search(r"[A-Za-z]", word) or (word, target) in seen):
                continue
            seen.add((word, target))
            alts.setdefault(target, word)
            rows += [[word, "", "", rule, score, glossary, seq, ""] for rule, score, glossary, seq in shadow[target]]
    return rows, alts


def _curly_rows(rows, seq):
    """Text mostly has ’ where Wiktionary writes ' (didn’t, I’m), and Yomitan's English lookup does not
    convert it. Give every spelling with ' a twin with ’ that points where the original does."""
    out, seen = [], {row[0] for row in rows}
    for row in rows:
        word = row[0]
        if "'" not in word:
            continue
        curly = word.replace("'", "’")
        is_link = isinstance(row[5][0], list)
        target, labels = (row[5][0][0], row[5][0][1]) if is_link else (word, [])
        if (curly, target) in seen:
            continue
        seen.add((curly, target))
        seq += 1
        out.append([curly, "", "", "", 0, [[target, labels]], seq, ""])
    return out


# Wiktionary's placeholder for the literal reading of an idiom ("see get, memo"); it says nothing in Korean.
LITERAL = "Used other than figuratively or idiomatically"


META = re.compile(r"해당 없음|적용되지 않|번역하지 않")


def _drop_literal(entry, tr):
    """The literal sense helps for phrasal verbs (found in → ~에서 찾다); drop it only where the model wrote
    a placeholder instead of a gloss (get the memo → 해당 없음)."""
    def useless(i):
        return entry["s"][i]["g"].startswith(LITERAL) and (tr is None or any(META.search(g) for g in tr["s"][i]))
    keep = [i for i in range(len(entry["s"])) if not useless(i)]
    if len(keep) == len(entry["s"]):
        return entry, tr
    entry = dict(entry, s=[entry["s"][i] for i in keep])
    if tr:
        tr = dict(tr, s=[tr["s"][i] for i in keep])
    return entry, tr


def _orders(entries):
    """id -> (position among the spelling's entries, sense order, hidden), from translations/order.jsonl.
    A spelling whose entries changed since its order was decided falls back to Wiktionary's order."""
    from .translate import order_hash

    store = Store(ORDER_STORE, key="w")
    by_word = {}
    for e in entries:
        by_word.setdefault(e["w"], []).append(e)
    out = {}
    for w, rec in store.records.items():
        if w in by_word and rec["h"] == order_hash(by_word[w]):
            for pos, (eid, senses, hide) in enumerate(rec["e"]):
                out[eid] = (pos, senses, hide)
    return out


def _reorder(entry, tr, senses):
    entry = dict(entry, s=[entry["s"][i - 1] for i in senses])
    if tr:
        tr = dict(tr, s=[tr["s"][i - 1] for i in senses])
    return entry, tr


def main(args):
    store = Store(Path(args.store) if args.store else TERMS_STORE)
    tags = TagNames()
    entries = wikt.load()
    orders = _orders(entries)
    rows, order, seq, hidden = [], Counter(), 0, 0
    shadow = {}  # spelling -> rows of its hidden entries, for one-word alternative spellings
    for seq, e in enumerate(entries, 1):
        tr = store.get(e["id"])
        if tr and tr["h"] != wikt.source_hash(e):
            tr = None  # the source entry changed since it was translated
        if tr is None and not args.include_untranslated:
            continue
        if e["id"] in orders:
            pos, senses, hide = orders[e["id"]]
            if hide:
                hidden += 1
                if " " in e["w"]:
                    # Wiktionary's own order: backpass, Redman mean the lexicalised sense, not the literal one.
                    se, st = _drop_literal(e, tr)
                    if se["s"]:
                        shadow.setdefault(e["w"], []).append([wikt.rule_of(se), -pos, [_render(se, st, tags)], seq])
                continue
            e, tr = _reorder(e, tr, senses)
            score = -pos
        else:
            order[e["w"]] += 1  # same spelling: keep Wiktionary's order (first etymology first)
            score = 1 - order[e["w"]]
        e, tr = _drop_literal(e, tr)
        if not e["s"]:
            continue
        rows.append([e["w"], "", "", wikt.rule_of(e), score, [_render(e, tr, tags)], seq, ""])
    headwords = {row[0] for row in rows}
    shadow_rows, alts = _shadow_rows(shadow, headwords)
    rows += shadow_rows
    forms = _form_rows({row[0] for row in rows}, seq, alts)
    forms += _curly_rows(rows + forms, seq + len(forms))
    rows += forms
    version = SOURCE_VERSION.read_text().strip()
    index = _index(f"영어 위키낱말사전 기반 영한사전. 한국어 뜻은 LLM 번역 (Wiktionary {version}).")
    digest = _write_zip(index, rows)
    (DIST / "content.sha256").write_text(f"{digest}  {NAME}\n")
    print(f"{NAME}: {len(rows) - len(forms)} entries, {len(forms)} forms, {len(orders)} entries reordered, {hidden} hidden")
