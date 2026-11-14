#!/bin/sh
# Download the review texts into data/review/ (gitignored): running prose to scan with lookup.mjs.
#   gatsby.txt     The Great Gatsby (Project Gutenberg #64317, public domain), first ~21k words of the body
#   news.txt       the 15 most recently published English Wikinews articles (CC BY 2.5)
#   wikipedia.txt  six English Wikipedia articles (CC BY-SA)
#   novel-news.txt gatsby + news, the "fiction and news" set used since 2026-11-13
# Wikinews and Wikipedia change over time, so keep the files of one review round and compare builds
# against the same files (tools/compare-scans.py), not against numbers from an older download.
set -eu
cd "$(dirname "$0")/.."
out=data/review
mkdir -p "$out"
ua="dictionary-coverage-check/1.0"
# Wikimedia answers 429 to rapid requests: one request every 2 seconds, and files already there are kept
# (delete data/review/ to start a new review round).

[ -s "$out/gatsby.txt" ] || {
curl -sfL -A "$ua" https://www.gutenberg.org/cache/epub/64317/pg64317.txt -o "$out/gatsby-raw.txt"
python3 - "$out" <<'EOF'
import sys
out = sys.argv[1]
s = open(f"{out}/gatsby-raw.txt", encoding="utf-8", errors="ignore").read()
body = s[s.find("In my younger and more vulnerable years"):s.find("*** END")]
open(f"{out}/gatsby.txt", "w", encoding="utf-8").write(body[:120000])
EOF
rm "$out/gatsby-raw.txt"
}

[ -s "$out/news.txt" ] || {
curl -sf -A "$ua" "https://en.wikinews.org/w/api.php?action=query&list=categorymembers&cmtitle=Category:Published&cmsort=timestamp&cmdir=desc&cmlimit=15&format=json" \
  | python3 -c "import json,sys; print('\n'.join(m['title'] for m in json.load(sys.stdin)['query']['categorymembers']))" > "$out/news-titles.txt"
: > "$out/news.txt.part"
while IFS= read -r t; do
  curl -sf -G -A "$ua" https://en.wikinews.org/w/api.php --data-urlencode action=query --data-urlencode prop=extracts \
    --data-urlencode explaintext=1 --data-urlencode format=json --data-urlencode "titles=$t" \
    | python3 -c "import json,sys; [print(p.get('extract', '')) for p in json.load(sys.stdin)['query']['pages'].values()]" >> "$out/news.txt.part"
  sleep 2
done < "$out/news-titles.txt"
mv "$out/news.txt.part" "$out/news.txt"
}

[ -s "$out/wikipedia.txt" ] || {
: > "$out/wikipedia.txt.part"
for t in Large_language_model Climate_change Association_football Jazz Sourdough Stock_market; do
  curl -sf -A "$ua" "https://en.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=1&format=json&titles=$t" \
    | python3 -c "import json,sys; [print(p.get('extract', '')) for p in json.load(sys.stdin)['query']['pages'].values()]" >> "$out/wikipedia.txt.part"
  sleep 2
done
mv "$out/wikipedia.txt.part" "$out/wikipedia.txt"
}

cat "$out/gatsby.txt" "$out/news.txt" > "$out/novel-news.txt"
wc -w "$out"/*.txt
