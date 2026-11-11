"""Print translation progress."""
from . import wikt
from .paths import TERMS_STORE
from .store import Store


def _pct(n, d):
    return f"{n:,} / {d:,} ({n / d:.1%})" if d else "0 / 0"


def main(args):
    entries = wikt.load()
    store = Store(TERMS_STORE)
    fresh = {e["id"] for e in entries if (store.get(e["id"]) or {}).get("h") == wikt.source_hash(e)}
    single = [e for e in entries if not wikt.is_phrasal(e)]
    phrasal = [e for e in entries if wikt.is_phrasal(e)]

    print(f"single words:  {_pct(sum(e['id'] in fresh for e in single), len(single))}")
    print(f"phrasal verbs: {_pct(sum(e['id'] in fresh for e in phrasal), len(phrasal))}")
    print(f"all entries:   {_pct(len(fresh), len(entries))}")
    print(f"senses:        {_pct(sum(len(e['s']) for e in entries if e['id'] in fresh), sum(len(e['s']) for e in entries))}")
    print(f"stale or dropped from the source: {len(store.records) - len(fresh):,}")
    print(f"low confidence: {sum(1 for i in fresh if store.get(i)['c'] == 'low'):,}")
