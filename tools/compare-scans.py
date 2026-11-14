"""Compare two `lookup.mjs --text --json` scans of the same text, token by token.

    python3 tools/compare-scans.py before.json after.json [-n 300]

Each hit carries `i`, its offset in the text, so the two scans line up even where one of them matched a
longer phrase. Prints the totals, the tokens that stopped resolving, and every change of the top result
(matched text and first Korean gloss) grouped by kind, most frequent first. Read the whole list: whether
a change is better or worse depends on the sentence, and only a reader can tell.
"""
import argparse
import json
from collections import Counter


def load(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if data["hits"] and "i" not in data["hits"][0]:
        raise SystemExit(f"{path}: hits have no offset `i`; rescan with the current tools/lookup.mjs")
    return data, {h["i"]: h for h in data["hits"]}


def key(hit):
    return None if hit is None else (hit["matched"], hit["ko"][:30])


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("before")
    p.add_argument("after")
    p.add_argument("-n", type=int, default=0, help="show only the N most frequent changes (0 = all)")
    args = p.parse_args()
    a, before = load(args.before)
    b, after = load(args.after)
    print(f"tokens {a['total']}: found {a['found']} -> {b['found']}")
    lost = Counter(before[i]["word"] for i in before if i not in after)
    if lost:
        print("no longer found:", ", ".join(f"{w}×{n}" for w, n in lost.most_common()))
    changes = Counter(
        (key(before.get(i)), key(after.get(i)))
        for i in set(before) | set(after)
        if key(before.get(i)) != key(after.get(i))
    )
    print(f"top result changed: {sum(changes.values())} tokens, {len(changes)} kinds")
    for (old, new), n in changes.most_common(args.n or None):
        show = lambda k: "—" if k is None else f"{k[0]} = {k[1]}"
        print(f"{n}\t{show(old)}  →  {show(new)}")


if __name__ == "__main__":
    main()
