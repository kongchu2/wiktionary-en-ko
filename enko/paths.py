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
FORMS = SOURCE / "forms.jsonl"  # inflected forms and other spellings, linked to their headword
SOURCE_VERSION = SOURCE / "VERSION"

TERMS_STORE = TRANSLATIONS / "terms.jsonl"
TAGS_FILE = TRANSLATIONS / "tags.json"
ORDER_STORE = TRANSLATIONS / "order.jsonl"  # per spelling: entry and sense order, hidden entries

NAME = "wiktionary-en-ko"
REPO = "kongchu2/" + NAME
RELEASE_URL = f"https://github.com/{REPO}/releases/latest/download"
