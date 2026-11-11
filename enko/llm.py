"""LLM backend: Claude Code CLI in headless mode (`claude -p`), using the user's subscription."""
import json
import os
import subprocess
import time

# Variables that make a nested `claude` think it runs inside this session.
_NESTED_ENV = ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT")
_LIMIT_MARKERS = ("usage limit", "rate limit", "rate_limit", "limit reached", "hit your", "overloaded")


class RateLimited(RuntimeError):
    pass


class ClaudeCLI:
    def __init__(self, model="sonnet", timeout=900, retries=2):
        self.model = model
        self.timeout = timeout
        self.retries = retries
        self.env = {k: v for k, v in os.environ.items() if k not in _NESTED_ENV}

    def call(self, system, prompt, schema):
        """Return the structured output dict matching `schema`."""
        cmd = [
            "claude", "-p",
            "--model", self.model,
            "--output-format", "json",
            "--tools", "",
            "--setting-sources", "",
            "--strict-mcp-config",
            "--no-session-persistence",
            "--system-prompt", system,
            "--json-schema", json.dumps(schema, ensure_ascii=False),
        ]
        last = None
        for attempt in range(self.retries + 1):
            try:
                r = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                                   timeout=self.timeout, env=self.env)
                out = json.loads(r.stdout) if r.stdout.strip().startswith("{") else {}
                if r.returncode == 0 and not out.get("is_error") and out.get("structured_output"):
                    return out["structured_output"]
                last = (out.get("result") or r.stderr or r.stdout)[-500:]
            except subprocess.TimeoutExpired:
                last = "timeout"
            if any(m in last.lower() for m in _LIMIT_MARKERS):
                raise RateLimited(last)
            time.sleep(10 * (attempt + 1))
        raise RuntimeError(f"claude CLI failed: {last}")
