import argparse

from . import build, fetch, review, status, translate, validate, wikt


def main():
    p = argparse.ArgumentParser(prog="python -m enko", description="English Wiktionary → Korean Yomitan dictionary builder")
    sub = p.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="download the Yomitan schemas")
    f.add_argument("--dump", action="store_true", help="also re-download the kaikki English dump (about 530 MB)")
    f.set_defaults(run=fetch.main)

    s = sub.add_parser("select", help="pick the entries to translate from the dump → source/entries.jsonl")
    s.add_argument("--top", type=int, default=wikt.TOP_WORDS, help="single words: wordfreq top N")
    s.set_defaults(run=wikt.main)

    t = sub.add_parser("translate", help="translate with the claude CLI (resumable)")
    t.add_argument("what", choices=["terms", "tags", "order"], help="order: entry and sense order for common spellings")
    t.add_argument("--model", default="sonnet")
    t.add_argument("--limit", type=int, default=0, help="max items this run (0 = all)")
    t.add_argument("--max-rank", type=int, default=0, help="only words inside the wordfreq top N (0 = all; order: default 5000)")
    t.add_argument("--batch", type=int, default=20, help="entries per LLM call")
    t.add_argument("--workers", type=int, default=4)
    t.add_argument("--store", help="alternative store file (e.g. to compare models)")
    t.set_defaults(run=translate.main)

    b = sub.add_parser("build", help="build dist/*.zip")
    b.add_argument("--include-untranslated", action="store_true", help="include entries with English definitions only")
    b.add_argument("--store", help="alternative store file")
    b.set_defaults(run=build.main)

    sub.add_parser("validate", help="validate dist/*.zip against Yomitan schemas").set_defaults(run=validate.main)

    sub.add_parser("status", help="translation progress").set_defaults(run=status.main)

    r = sub.add_parser("review", help="write a translation sample for manual review")
    r.add_argument("-n", type=int, default=200)
    r.add_argument("--low", action="store_true", help="only low-confidence entries")
    r.add_argument("--seed", type=int, default=0)
    r.add_argument("--store", help="alternative store file")
    r.add_argument("--against", help="second store to show side by side")
    r.set_defaults(run=review.main)

    args = p.parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
