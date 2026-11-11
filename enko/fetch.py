"""Download the Yomitan dictionary schemas and, on request, the kaikki.org English Wiktionary dump."""
import shutil
import urllib.request
from email.utils import parsedate_to_datetime

from .paths import DUMP, DUMP_VERSION, RAW, SCHEMAS

DUMP_URL = "https://kaikki.org/dictionary/English/kaikki.org-dictionary-English.jsonl.gz"
SCHEMA_BASE = "https://raw.githubusercontent.com/yomidevs/yomitan/master/ext/data/schemas"
SCHEMA_FILES = [
    "dictionary-index-schema.json",
    "dictionary-term-bank-v3-schema.json",
]


def _open(url):
    req = urllib.request.Request(url, headers={"User-Agent": "enko-builder"})
    return urllib.request.urlopen(req, timeout=300)


def fetch_schemas():
    SCHEMAS.mkdir(parents=True, exist_ok=True)
    for name in SCHEMA_FILES:
        with _open(f"{SCHEMA_BASE}/{name}") as r:
            (SCHEMAS / name).write_bytes(r.read())


def fetch_dump(refresh=False):
    """About 530 MB. Kept in data/raw (gitignored); only `select` reads it."""
    if DUMP.exists() and not refresh:
        return
    RAW.mkdir(parents=True, exist_ok=True)
    print(f"downloading {DUMP_URL}")
    tmp = DUMP.with_suffix(".part")
    with _open(DUMP_URL) as r, open(tmp, "wb") as f:
        modified = r.headers.get("Last-Modified")
        shutil.copyfileobj(r, f, 1 << 20)
    tmp.replace(DUMP)
    version = parsedate_to_datetime(modified).strftime("%Y-%m-%d") if modified else "unknown"
    DUMP_VERSION.write_text(version + "\n")
    print(f"kaikki English dump {version}")


def main(args):
    fetch_schemas()
    if args.dump:
        fetch_dump(refresh=True)
