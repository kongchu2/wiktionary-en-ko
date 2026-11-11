"""Append-only JSONL translation store; the last record for a key wins."""
import json
import threading


class Store:
    def __init__(self, path, key="id"):
        self.path = path
        self.key = key
        self.records = {}
        self._lock = threading.Lock()
        if path.exists():
            with open(path, encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        if line.endswith("\n"):
                            raise
                        break  # truncated last line from an interrupted append
                    self.records[rec[key]] = rec

    def get(self, k):
        return self.records.get(k)

    def add_many(self, recs):
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as f:
                for rec in recs:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    self.records[rec[self.key]] = rec

    def compact(self, sort_key=None):
        """Rewrite the file with one record per key, sorted for stable git diffs."""
        with self._lock:
            recs = sorted(self.records.values(), key=sort_key or (lambda r: r[self.key]))
            tmp = self.path.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                for rec in recs:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            tmp.replace(self.path)
