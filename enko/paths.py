from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
SCHEMAS = ROOT / "data" / "schemas"
SOURCE = ROOT / "source"
TRANSLATIONS = ROOT / "translations"
DIST = ROOT / "dist"
REVIEW = ROOT / "review"

DUMP = RAW / "kaikki-English.jsonl.gz"
DUMP_VERSION = RAW / "DUMP_VERSION"
ENTRIES = SOURCE / "entries.jsonl"
DEFERRED = SOURCE / "deferred.jsonl"  # selected but set aside: not translated, not built
SOURCE_VERSION = SOURCE / "VERSION"

TERMS_STORE = TRANSLATIONS / "terms.jsonl"
TAGS_FILE = TRANSLATIONS / "tags.json"

NAME = "wiktionary-en-ko"
REPO = "kongchu2/" + NAME
RELEASE_URL = f"https://github.com/{REPO}/releases/latest/download"
