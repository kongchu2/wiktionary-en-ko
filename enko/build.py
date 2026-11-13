"""Build the Yomitan English→Korean term dictionary."""
import hashlib
import json
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from . import wikt
from .paths import DIST, FORMS, NAME, RELEASE_URL, REPO, SOURCE_VERSION, TAGS_FILE, TERMS_STORE
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
    if tags[0] == "form-of":
        return " ".join(ko for tag, ko in FORM_LABELS if tag in tags) or "활용형"
    return next((ko for tag, ko in ALT_LABELS if tag in tags), "다른 철자")


def _form_rows(headwords, seq):
    """Rows that only point at a headword: Yomitan looks up the target and shows the label as the inflection."""
    rows, seen = [], set()
    if not FORMS.exists():
        return rows
    with open(FORMS, encoding="utf-8") as f:
        for line in f:
            form = json.loads(line)
            if form["to"] in headwords and (form["w"], form["to"]) not in seen:
                seen.add((form["w"], form["to"]))
                seq += 1
                rows.append([form["w"], "", "", "", 0, [[form["to"], [form_label(form["t"])]]], seq, ""])
    return rows


def main(args):
    store = Store(Path(args.store) if args.store else TERMS_STORE)
    tags = TagNames()
    rows, order, seq = [], Counter(), 0
    for seq, e in enumerate(wikt.load(), 1):
        tr = store.get(e["id"])
        if tr and tr["h"] != wikt.source_hash(e):
            tr = None  # the source entry changed since it was translated
        if tr is None and not args.include_untranslated:
            continue
        order[e["w"]] += 1  # same spelling: keep Wiktionary's order (first etymology first)
        rows.append([e["w"], "", "", wikt.rule_of(e), 1 - order[e["w"]], [_render(e, tr, tags)], seq, ""])
    forms = _form_rows({row[0] for row in rows}, seq)
    rows += forms
    version = SOURCE_VERSION.read_text().strip()
    index = _index(f"영어 위키낱말사전 기반 영한사전. 한국어 뜻은 LLM 번역 (Wiktionary {version}).")
    digest = _write_zip(index, rows)
    (DIST / "content.sha256").write_text(f"{digest}  {NAME}\n")
    print(f"{NAME}: {len(rows) - len(forms)} entries, {len(forms)} forms")
