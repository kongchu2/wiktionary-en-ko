"""Dump a random sample of translations (optionally side by side with another store) for manual review."""
import random
from pathlib import Path

from . import wikt
from .paths import REVIEW, TERMS_STORE
from .store import Store


def main(args):
    order = {e["id"]: (n, e) for n, e in enumerate(wikt.load())}
    store = Store(Path(args.store) if args.store else TERMS_STORE)
    other = Store(Path(args.against)) if args.against else None
    ids = [
        i for i, r in store.records.items()
        if i in order and len(r["s"]) == len(order[i][1]["s"]) and (r["c"] == "low" or not args.low) and (not other or other.get(i))
    ]
    random.Random(args.seed).shuffle(ids)
    out = []
    for i in sorted(ids[: args.n], key=lambda i: order[i][0]):
        e, r = order[i][1], store.get(i)
        out.append(f"### {e['w']} ({e['pos']}) conf={r['c']}")
        for n, s in enumerate(e["s"]):
            tags = f"({', '.join(s['t'])}) " if s["t"] else ""
            line = f"{n + 1}. {tags}{s['g']}\n   → {'; '.join(r['s'][n])}"
            if other:
                line += f"\n   ⇢ {'; '.join(other.get(i)['s'][n])}  ({other.get(i)['m']})"
            out.append(line)
        out.append("")
    REVIEW.mkdir(exist_ok=True)
    path = REVIEW / ("low.md" if args.low else "sample.md")
    path.write_text("\n".join(out))
    print(f"{min(len(ids), args.n)} entries → {path}")
