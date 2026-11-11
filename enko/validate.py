"""Validate the built dictionary against Yomitan's JSON schemas, plus a few lookup smoke checks."""
import json
import os
import re
import sys
import zipfile
from concurrent.futures import ProcessPoolExecutor

from jsonschema.validators import validator_for

from .paths import DIST, SCHEMAS

TERM_SCHEMA = "dictionary-term-bank-v3-schema.json"
CHUNK = 250  # rows per worker task; the structured-content schema is slow to check in one process
# term -> rule a row must carry, so inflected forms (running, gave up, bigger) resolve
SMOKE_RULES = {"run": "v", "give up": "v_phr", "house": "n", "big": "adj", "quickly": "adv"}


def _validator(name):
    schema = json.loads((SCHEMAS / name).read_text())
    return validator_for(schema)(schema)


def _check_rows(task):
    name, start, rows = task
    return [
        f"{name}: {'/'.join(map(str, [start + err.absolute_path[0]] + list(err.absolute_path)[1:]))}: {err.message[:200]}"
        for err in _validator(TERM_SCHEMA).iter_errors(rows)
    ]


def validate_zip(path):
    messages, rows, tasks = [], [], []
    with zipfile.ZipFile(path) as z:
        for err in _validator("dictionary-index-schema.json").iter_errors(json.loads(z.read("index.json"))):
            messages.append(f"index.json: {err.message[:200]}")
        for name in sorted(n for n in z.namelist() if re.match(r"term_bank_\d+\.json$", n)):
            bank = json.loads(z.read(name))
            if not isinstance(bank, list):
                messages.append(f"{name}: not an array")
                continue
            rows += bank
            tasks += [(name, n, bank[n : n + CHUNK]) for n in range(0, len(bank), CHUNK)]
    with ProcessPoolExecutor(os.cpu_count()) as pool:
        for found in pool.map(_check_rows, tasks):
            messages += found
    for term, rule in SMOKE_RULES.items():
        hits = [r for r in rows if r[0] == term]
        if hits and not any(rule in r[3].split() for r in hits):
            messages.append(f"smoke: {term} has no '{rule}' rule")
    for m in messages[:20]:
        print(f"  {m}")
    print(f"{path.name}: {'OK' if not messages else f'{len(messages)} errors'}")
    return len(messages)


def main(args):
    zips = sorted(DIST.glob("*.zip"))
    if not zips:
        sys.exit("nothing in dist/ — run `python -m enko build` first")
    if sum(validate_zip(z) for z in zips):
        sys.exit(1)
